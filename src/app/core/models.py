from __future__ import annotations

import asyncio
import hashlib
import json
import logging
from abc import ABC, abstractmethod
from dataclasses import asdict, dataclass, field
from typing import Any

logger = logging.getLogger(__name__)


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
        """Return playlist metadata, using the shared source-content cache when available.

        Uses a sync Valkey client (via ``asyncio.to_thread``) so that the
        connection pool is **not** bound to the current event loop.  This makes
        the cache work correctly from Celery workers where ``asyncio.run()``
        creates a temporary event loop each invocation.
        """
        cache_key = self._playlist_cache_key(playlist_url)

        try:
            from src.app.services.valkey import ValkeyService

            client = ValkeyService.get_sync_instance()
            cached: str | None = await asyncio.to_thread(client.get, cache_key)  # type: ignore[arg-type]
            if cached:
                logger.debug("Cache hit for %s playlist '%s'", self.source_id, cache_key)
                return self._deserialize_playlist(cached)
        except Exception as exc:
            logger.debug(
                "Playlist cache read failed for %s (continuing without cache): %s",
                self.source_id,
                exc,
            )

        playlist = await self._fetch_playlist(playlist_url)

        try:
            from src.app.services.valkey import ValkeyService
            from src.app.settings import settings

            client = ValkeyService.get_sync_instance()
            await asyncio.to_thread(
                client.setex,
                cache_key,
                settings.source_playlist_cache_ttl_seconds,
                json.dumps(asdict(playlist)),
            )
        except Exception as exc:
            logger.debug("Playlist cache write failed for %s (non-fatal): %s", self.source_id, exc)

        return playlist

    @abstractmethod
    async def _fetch_playlist(self, playlist_url: str) -> PlaylistMetadata:
        """Fetch fresh normalized playlist metadata from this platform."""
        ...

    def get_playlist_cache_identifier(self, playlist_url: str) -> str:
        """Return a stable per-source playlist identifier for cache keying.

        Sources with canonical playlist IDs should override this method. The
        URL hash keeps caching available by default for future source adapters.
        """
        return hashlib.sha256(playlist_url.encode()).hexdigest()

    def _playlist_cache_key(self, playlist_url: str) -> str:
        identifier = self.get_playlist_cache_identifier(playlist_url)
        return f"source:playlist:{self.source_id}:{identifier}"

    @staticmethod
    def _deserialize_playlist(payload: str) -> PlaylistMetadata:
        """Deserialize cache content and reject malformed values as cache misses."""
        data: Any = json.loads(payload)
        if not isinstance(data, dict):
            raise ValueError("Cached playlist has an invalid shape")
        tracks = data.pop("tracks", [])
        if not isinstance(tracks, list) or not all(isinstance(track, dict) for track in tracks):
            raise ValueError("Cached playlist contains an invalid track")
        return PlaylistMetadata(**data, tracks=[TrackMetadata(**track) for track in tracks])

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
