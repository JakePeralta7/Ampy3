from __future__ import annotations

from abc import ABC, abstractmethod
from dataclasses import dataclass, field


class IPlatformSource(ABC):
    """Abstract base class for playlist extraction sources.

    Subclasses must set ``source_id`` and ``display_name`` class
    attributes and implement ``get_playlist`` and ``supports_url``.
    """

    source_id: str
    """Unique identifier, e.g. ``"youtube_music"``."""

    display_name: str
    """Human-readable name, e.g. ``"YouTube Music"``."""

    @abstractmethod
    async def get_playlist(self, playlist_url: str) -> PlaylistMetadata:
        ...

    @classmethod
    @abstractmethod
    def supports_url(cls, url: str) -> bool:
        """Return ``True`` if *url* can be handled by this source."""
        ...


@dataclass(frozen=True)
class TrackMetadata:
    """Canonical music metadata model bridging all platforms via MusicBrainz."""

    mbid: str | None = None
    title: str | None = None
    artist_name: str | None = None
    album_name: str | None = None
    album_mbid: str | None = None
    artist_mbid: str | None = None
    duration_ms: int | None = None
    track_number: int | None = None
    disc_number: int | None = None
    source_id: str | None = None

    @property
    def is_matchable(self) -> bool:
        return all([self.title, self.artist_name])


@dataclass(frozen=True)
class PlaylistMetadata:
    """Represents a playlist from any source platform."""

    source_id: str
    source: str
    title: str
    description: str = ""
    tracks: list[TrackMetadata] = field(default_factory=list)
    external_url: str | None = None

    @property
    def is_complete(self) -> bool:
        return len(self.tracks) > 0


@dataclass(frozen=True)
class PlatformSearchResult:
    """Single match result from searching a platform."""

    mbid: str | None = None
    title: str | None = None
    artist_name: str | None = None
    album_name: str | None = None
    duration_ms: int | None = None
    confidence: float = 0.0


@dataclass(frozen=True)
class MatchedTrack:
    """A track matched from source platform to a target library."""

    source_track: TrackMetadata
    match_result: PlatformSearchResult | None = None
    item_id: str | None = None
    success: bool = False
    error: str | None = None


@dataclass(frozen=True)
class SyncStatus:
    """Overall sync operation status."""

    playlist_title: str
    total_tracks: int
    processed_tracks: int
    matched_tracks: int
    failed_tracks: int
    status: str = "pending"
    error: str | None = None


@dataclass(frozen=True)
class LibraryTrack:
    """Represents a track in a target media library."""

    item_id: str
    title: str
    artist_name: str
    album_name: str = ""
    duration: int = 0
    track_number: int | None = None
