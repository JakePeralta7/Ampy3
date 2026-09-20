"""Match strategy abstractions for track matching."""

from __future__ import annotations

from abc import ABC, abstractmethod
from dataclasses import dataclass
from typing import TYPE_CHECKING, Literal

from src.app.core.matching.candidate import TrackCandidate

if TYPE_CHECKING:
    from src.app.core.models import TrackMetadata


class MatchStrategy(ABC):
    """Abstract base class for track matching strategies.

    Each strategy encapsulates a specific matching approach (MBID exact,
    fuzzy title+artist, album comparison, etc.) and can be composed
    into composite strategies for complex matching logic.
    """

    @abstractmethod
    async def match(
        self, track: TrackMetadata, candidates: list[TrackCandidate]
    ) -> TrackCandidate | None:
        """Find the best matching candidate for the given track.

        Args:
            track: The source track metadata to match.
            candidates: List of candidate tracks from target library.

        Returns:
            The best matching candidate, or None if no match found.
        """
        ...


@dataclass(frozen=True, slots=True)
class MBIDMatch(MatchStrategy):
    """Exact MusicBrainz ID matching strategy.

    Matches source track MBID against candidate MBID fields.
    Supports recording, artist, and album MBIDs.
    """

    field: str = "mbid"

    async def match(
        self, track: TrackMetadata, candidates: list[TrackCandidate]
    ) -> TrackCandidate | None:
        source_mbid = getattr(track, self.field, None)
        if not source_mbid:
            return None

        for candidate in candidates:
            target_mbid = getattr(candidate, self.field, None)
            if target_mbid and source_mbid == target_mbid:
                return candidate

        return None


@dataclass(frozen=True, slots=True)
class FuzzyTitleArtistMatch(MatchStrategy):
    """Fuzzy title + artist similarity matching.

    Combines title and artist similarity scores with configurable weights.
    Uses the existing matching functions from src.app.core.matching.
    """

    title_threshold: float = 0.75
    title_weight: float = 0.6
    artist_weight: float = 0.4

    async def match(
        self, track: TrackMetadata, candidates: list[TrackCandidate]
    ) -> TrackCandidate | None:
        from src.app.core.matching import _best_match

        if not track.title or not candidates:
            return None

        match = _best_match(
            track.title,
            [c.to_dict() for c in candidates],
            threshold=self.title_threshold,
            search_artist=track.artist_name or None,
            title_weight=self.title_weight,
            artist_weight=self.artist_weight,
        )
        if match:
            return TrackCandidate.from_dict(match)
        return None


@dataclass(frozen=True, slots=True)
class AlbumMatch(MatchStrategy):
    """Album name comparison matching.

    Supports multiple comparison strategies: exact, contains, fuzzy.
    """

    strategy: Literal["exact", "contains", "fuzzy"] = "exact"
    threshold: float = 0.70

    async def match(
        self, track: TrackMetadata, candidates: list[TrackCandidate]
    ) -> TrackCandidate | None:
        from src.app.core.matching import _normalize_album

        if not track.album_name or not candidates:
            return None

        ref_norm = _normalize_album(track.album_name).lower().strip()
        if not ref_norm:
            return None

        def _album_exact(ref: str, cand: str) -> float:
            return 1.0 if ref == cand else 0.0

        def _album_contains(ref: str, cand: str) -> float:
            if ref == cand:
                return 1.0
            if ref in cand or cand in ref:
                return 0.9
            return 0.0

        def _album_fuzzy(ref: str, cand: str) -> float:
            ref_tokens = set(ref.split())
            cand_tokens = set(cand.split())
            if not ref_tokens or not cand_tokens:
                return 0.0
            return len(ref_tokens & cand_tokens) / len(ref_tokens | cand_tokens)

        comparators = {
            "exact": _album_exact,
            "contains": _album_contains,
            "fuzzy": _album_fuzzy,
        }
        comparator = comparators.get(self.strategy, _album_exact)

        best_match = None
        best_score = 0.0

        for candidate in candidates:
            cand_album = candidate.album_name or ""
            cand_norm = _normalize_album(cand_album).lower().strip()
            if not cand_norm:
                continue
            score = comparator(ref_norm, cand_norm)
            if score > best_score:
                best_score = score
                best_match = candidate

        if best_match and best_score >= self.threshold:
            return best_match
        return None


@dataclass(frozen=True, slots=True)
class CompositeMatch(MatchStrategy):
    """Compose multiple match strategies with configurable logic.

    Can require all strategies to match (AND) or accept first match (OR).
    """

    strategies: tuple[MatchStrategy, ...]
    require_all: bool = False
    mode: Literal["sequential", "intersection"] = "sequential"

    async def match(
        self, track: TrackMetadata, candidates: list[TrackCandidate]
    ) -> TrackCandidate | None:
        if not candidates:
            return None

        if self.require_all:
            if self.mode == "intersection":
                # Each strategy runs on full candidate list, results intersected
                strategy_matches: list[set[str]] = []
                for strategy in self.strategies:
                    match = await strategy.match(track, candidates)
                    if match:
                        strategy_matches.append({match.item_id})
                    else:
                        strategy_matches.append(set())
                if not all(strategy_matches):
                    return None
                common_ids = set.intersection(*strategy_matches)
                if not common_ids:
                    return None
                # Return first candidate with matching ID
                for c in candidates:
                    if c.item_id in common_ids:
                        return c
                return None
            else:
                # Sequential filtering (current behavior)
                remaining = candidates
                for strategy in self.strategies:
                    match = await strategy.match(track, remaining)
                    if not match:
                        return None
                    remaining = [match]
                return remaining[0] if remaining else None

        for strategy in self.strategies:
            match = await strategy.match(track, candidates)
            if match:
                return match
        return None
