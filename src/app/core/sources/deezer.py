"""Deezer source adapter using the public Deezer API (no authentication)."""

from __future__ import annotations

import logging
import re

import httpx

from src.app.constants import SOURCE_DEEZER, SOURCE_DEEZER_DISPLAY
from src.app.core.models import IPlatformSource, PlaylistMetadata, TrackMetadata
from src.app.core.sources.registry import register_source

logger = logging.getLogger(__name__)

BASE_URL = "https://api.deezer.com"
REQUEST_TIMEOUT = 15

DEEZER_URL_PATTERN = re.compile(
    r"https?://(?:www\.)?deezer\.com/playlist/(\d+)",
    re.IGNORECASE,
)
LINK_PATTERN = re.compile(r"https?://deezer\.page\.link/.+", re.IGNORECASE)


@register_source(SOURCE_DEEZER)
class DeezerSource(IPlatformSource):
    """Extract playlists from Deezer via its public REST API."""

    source_id = SOURCE_DEEZER
    display_name = SOURCE_DEEZER_DISPLAY

    @classmethod
    def supports_url(cls, url: str) -> bool:
        return bool(DEEZER_URL_PATTERN.search(url)) or bool(LINK_PATTERN.search(url))

    @classmethod
    def _parse_playlist_id(cls, url: str) -> str:
        match = DEEZER_URL_PATTERN.search(url)
        if not match:
            raise ValueError(f"Could not parse Deezer playlist ID from: {url}")
        return match.group(1)

    def get_playlist_cache_identifier(self, playlist_url: str) -> str:
        return self._parse_playlist_id(playlist_url)

    async def _fetch_playlist(self, playlist_url: str) -> PlaylistMetadata:
        playlist_id = self._parse_playlist_id(playlist_url)
        try:
            resp = httpx.get(
                f"{BASE_URL}/playlist/{playlist_id}",
                timeout=REQUEST_TIMEOUT,
            )
            resp.raise_for_status()
            data = resp.json()
        except httpx.HTTPError as exc:
            raise RuntimeError(f"Deezer API request failed: {exc}") from exc

        if not isinstance(data, dict) or "tracks" not in data:
            raise RuntimeError(f"Deezer playlist {playlist_id} not found or is empty.")

        return self._parse_playlist_data(playlist_id, data)

    @staticmethod
    def _parse_playlist_data(playlist_id: str, data: dict) -> PlaylistMetadata:
        title = data.get("title", "Unknown Playlist")
        description = data.get("description", "")

        tracks: list[TrackMetadata] = []
        for entry in data.get("tracks", {}).get("data", []):
            if not isinstance(entry, dict):
                continue
            artist = entry.get("artist", {})
            album = entry.get("album", {})
            duration = entry.get("duration")
            tracks.append(
                TrackMetadata(
                    title=entry.get("title", "") or None,
                    artist_name=artist.get("name") if isinstance(artist, dict) else None,
                    album_name=album.get("title") if isinstance(album, dict) else None,
                    duration_ms=int(duration * 1000) if duration else None,
                    source_id=str(entry.get("id")) if entry.get("id") else None,
                )
            )

        return PlaylistMetadata(
            source_id=playlist_id,
            source=SOURCE_DEEZER,
            title=title,
            description=description,
            tracks=[t for t in tracks if t.title],
            external_url=f"https://www.deezer.com/playlist/{playlist_id}",
        )
