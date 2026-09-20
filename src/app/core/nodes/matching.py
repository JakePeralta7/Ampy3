"""Comparison and best-match selection node handlers using MatchStrategy."""

from __future__ import annotations

import logging

from src.app.core.matching.candidate import TrackCandidate
from src.app.core.matching.strategies import (
    AlbumMatch,
    CompositeMatch,
    FuzzyTitleArtistMatch,
    MBIDMatch,
)
from src.app.core.models import TrackMetadata
from src.app.core.nodes.base import NodeHandlerBase, NodeInputs, NodeOutputs
from src.app.core.nodes.registry import register_node


def _parse_candidates(candidates_raw: list[dict]) -> list[TrackCandidate]:
    """Parse raw candidate dicts into TrackCandidate objects, filtering None."""
    return [
        c
        for c in [TrackCandidate.from_dict(c) for c in candidates_raw]
        if c is not None
    ]


logger = logging.getLogger(__name__)


@register_node("match_mbid")
class MBIDMatchNode(NodeHandlerBase):
    """Exact MusicBrainz ID matching node using MBIDMatch strategy.

    Config:
    - field: which MBID field to compare (mbid, artist_mbid, album_mbid). Default: mbid
    """

    async def execute(self, track: TrackMetadata, inputs: NodeInputs) -> NodeOutputs:
        candidates_raw = inputs.get("candidates") or []
        if not isinstance(candidates_raw, list) or not candidates_raw:
            return {"out": None}

        field = self._config.get("field", "mbid")
        strategy = MBIDMatch(field=field)

        candidates = _parse_candidates(candidates_raw)
        match = await strategy.match(track, candidates)

        return {"out": match.to_dict() if match else None}


@register_node("match_fuzzy")
class FuzzyMatchNode(NodeHandlerBase):
    """Fuzzy title + artist matching node using FuzzyTitleArtistMatch strategy.

    Config:
    - title_threshold: minimum combined score to accept a match. Default: 0.75
    - title_weight: weight for title score when combining. Default: 0.6
    - artist_weight: weight for artist score when combining. Default: 0.4
    """

    async def execute(self, track: TrackMetadata, inputs: NodeInputs) -> NodeOutputs:
        candidates_raw = inputs.get("candidates", inputs.get("in", []))
        if not isinstance(candidates_raw, list) or not candidates_raw:
            return {"out": None}

        strategy = FuzzyTitleArtistMatch(
            title_threshold=self._config.get("title_threshold", 0.75),
            title_weight=self._config.get("title_weight", 0.6),
            artist_weight=self._config.get("artist_weight", 0.4),
        )

        candidates = _parse_candidates(candidates_raw)
        match = await strategy.match(track, candidates)

        return {"out": match.to_dict() if match else None}


@register_node("match_album")
class AlbumMatchNode(NodeHandlerBase):
    """Album name matching node using AlbumMatch strategy.

    Config:
    - strategy: album matching strategy - "exact" | "contains" | "fuzzy". Default: exact
    - threshold: minimum score to accept a match. Default: 0.70
    """

    async def execute(self, track: TrackMetadata, inputs: NodeInputs) -> NodeOutputs:
        candidates_raw = inputs.get("candidates") or []
        if not isinstance(candidates_raw, list) or not candidates_raw:
            return {"out": None}

        strategy = AlbumMatch(
            strategy=self._config.get("strategy", "exact"),
            threshold=self._config.get("threshold", 0.70),
        )

        candidates = _parse_candidates(candidates_raw)
        match = await strategy.match(track, candidates)

        return {"out": match.to_dict() if match else None}


@register_node("match_composite")
class CompositeMatchNode(NodeHandlerBase):
    """Composite match node using CompositeMatch strategy.

    Combines multiple match strategies with configurable logic (AND/OR).

    Config:
    - strategies: list of strategy configs, each with:
      - type: "mbid" | "fuzzy" | "album"
      - field (for mbid): MBID field to compare. Default: mbid
      - title_threshold, title_weight, artist_weight (for fuzzy)
      - strategy (for album): "exact" | "contains" | "fuzzy". Default: exact
      - threshold (for album): minimum score. Default: 0.70
    - require_all: if true, all strategies must match (AND). Default: false (OR)
    - mode: "sequential" | "intersection". Default: "sequential"
    """

    async def execute(self, track: TrackMetadata, inputs: NodeInputs) -> NodeOutputs:
        candidates_raw = inputs.get("candidates", inputs.get("in", []))
        if not isinstance(candidates_raw, list) or not candidates_raw:
            return {"out": None}

        strategies = []
        for s in self._config.get("strategies", []):
            stype = s.get("type")
            if stype == "mbid":
                strategies.append(MBIDMatch(field=s.get("field", "mbid")))
            elif stype == "fuzzy":
                strategies.append(
                    FuzzyTitleArtistMatch(
                        title_threshold=s.get("title_threshold", 0.75),
                        title_weight=s.get("title_weight", 0.6),
                        artist_weight=s.get("artist_weight", 0.4),
                    )
                )
            elif stype == "album":
                strategies.append(AlbumMatch(
                    strategy=s.get("strategy", "exact"),
                    threshold=s.get("threshold", 0.70),
                ))
            else:
                logger.warning(f"Unknown match strategy type: {stype}")

        if not strategies:
            return {"out": None}

        composite = CompositeMatch(
            strategies=tuple(strategies),
            require_all=self._config.get("require_all", False),
            mode=self._config.get("mode", "sequential"),
        )

        candidates = _parse_candidates(candidates_raw)
        match = await composite.match(track, candidates)

        return {"out": match.to_dict() if match else None}


@register_node("match_output")
class MatchOutputNode(NodeHandlerBase):
    """Pass-through node to emit a match result.

    Used as the final node in a match chain to emit the matched candidate.
    """

    async def execute(self, track: TrackMetadata, inputs: NodeInputs) -> NodeOutputs:
        return {"out": inputs.get("in")}
