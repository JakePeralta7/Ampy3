"""Type-safe track candidate model for matching."""

from __future__ import annotations

from dataclasses import asdict, dataclass, field
from typing import Any


@dataclass(frozen=True, slots=True)
class TrackCandidate:
    """Type-safe candidate track from a target library.

    Used throughout the matching pipeline to ensure consistent
    data shape between search strategies, match strategies, and nodes.
    """

    item_id: str
    title: str
    artist_name: str
    album_name: str = ""
    duration_ms: int | None = None
    mbid: str | None = None
    artist_mbid: str | None = None
    album_mbid: str | None = None
    raw_data: dict[str, Any] = field(default_factory=dict)

    def to_dict(self) -> dict[str, Any]:
        """Convert to dictionary for serialization/legacy compatibility."""
        return asdict(self)

    @classmethod
    def from_dict(cls, data: dict[str, Any]) -> TrackCandidate | None:
        """Create from dictionary (e.g., legacy target search results).

        Returns None if item_id is missing or empty, as a candidate
        without an identifier is not useful for matching.
        """
        item_id = data.get("item_id") or data.get("id", "")
        if not item_id:
            return None

        known_fields = {
            "item_id",
            "title",
            "artist_name",
            "album_name",
            "duration_ms",
            "mbid",
            "artist_mbid",
            "album_mbid",
        }
        raw = {k: v for k, v in data.items() if k not in known_fields}
        return cls(
            item_id=item_id,
            title=data.get("title", ""),
            artist_name=data.get("artist_name", ""),
            album_name=data.get("album_name", ""),
            duration_ms=data.get("duration_ms"),
            mbid=data.get("mbid"),
            artist_mbid=data.get("artist_mbid"),
            album_mbid=data.get("album_mbid"),
            raw_data=raw,
        )
