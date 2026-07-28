"""Node-graph-based track matching engine.

Each rule has a canvas (nodes + edges) defining a dataflow program.
The engine executes nodes in dependency order and collects match candidates.
"""

from __future__ import annotations

import logging
from collections import deque
from typing import TYPE_CHECKING, Any

from sqlalchemy import select

# Import nodes package to trigger handler registration.
import src.app.core.nodes  # noqa: F401
from src.app.core.models import TrackMetadata
from src.app.core.nodes.base import NodeConfig, NodeInputs, NodeOutputs
from src.app.core.nodes.registry import NodeRegistry, current_target
from src.app.db import AsyncSessionLocal, SessionLocal
from src.app.models import MatchRule

if TYPE_CHECKING:
    from src.app.core.targets.base import BaseTarget

logger = logging.getLogger(__name__)


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
        canvas: dict[str, Any],
        track: TrackMetadata,
        *,
        collect_trace: bool = False,
    ) -> list[dict[str, Any]]:
        nodes: list[dict[str, Any]] = canvas.get("nodes", [])
        edges: list[dict[str, Any]] = canvas.get("edges", [])

        if not nodes:
            return []

        token = current_target.set(self._target)
        try:
            return await self._execute_impl(
                canvas,
                track,
                nodes,
                edges,
                collect_trace=collect_trace,
            )
        finally:
            current_target.reset(token)

    async def _execute_impl(
        self,
        canvas: dict[str, Any],
        track: TrackMetadata,
        nodes: list[dict[str, Any]],
        edges: list[dict[str, Any]],
        *,
        collect_trace: bool = False,
    ) -> list[dict[str, Any]]:

        node_map = {n["id"]: n for n in nodes}

        out_edges: dict[str, list[dict[str, Any]]] = {n["id"]: [] for n in nodes}
        in_edges: dict[str, list[dict[str, Any]]] = {n["id"]: [] for n in nodes}
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

        outputs: dict[str, NodeOutputs] = {}
        trace: list[dict[str, Any]] | None = [] if collect_trace else None
        match_results: list[dict[str, Any]] = []

        for nid in sorted_ids:
            node = node_map[nid]
            try:
                handler = NodeRegistry.create(node["type"], node.get("config", {}))
            except KeyError:
                logger.warning("Unknown node type '%s' (id=%s)", node["type"], nid)
                continue

            inputs: NodeInputs = {}
            for edge in in_edges.get(nid, []):
                src_outputs = outputs.get(edge["source"], {})
                src_handle = edge.get("sourceHandle", "out")
                tgt_handle = edge.get("targetHandle", "in")
                inputs[tgt_handle] = src_outputs.get(src_handle)

            # Auto-provide reference data for compare nodes
            if node["type"] == "compare" and "reference" not in inputs:
                for src_nid in reversed(sorted_ids[: sorted_ids.index(nid)]):
                    src_output = outputs.get(src_nid, {})
                    for val in src_output.values():
                        if isinstance(val, dict) and "title" in val:
                            inputs.setdefault("reference", val)
                            break
                    if "reference" in inputs:
                        break

            logger.debug("Executing node %s (%s)", nid, node["type"])

            result = await handler(track, inputs)

            outputs[nid] = result

            if collect_trace and trace is not None:
                trace.append(
                    {
                        "node_id": nid,
                        "node_type": node["type"],
                        "config": node.get("config", {}),
                        "inputs": dict(inputs),
                        "outputs": dict(result),
                    }
                )

            if node["type"] == "compare":
                match_data = result.get("out")
                if match_data is not None:
                    match_results.append(match_data)

            if node.get("config", {}).get("breakpoint"):
                logger.debug("Breakpoint hit at node %s (%s)", nid, node["type"])

        return match_results if not collect_trace else (trace or [])


# ─── Match Engine ──────────────────────────────────────────────


def _rule_canvas(rule: MatchRule) -> dict[str, Any]:
    """Convert a MatchRule's yaml_content to a canvas dict for the executor."""
    from src.app.match_rules.parser import yaml_to_canvas
    from src.app.match_rules.validator import validate_rule_yaml

    rule_def = validate_rule_yaml(rule.yaml_content)
    return yaml_to_canvas(rule_def)


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
    ) -> list[dict[str, Any]]:
        if rules is None:
            rules = await self._load_rules(rule_ids)
        all_matches: list[dict[str, Any]] = []
        for rule in rules:
            try:
                canvas = _rule_canvas(rule)
                matches = await self._executor.execute(canvas, track)
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
    ) -> list[dict[str, Any]]:
        """Execute rules and return full execution trace for debugging."""
        if rules is None:
            rules = await self._load_rules(rule_ids)
        traces: list[dict[str, Any]] = []
        for rule in rules:
            try:
                canvas = _rule_canvas(rule)
                steps = await self._executor.execute(canvas, track, collect_trace=True)
                traces.append(
                    {
                        "rule_id": rule.id,
                        "rule_name": rule.name,
                        "rule_priority": rule.priority,
                        "steps": steps,
                        "isinstance": isinstance(steps, list),
                    }
                )
            except Exception as e:
                logger.exception("Rule '%s' (id=%d) trace failed: %s", rule.name, rule.id, e)
                traces.append(
                    {
                        "rule_id": rule.id,
                        "rule_name": rule.name,
                        "rule_priority": rule.priority,
                        "steps": [],
                        "error": str(e),
                    }
                )
        return traces

    async def _load_rules(self, rule_ids: list[int] | None) -> list[MatchRule]:
        async with AsyncSessionLocal() as session:
            stmt = select(MatchRule).where(MatchRule.is_active)
            if rule_ids:
                stmt = stmt.where(MatchRule.id.in_(rule_ids))
            stmt = stmt.order_by(MatchRule.priority)
            result = await session.execute(stmt)
            rules = list(result.scalars().all())
        return rules


async def get_active_rules() -> list[MatchRule]:
    """Load active rules sorted by priority."""
    async with AsyncSessionLocal() as session:
        stmt = select(MatchRule).where(MatchRule.is_active).order_by(MatchRule.priority)
        result = await session.execute(stmt)
        return list(result.scalars().all())


def get_active_rules_sync() -> list[MatchRule]:
    """Load active rules sorted by priority (sync version for Celery workers)."""
    session = SessionLocal()
    try:
        stmt = select(MatchRule).where(MatchRule.is_active).order_by(MatchRule.priority)
        result = session.execute(stmt)
        return list(result.scalars().all())
    finally:
        session.close()
