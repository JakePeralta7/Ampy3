"""Comparison and best-match selection node handlers."""

from __future__ import annotations

import json
import logging

from src.app.core.matching import _artist_similarity, _best_match, _match_titles, _normalize_album
from src.app.core.models import TrackMetadata
from src.app.core.nodes.base import NodeConfig, NodeInputs, NodeOutputs
from src.app.core.nodes.registry import register_node

logger = logging.getLogger(__name__)


@register_node("pick_best")
async def _handle_pick_best(
    config: NodeConfig,
    track: TrackMetadata,
    inputs: NodeInputs,
) -> NodeOutputs:
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

    match = _best_match(
        search_title,
        candidates,
        threshold=threshold,
        search_artist=search_artist or None,
    )
    return {"out": match}


@register_node("sort_by_score")
async def _handle_sort_by_score(
    config: NodeConfig,
    track: TrackMetadata,
    inputs: NodeInputs,
) -> NodeOutputs:
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


@register_node("compare")
async def _handle_compare(
    config: NodeConfig,
    track: TrackMetadata,
    inputs: NodeInputs,
) -> NodeOutputs:
    """Compare search candidates against a reference track and return best match.

    Combines logic from pick_best, filter, and similarity nodes.

    Config:
    - fields_to_match: list of field names (title, artist_name, album_name)
    - threshold: minimum similarity score (0.0-1.0)
    - weights: dict of field weights {title: 50, artist_name: 25, album_name: 25}
    """
    candidates = inputs.get("candidates") or inputs.get("in") or inputs.get("out") or []
    logger.debug(f"[COMPARE] Received inputs keys: {list(inputs.keys())}")
    c_len = len(candidates) if isinstance(candidates, list) else "N/A"
    logger.debug(
        "[COMPARE] Received candidates type: %s, len: %s",
        type(candidates),
        c_len,
    )

    if not isinstance(candidates, list):
        logger.debug("[COMPARE] Candidates is not a list, returning None")
        return {"out": None}

    if not candidates:
        logger.debug("[COMPARE] Candidates list is empty, returning None")
        return {"out": None}

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
    logger.debug(f"[COMPARE] Reference: title={ref_title}, artist={ref_artist}, album={ref_album}")
    logger.debug(f"[COMPARE] Fields to match: {fields}, threshold: {threshold}")

    if isinstance(weights_config, str):
        try:
            weights = (
                json.loads(weights_config)
                if (weights_config and weights_config != "[object Object]")
                else {}
            )
        except Exception:
            weights = {}
    else:
        weights = weights_config if isinstance(weights_config, dict) else {}

    if not weights:
        if "title" in fields:
            weights.setdefault("title", 50)
        if "artist_name" in fields:
            weights.setdefault("artist_name", 25 if "title" in fields else 50)
        if "album_name" in fields:
            weights.setdefault("album_name", 25 if "title" in fields else 25)

    total_weight = sum(weights.get(f, 0) for f in fields)
    if total_weight > 0:
        normalized_weights = {f: (weights.get(f, 0) / total_weight * 100) for f in fields}
    else:
        normalized_weights = {f: (100 / len(fields)) for f in fields}

    best_match = None
    best_score = 0.0

    for candidate in candidates:
        field_scores = {}

        if "title" in fields:
            ref_title = ref.get("title", "") or track.title or ""
            cand_title = candidate.get("title", "")
            title_match = _match_titles(ref_title, cand_title) if ref_title and cand_title else 0.0
            field_scores["title"] = title_match

        if "artist_name" in fields:
            ref_artist = ref.get("artist_name", "") or track.artist_name or ""
            cand_artist = candidate.get("artist_name", "")
            artist_match = (
                _artist_similarity(ref_artist, cand_artist) if ref_artist and cand_artist else 0.0
            )
            field_scores["artist_name"] = artist_match

        if "album_name" in fields:
            ref_album = ref.get("album_name", "") or track.album_name or ""
            cand_album = candidate.get("album_name", "")
            ref_norm = _normalize_album(ref_album).lower().strip()
            cand_norm = _normalize_album(cand_album).lower().strip()
            if ref_norm and cand_norm:
                field_scores["album_name"] = 1.0 if ref_norm == cand_norm else 0.0
            else:
                field_scores["album_name"] = 0.0

        weighted_score = sum(
            field_scores.get(f, 0.0) * (normalized_weights.get(f, 0) / 100) for f in fields
        )

        c_title = candidate.get("title")
        c_artist = candidate.get("artist_name")
        logger.debug(
            "[COMPARE] Candidate: %s by %s - score: %.2f, field_scores: %s",
            c_title,
            c_artist,
            weighted_score,
            field_scores,
        )

        if weighted_score > best_score:
            best_score = weighted_score
            best_match = candidate

    best_title = best_match.get("title") if best_match else "None"
    logger.debug(
        "[COMPARE] Best match: %s, score: %.2f, threshold: %s",
        best_title,
        best_score,
        threshold,
    )

    if best_score >= threshold and best_match:
        return {"out": best_match}

    return {"out": None}
