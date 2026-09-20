"""Core matching module - strategies and candidate types."""

from __future__ import annotations

from src.app.core.matching.candidate import TrackCandidate

# Re-export legacy functions from the original matching module
from src.app.core.matching.legacy import (  # noqa: F401
    _artist_similarity,
    _best_match,
    _extract_primary_artist,
    _match_titles,
    _normalize_album,
    normalize,
)
from src.app.core.matching.strategies import (
    AlbumMatch,
    CompositeMatch,
    FuzzyTitleArtistMatch,
    MatchStrategy,
    MBIDMatch,
)

__all__ = [
    "TrackCandidate",
    "MatchStrategy",
    "MBIDMatch",
    "FuzzyTitleArtistMatch",
    "AlbumMatch",
    "CompositeMatch",
    "normalize",
    "_normalize_album",
    "_extract_primary_artist",
    "_match_titles",
    "_artist_similarity",
    "_best_match",
]
