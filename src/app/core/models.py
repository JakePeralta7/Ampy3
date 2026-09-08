from __future__ import annotations

from abc import ABC, abstractmethod
from dataclasses import dataclass, field


class IPlatformSource(ABC):
    """Abstract base class for playlist extraction sources.

    Subclasses must set ``source_id`` and ``display_name`` class
    attributes and implement ``_fetch_playlist`` and ``supports_url``.
    """

    source_id: str
    """Unique identifier, e.g. ``"youtube_music"``."""

    display_name: str
    """Human-readable name, e.g. ``"YouTube Music"``."""

    async def get_playlist(self, playlist_url: str) -> PlaylistMetadata:
        """Return normalized playlist metadata for *playlist_url*.

        Caching lives in the platform's shared client (see
        ``src.app.core.clients``) rather than here, so syncs and Explore
        reuse the same cache entries.
        """
        return await self._fetch_playlist(playlist_url)

    @abstractmethod
    async def _fetch_playlist(self, playlist_url: str) -> PlaylistMetadata:
        """Fetch fresh normalized playlist metadata from this platform."""
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
