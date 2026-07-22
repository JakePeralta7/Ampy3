"""Node-graph-based track matching engine.

Each rule has a canvas (nodes + edges) defining a dataflow program.
The engine executes nodes in dependency order and collects match candidates.
"""
from __future__ import annotations

import contextvars
import logging
import re
from collections import deque
from collections.abc import Callable, Coroutine
from typing import TYPE_CHECKING, Any

from sqlalchemy import select

from src.app.core.matching import _best_match, _match_titles, _normalize_album
from src.app.core.models import TrackMetadata
from src.app.db import AsyncSessionLocal, SessionLocal
from src.app.models import MatchRule

if TYPE_CHECKING:
    from src.app.core.targets.base import BaseTarget

logger = logging.getLogger(__name__)

# ─── Type Aliases (imported from core.nodes) ────────────────────

from src.app.core.nodes.base import (  # noqa: E402, F401
    NodeConfig,
    NodeHandlerBase,
    NodeHandlerProtocol,
    NodeInputs,
    NodeOutputs,
)

# Callable form is still used for simple function-based handlers.
NodeHandler = Callable[
    [NodeConfig, TrackMetadata, NodeInputs],
    Coroutine[Any, Any, NodeOutputs],
]

# ─── Handler Registry ─────────────────────────────────────────

_handlers: dict[str, NodeHandler | NodeHandlerBase] = {}


def register_node(node_type: str, handler: NodeHandler | NodeHandlerBase | None = None):
    """Decorator or direct call to register a node handler by type.

    Usage as decorator::

        @register_node("search")
        async def _handle_search(config, track, inputs): ...

    Usage with a :class:`NodeHandlerBase` instance::

        register_node("search", MySearchHandler())
    """
    if handler is not None:
        _handlers[node_type] = handler
        return handler

    def decorator(fn: NodeHandler | NodeHandlerBase) -> NodeHandler | NodeHandlerBase:
        _handlers[node_type] = fn
        return fn
    return decorator


def get_handler(node_type: str) -> NodeHandler | NodeHandlerBase | None:
    return _handlers.get(node_type)


# ─── Target Context ───────────────────────────────────────────

current_target: contextvars.ContextVar[BaseTarget | None] = contextvars.ContextVar(
    "current_target", default=None,
)


def get_current_target() -> BaseTarget:
    """Get the sync target for the current execution context.

    Node handlers call this instead of importing a specific target client.
    Raises ``RuntimeError`` if no target is set.
    """
    target = current_target.get()
    if target is None:
        raise RuntimeError(
            "No sync target available. Ensure NodeGraphExecutor receives a BaseTarget."
        )
    return target


# ─── Graph Executor ────────────────────────────────────────────

class NodeGraphExecutor:
    """Executes a single rule's node graph (canvas) for a given track.

    Handles:
    - Topological sort for dependency ordering
    - Data propagation through edges
    - Collection of ``match_output`` emissions
    """

    def __init__(self, target: BaseTarget):
        self._target = target

    async def execute(
        self,
        canvas: dict,
        track: TrackMetadata,
        *,
        collect_trace: bool = False,
    ) -> list[dict]:
        nodes: list[dict] = canvas.get("nodes", [])
        edges: list[dict] = canvas.get("edges", [])

        if not nodes:
            return []

        # Set the target context so node handlers can access it
        token = current_target.set(self._target)
        try:
            return await self._execute_impl(canvas, track, nodes, edges, collect_trace=collect_trace)
        finally:
            current_target.reset(token)

    async def _execute_impl(
        self,
        canvas: dict,
        track: TrackMetadata,
        nodes: list[dict],
        edges: list[dict],
        *,
        collect_trace: bool = False,
    ) -> list[dict]:

        node_map = {n["id"]: n for n in nodes}

        # Build adjacency: for each node, list of outgoing edge targets
        out_edges: dict[str, list[dict]] = {n["id"]: [] for n in nodes}
        in_edges: dict[str, list[dict]] = {n["id"]: [] for n in nodes}
        for edge in edges:
            src = edge["source"]
            tgt = edge["target"]
            if src in out_edges:
                out_edges[src].append(edge)
            if tgt in in_edges:
                in_edges[tgt].append(edge)

        # Topological sort (Kahn's algorithm)
        in_degree: dict[str, int] = {n["id"]: 0 for n in nodes}
        for edge in edges:
            if edge["target"] in in_degree:
                in_degree[edge["target"]] += 1

        queue = deque(n["id"] for n in nodes if in_degree[n["id"]] == 0)
        sorted_ids: list[str] = []
        while queue:
            nid = queue.popleft()
            sorted_ids.append(nid)
            for edge in out_edges.get(nid, []):
                tgt = edge["target"]
                if tgt in in_degree:
                    in_degree[tgt] -= 1
                    if in_degree[tgt] == 0:
                        queue.append(tgt)

        if len(sorted_ids) != len(nodes):
            logger.warning("Cycle detected in rule graph; executing in arbitrary order")

        # Execute in dependency order
        outputs: dict[str, NodeOutputs] = {}
        trace: list[dict] = [] if collect_trace else None
        match_results: list[dict] = []

        for nid in sorted_ids:
            node = node_map[nid]
            handler = get_handler(node["type"])
            if handler is None:
                logger.warning("Unknown node type '%s' (id=%s)", node["type"], nid)
                continue

            # Gather inputs from incoming edges
            inputs: NodeInputs = {}
            for edge in in_edges.get(nid, []):
                src_outputs = outputs.get(edge["source"], {})
                src_handle = edge.get("sourceHandle", "out")
                tgt_handle = edge.get("targetHandle", "in")
                inputs[tgt_handle] = src_outputs.get(src_handle)

            # Auto-provide reference data for compare nodes
            if node["type"] == "compare" and "reference" not in inputs:
                for src_nid in reversed(sorted_ids[:sorted_ids.index(nid)]):
                    src_output = outputs.get(src_nid, {})
                    for val in src_output.values():
                        if isinstance(val, dict) and "title" in val:
                            inputs.setdefault("reference", val)
                            break
                    if "reference" in inputs:
                        break

            step_start = logger.info("Executing node %s (%s)", nid, node["type"])

            result = await handler(node.get("config", {}), track, inputs)

            outputs[nid] = result

            if collect_trace:
                trace.append({
                    "node_id": nid,
                    "node_type": node["type"],
                    "config": node.get("config", {}),
                    "inputs": dict(inputs),
                    "outputs": dict(result),
                })

            # Collect match emissions from terminal compare nodes
            if node["type"] == "compare":
                match_data = result.get("out")
                if match_data is not None:
                    match_results.append(match_data)

            # Handle breakpoints
            if node.get("config", {}).get("breakpoint"):
                logger.info("Breakpoint hit at node %s (%s)", nid, node["type"])

        return match_results if not collect_trace else trace


# ─── Match Engine ──────────────────────────────────────────────

class MatchEngine:
    """Runs all active rules in priority order, collecting matches.

    Returns matches ordered by rule priority (then by execution order
    within each rule).
    """

    def __init__(self, target: BaseTarget):
        self._executor = NodeGraphExecutor(target)

    async def run(
        self,
        track: TrackMetadata,
        rule_ids: list[int] | None = None,
        rules: list[MatchRule] | None = None,
    ) -> list[dict]:
        if rules is None:
            rules = await self._load_rules(rule_ids)
        all_matches: list[dict] = []
        for rule in rules:
            try:
                matches = await self._executor.execute(rule.canvas, track)
                for m in matches:
                    m["_rule_id"] = rule.id
                    m["_rule_name"] = rule.name
                    m["_rule_priority"] = rule.priority
                all_matches.extend(matches)
            except Exception as e:
                logger.exception("Rule '%s' (id=%d) failed: %s", rule.name, rule.id, e)
        return all_matches

    async def trace(
        self,
        track: TrackMetadata,
        rule_ids: list[int] | None = None,
        rules: list[MatchRule] | None = None,
    ) -> list[dict]:
        """Execute rules and return full execution trace for debugging."""
        if rules is None:
            rules = await self._load_rules(rule_ids)
        traces: list[dict] = []
        for rule in rules:
            try:
                steps = await self._executor.execute(rule.canvas, track, collect_trace=True)
                traces.append({
                    "rule_id": rule.id,
                    "rule_name": rule.name,
                    "rule_priority": rule.priority,
                    "steps": steps,
                    "isinstance": isinstance(steps, list),
                })
            except Exception as e:
                logger.exception("Rule '%s' (id=%d) trace failed: %s", rule.name, rule.id, e)
                traces.append({
                    "rule_id": rule.id,
                    "rule_name": rule.name,
                    "rule_priority": rule.priority,
                    "steps": [],
                    "error": str(e),
                })
        return traces

    async def _load_rules(self, rule_ids: list[int] | None) -> list[MatchRule]:
        async with AsyncSessionLocal() as session:
            stmt = select(MatchRule).where(MatchRule.is_active == True)
            if rule_ids:
                stmt = stmt.where(MatchRule.id.in_(rule_ids))
            stmt = stmt.order_by(MatchRule.priority)
            result = await session.execute(stmt)
            rules = list(result.scalars().all())
        return rules


async def get_active_rules() -> list[MatchRule]:
    """Load active rules sorted by priority."""
    async with AsyncSessionLocal() as session:
        stmt = select(MatchRule).where(MatchRule.is_active == True).order_by(MatchRule.priority)
        result = await session.execute(stmt)
        return list(result.scalars().all())


def get_active_rules_sync() -> list[MatchRule]:
    """Load active rules sorted by priority (sync version for Celery workers)."""
    session = SessionLocal()
    try:
        stmt = select(MatchRule).where(MatchRule.is_active == True).order_by(MatchRule.priority)
        result = session.execute(stmt)
        return list(result.scalars().all())
    finally:
        session.close()


# ─── Generic Node Handlers ─────────────────────────────────────

TRACK_FIELDS = {"title", "artist_name", "album_name"}


def _apply_string_op(value: Any, config: dict, operation: str) -> Any:
    if operation == "lowercase":
        return str(value).lower()
    if operation == "uppercase":
        return str(value).upper()
    if operation == "trim":
        return re.sub(r'\s+', ' ', str(value)).strip()
    if operation == "replace":
        find = config.get("find", "")
        replacement = config.get("replacement", "")
        if config.get("case_sensitive", False):
            return str(value).replace(find, replacement)
        return re.sub(re.escape(find), replacement, str(value), flags=re.IGNORECASE)
    if operation == "regex_replace":
        pattern = config.get("pattern", "")
        replacement = config.get("replacement", "")
        flags = 0 if config.get("case_sensitive", False) else re.IGNORECASE
        return re.sub(pattern, replacement, str(value), flags=flags)
    if operation == "regex_match":
        pattern = config.get("pattern", "")
        flags = 0 if config.get("case_sensitive", False) else re.IGNORECASE
        return bool(re.search(pattern, str(value), flags))
    if operation == "regex_extract":
        pattern = config.get("pattern", "")
        group = config.get("group", 0)
        flags = 0 if config.get("case_sensitive", False) else re.IGNORECASE
        m = re.search(pattern, str(value), flags)
        return m.group(group) if m else None
    if operation == "contains":
        substr = config.get("substring", "")
        if config.get("case_sensitive", False):
            return substr in str(value)
        return substr.lower() in str(value).lower()
    if operation == "split":
        delimiter = config.get("delimiter", ",")
        return [s.strip() for s in str(value).split(delimiter)]
    if operation == "join":
        delimiter = config.get("delimiter", ", ")
        items = value if isinstance(value, list) else [value]
        return delimiter.join(str(v) for v in items)
    if operation == "substring":
        start = config.get("start", 0)
        end = config.get("end")
        return str(value)[start:end] if end is not None else str(value)[start:]
    return value


# -- Input / Output --------------------------------------------

@register_node("track_source")
async def _handle_track_source(config: NodeConfig, track: TrackMetadata, inputs: NodeInputs) -> NodeOutputs:
    return {
        "out": {
            "title": track.title or "",
            "artist_name": track.artist_name or "",
            "album_name": track.album_name or "",
            "duration_ms": track.duration_ms,
            "source_id": track.source_id,
            "track_number": track.track_number,
            "disc_number": track.disc_number,
            "mbid": track.mbid,
            "artist_mbid": track.artist_mbid,
            "album_mbid": track.album_mbid,
        }
    }


@register_node("constant")
async def _handle_constant(config: NodeConfig, track: TrackMetadata, inputs: NodeInputs) -> NodeOutputs:
    return {"out": config.get("value", "")}


@register_node("match_output")
async def _handle_match_output(config: NodeConfig, track: TrackMetadata, inputs: NodeInputs) -> NodeOutputs:
    return {"out": inputs.get("in")}


# -- Generic String Op -----------------------------------------

@register_node("transform")
async def _handle_string_op(config: NodeConfig, track: TrackMetadata, inputs: NodeInputs) -> NodeOutputs:
    field = config.get("field", "value")
    target_field = config.get("target_field", field)
    operation = config.get("operation", "lowercase")

    raw_input = inputs.get("in")

    if field == "value":
        value = str(raw_input) if raw_input is not None else ""
        result = _apply_string_op(value, config, operation)
        return {"out": result}

    track_data = raw_input if isinstance(raw_input, dict) else {}
    if not track_data:
        track_data = {
            "title": track.title or "",
            "artist_name": track.artist_name or "",
            "album_name": track.album_name or "",
        }
    value = str(track_data.get(field, ""))
    result = _apply_string_op(value, config, operation)

    out_data = dict(track_data)
    if result is not None:
        out_data[target_field] = result
    return {"out": out_data}


# -- Generic Logic Op -------------------------------------------

@register_node("logic_op")
async def _handle_logic_op(config: NodeConfig, track: TrackMetadata, inputs: NodeInputs) -> NodeOutputs:
    operation = config.get("operation", "and")
    a = inputs.get("a", inputs.get("in"))
    b = inputs.get("b", config.get("value"))

    if operation == "and":
        return {"out": bool(a) and bool(b)}
    if operation == "or":
        return {"out": bool(a) or bool(b)}
    if operation == "not":
        return {"out": not bool(inputs.get("in", False))}
    if operation == "if_else":
        condition = inputs.get("condition", False)
        true_val = inputs.get("true", inputs.get("in"))
        false_val = inputs.get("false", inputs.get("in"))
        return {"true": true_val if condition else None, "false": false_val if not condition else None}
    return {"out": False}


# -- Legacy: Simple value comparison (kept for backward compat, hidden from UI) --------

# Compare operator moved to legacy; use "compare" node for track matching instead


# -- Similarity / Threshold -------------------------------------

@register_node("similarity")
async def _handle_similarity(config: NodeConfig, track: TrackMetadata, inputs: NodeInputs) -> NodeOutputs:
    a = str(inputs.get("a", inputs.get("in", "")))
    b = str(inputs.get("b", config.get("value", "")))
    algorithm = config.get("algorithm", "jaccard")

    a_norm = a.lower().strip()
    b_norm = b.lower().strip()

    if algorithm == "exact":
        return {"out": 1.0 if a_norm == b_norm else 0.0}

    if algorithm == "substring":
        return {"out": 1.0 if a_norm in b_norm or b_norm in a_norm else 0.0}

    if algorithm == "jaccard":
        if not a_norm or not b_norm:
            return {"out": 0.0}
        tokens_a = set(a_norm.split())
        tokens_b = set(b_norm.split())
        intersection = tokens_a & tokens_b
        union = tokens_a | tokens_b
        return {"out": len(intersection) / len(union) if union else 0.0}

    if algorithm == "token_sort":
        if not a_norm or not b_norm:
            return {"out": 0.0}
        tokens_a = sorted(a_norm.split())
        tokens_b = sorted(b_norm.split())
        from difflib import SequenceMatcher
        sm = SequenceMatcher(None, tokens_a, tokens_b)
        return {"out": sm.ratio()}

    return {"out": 0.0}


@register_node("threshold")
async def _handle_threshold(config: NodeConfig, track: TrackMetadata, inputs: NodeInputs) -> NodeOutputs:
    value = inputs.get("in", 0)
    threshold = config.get("threshold", 0.75)
    try:
        passed = float(value) >= threshold
    except (ValueError, TypeError):
        passed = False
    return {"out": value if passed else None}


# -- Generic Plex Search ----------------------------------------

@register_node("plex_search")
async def _handle_plex_search(config: NodeConfig, track: TrackMetadata, inputs: NodeInputs) -> NodeOutputs:
    target = get_current_target()
    data = inputs.get("in", {})
    search_type = config.get("search_type", "title_artist_album")
    max_results = config.get("max_results", 50)

    # Support both legacy and new search types
    if search_type in ("artist_tracks", "artist_only"):
        artist = data.get("artist_name", "")
        if not artist:
            return {"out": []}
        results = await target.search_artist_tracks(artist)
        return {"out": results[:max_results]}

    if search_type == "title_only":
        title = data.get("title", "")
        if not title:
            return {"out": []}
        results = await target.search_title_only(title)
        return {"out": results[:max_results]}

    if search_type == "album_only":
        album = data.get("album_name", "")
        if not album:
            return {"out": []}
        results = await target.search_library(album=album)
        return {"out": results[:max_results]}

    if search_type == "title_artist":
        results = await target.search_library(
            title=data.get("title", ""),
            artist=data.get("artist_name", ""),
        )
        return {"out": results[:max_results]}

    if search_type == "artist_album":
        results = await target.search_library(
            artist=data.get("artist_name", ""),
            album=data.get("album_name", ""),
        )
        return {"out": results[:max_results]}

    # Default: title_artist_album or library
    results = await target.search_library(
        title=data.get("title", ""),
        artist=data.get("artist_name", ""),
        album=data.get("album_name", ""),
    )
    return {"out": results[:max_results] if results else []}


# Also register as 'search' for new system
@register_node("search")
async def _handle_search(config: NodeConfig, track: TrackMetadata, inputs: NodeInputs) -> NodeOutputs:
    """New simplified search node - uses checkbox config."""
    target = get_current_target()

    # Get data from edge input, or fall back to track data if no edge connected
    data = inputs.get("in", {})
    if not data or not isinstance(data, dict):
        # Use track data directly if no input edge
        data = {
            "title": track.title or "",
            "artist_name": track.artist_name or "",
            "album_name": track.album_name or "",
        }

    # Handle both new (fields_to_search array) and old (individual booleans) formats
    if "fields_to_search" in config:
        fields = config.get("fields_to_search", [])
        search_title = "search_title" in fields
        search_artist = "search_artist" in fields
        search_album = "search_album" in fields
    else:
        # Fallback to old format for backward compatibility
        search_title = config.get("search_title", True)
        search_artist = config.get("search_artist", True)
        search_album = config.get("search_album", True)

    max_results = config.get("max_results", 50)

    # Build search parameters based on checkboxes
    title = data.get("title", "") if search_title else ""
    artist = data.get("artist_name", "") if search_artist else ""
    album = data.get("album_name", "") if search_album else ""

    logger.info(f"[SEARCH] Input track: title={track.title}, artist={track.artist_name}, album={track.album_name}")
    logger.info(f"[SEARCH] Search config: title={search_title}, artist={search_artist}, album={search_album}")
    logger.info(f"[SEARCH] Search params: title={title}, artist={artist}, album={album}")

    # If nothing is checked, return empty
    if not search_title and not search_artist and not search_album:
        return {"out": []}

    # If only one field is checked, use specific search
    if search_title and not search_artist and not search_album:
        if not title:
            return {"out": []}
        results = await target.search_title_only(title)
        logger.info(f"[SEARCH] Title-only search returned {len(results)} results")
        return {"out": results[:max_results]}

    if search_artist and not search_title and not search_album:
        if not artist:
            return {"out": []}
        results = await target.search_artist_tracks(artist)
        logger.info(f"[SEARCH] Artist-only search returned {len(results)} results")
        return {"out": results[:max_results]}

    if search_album and not search_title and not search_artist:
        if not album:
            return {"out": []}
        results = await target.search_library(album=album)
        logger.info(f"[SEARCH] Album-only search returned {len(results)} results")
        return {"out": results[:max_results]}

    # For multiple fields checked, use library search
    results = await target.search_library(title=title, artist=artist, album=album)
    logger.info(f"[SEARCH] Multi-field search returned {len(results) if results else 0} results")
    return {"out": results[:max_results] if results else []}


# -- Generic Filter ----------------------------------------------

@register_node("filter")
async def _handle_filter(config: NodeConfig, track: TrackMetadata, inputs: NodeInputs) -> NodeOutputs:
    candidates = inputs.get("candidates", inputs.get("in", []))
    field = config.get("field", "artist_name")
    threshold = config.get("threshold", 0.6)
    reference = inputs.get("reference")

    if not isinstance(candidates, list):
        return {"out": []}

    # Fall back to the incoming track's own field value when the reference
    # port is not connected (linear-chain canvases from seed rules).
    if reference is None:
        reference = getattr(track, field, "") or ""
    ref_str = str(reference) if reference is not None else ""
    if not ref_str:
        return {"out": candidates}

    if field == "album_name":
        ref_norm = _normalize_album(ref_str)
        filtered = [
            c for c in candidates
            if _normalize_album(c.get("album_name", "")) == ref_norm
        ]
        return {"out": filtered}

    ref_norm = ref_str.lower().strip()
    filtered = []
    for c in candidates:
        val = str(c.get(field, ""))
        if not val:
            continue
        v_norm = val.lower().strip()
        sim = 0.0
        if v_norm == ref_norm:
            sim = 1.0
        elif v_norm in ref_norm or ref_norm in v_norm:
            sim = 0.85
        else:
            ref_tokens = set(ref_norm.split())
            val_tokens = set(v_norm.split())
            if ref_tokens and val_tokens:
                sim = len(ref_tokens & val_tokens) / len(ref_tokens | val_tokens)
        if sim >= threshold:
            filtered.append(c)

    return {"out": filtered}


# -- Plex Matching Utilities ------------------------------------

@register_node("pick_best")
async def _handle_pick_best(config: NodeConfig, track: TrackMetadata, inputs: NodeInputs) -> NodeOutputs:
    candidates = inputs.get("candidates", inputs.get("in", []))
    threshold = config.get("title_threshold", 0.75)

    search_title: str = ""
    title_input = inputs.get("title")
    if title_input is not None:
        search_title = str(title_input)
    elif isinstance(track.title, str):
        search_title = track.title

    search_artist: str = ""
    artist_input = inputs.get("artist")
    if artist_input is not None:
        search_artist = str(artist_input)
    elif isinstance(track.artist_name, str):
        search_artist = track.artist_name

    if not search_title or not isinstance(candidates, list):
        return {"out": None}

    match = _best_match(search_title, candidates, threshold=threshold, search_artist=search_artist or None)
    return {"out": match}


@register_node("sort_by_score")
async def _handle_sort_by_score(config: NodeConfig, track: TrackMetadata, inputs: NodeInputs) -> NodeOutputs:
    candidates = inputs.get("in", [])
    search_title = str(inputs.get("title", track.title or ""))

    if not isinstance(candidates, list) or not search_title:
        return {"out": candidates}

    scored = []
    for c in candidates:
        score = _match_titles(search_title, c.get("title", ""))
        scored.append((score, c))

    scored.sort(key=lambda x: x[0], reverse=config.get("descending", True))
    return {"out": [c for _, c in scored]}


# -- Compare (unified matching) ------------------------------------

@register_node("compare")
async def _handle_compare(config: NodeConfig, track: TrackMetadata, inputs: NodeInputs) -> NodeOutputs:
    """Compare search candidates against a reference track and return best match.
    
    Combines logic from pick_best, filter, and similarity nodes.
    
    Config:
    - fields_to_match: list of field names (title, artist_name, album_name)
    - threshold: minimum similarity score (0.0-1.0)
    - weights: dict of field weights {title: 50, artist_name: 25, album_name: 25}
    """
    from src.app.core.matching import _artist_similarity, _match_titles, _normalize_album

    # Accept input from any handle: candidates (explicit edge), in (implicit), or first available input
    candidates = inputs.get("candidates") or inputs.get("in") or inputs.get("out") or []
    logger.info(f"[COMPARE] Received inputs keys: {list(inputs.keys())}")
    logger.info(f"[COMPARE] Received candidates type: {type(candidates)}, len: {len(candidates) if isinstance(candidates, list) else 'N/A'}")

    if not isinstance(candidates, list):
        logger.info("[COMPARE] Candidates is not a list, returning None")
        return {"out": None}

    if not candidates:
        logger.info("[COMPARE] Candidates list is empty, returning None")
        return {"out": None}

    # Parse fields_to_match (can be string or list)
    fields_config = config.get("fields_to_match", "title")
    if isinstance(fields_config, str):
        fields = [f.strip() for f in fields_config.split(",")]
    else:
        fields = fields_config if isinstance(fields_config, list) else ["title"]

    threshold = config.get("threshold", 0.75)
    weights_config = config.get("weights", {})

    ref = inputs.get("reference")
    if not isinstance(ref, dict):
        ref = {
            "title": track.title or "",
            "artist_name": track.artist_name or "",
            "album_name": track.album_name or "",
        }
    ref_title = ref.get("title", track.title or "")
    ref_artist = ref.get("artist_name", track.artist_name or "")
    ref_album = ref.get("album_name", track.album_name or "")
    logger.info(f"[COMPARE] Reference: title={ref_title}, artist={ref_artist}, album={ref_album}")
    logger.info(f"[COMPARE] Fields to match: {fields}, threshold: {threshold}")

    # Parse weights (could be string, dict, or null)
    if isinstance(weights_config, str):
        # Try to parse JSON if it's a string
        import json
        try:
            weights = json.loads(weights_config) if weights_config and weights_config != "[object Object]" else {}
        except:
            weights = {}
    else:
        weights = weights_config if isinstance(weights_config, dict) else {}

    # Default weights if not specified
    if not weights:
        if "title" in fields:
            weights.setdefault("title", 50)
        if "artist_name" in fields:
            weights.setdefault("artist_name", 25 if "title" in fields else 50)
        if "album_name" in fields:
            weights.setdefault("album_name", 25 if "title" in fields else 25)

    # Normalize weights to sum to 100
    total_weight = sum(weights.get(f, 0) for f in fields)
    if total_weight > 0:
        normalized_weights = {f: (weights.get(f, 0) / total_weight * 100) for f in fields}
    else:
        normalized_weights = {f: (100 / len(fields)) for f in fields}

    best_match = None
    best_score = 0.0

    for candidate in candidates:
        field_scores = {}

        # Score each field
        if "title" in fields:
            ref_title = ref.get("title", "") or track.title or ""
            cand_title = candidate.get("title", "")
            field_scores["title"] = _match_titles(ref_title, cand_title) if ref_title and cand_title else 0.0

        if "artist_name" in fields:
            ref_artist = ref.get("artist_name", "") or track.artist_name or ""
            cand_artist = candidate.get("artist_name", "")
            field_scores["artist_name"] = _artist_similarity(ref_artist, cand_artist) if ref_artist and cand_artist else 0.0

        if "album_name" in fields:
            ref_album = ref.get("album_name", "") or track.album_name or ""
            cand_album = candidate.get("album_name", "")
            ref_norm = _normalize_album(ref_album).lower().strip()
            cand_norm = _normalize_album(cand_album).lower().strip()
            if ref_norm and cand_norm:
                field_scores["album_name"] = 1.0 if ref_norm == cand_norm else 0.0
            else:
                field_scores["album_name"] = 0.0

        # Compute weighted score
        weighted_score = sum(
            field_scores.get(f, 0.0) * (normalized_weights.get(f, 0) / 100)
            for f in fields
        )

        logger.info(f"[COMPARE] Candidate: {candidate.get('title')} by {candidate.get('artist_name')} - score: {weighted_score:.2f}, field_scores: {field_scores}")

        if weighted_score > best_score:
            best_score = weighted_score
            best_match = candidate

    logger.info(f"[COMPARE] Best match: {best_match.get('title') if best_match else 'None'}, score: {best_score:.2f}, threshold: {threshold}")

    if best_score >= threshold and best_match:
        return {"out": best_match}

    return {"out": None}


@register_node("search_musicbrainz")
async def _handle_search_musicbrainz(config: NodeConfig, track: TrackMetadata, inputs: NodeInputs) -> NodeOutputs:
    """Search MusicBrainz for recording info."""
    from src.app.core.musicbrainz import MusicBrainzResolver
    data = inputs.get("in", {})
    title = data.get("title", track.title or "")
    artist = data.get("artist_name", track.artist_name or "")

    if not title:
        return {"out": None}

    resolver = MusicBrainzResolver()
    recordings = await resolver.search_recording(title, artist)
    if recordings:
        return {"out": recordings[0]}
    return {"out": None}
