"""YouTube Music adapter using yt-dlp for playlist extraction."""
from __future__ import annotations

import json
import logging
import re
from pathlib import Path
from typing import List

import requests

from src.app.core.models import IPlatformSource, PlaylistMetadata, TrackMetadata
from src.app.core.sources.registry import register_source
from src.app.settings import settings

logger = logging.getLogger(__name__)


@register_source("youtube_music")
class YouTubeMusicSource(IPlatformSource):
    """Extracts playlists from YouTube Music via yt-dlp."""

    source_id = "youtube_music"
    display_name = "YouTube Music"

    YTM_URL_PATTERN = re.compile(r"(https?://music\.youtube\.com/playlist\?list=[a-zA-Z0-9_-]+)")

    @classmethod
    def supports_url(cls, url: str) -> bool:
        return bool(cls.YTM_URL_PATTERN.search(url))

    @classmethod
    def _parse_playlist_id(cls, url: str) -> str | None:
        match = cls.YTM_URL_PATTERN.search(url)
        if not match:
            return f"PL{url.split('list=')[-1]}"
        parts = match.group(1).split("list=")
        return parts[-1]

    async def get_playlist(self, playlist_url: str) -> PlaylistMetadata:
        pl_id = self._parse_playlist_id(playlist_url)
        if not pl_id:
            raise ValueError(f"Could not parse playlist ID from: {playlist_url}")

        cache_key = f"ytmusic:playlist:{pl_id}"

        # Try Valkey cache first (5 min TTL)
        from src.app.services.valkey import ValkeyService
        try:
            cache = ValkeyService.get_instance()
            cached = await cache.get(cache_key)
            if cached:
                logger.debug("Cache hit for playlist '%s' — using cached yt-dlp output", pl_id)
                return self._parse_playlist_data(pl_id, playlist_url, json.loads(cached))
        except Exception as e:
            logger.debug("Valkey cache read failed (continuing without cache): %s", e)

        # Fetch from yt-dlp
        cmd = [
            "yt-dlp",
            "--dump-single-json",
            "--no-download",
            "--no-warnings",
            "--ignore-errors",
        ]
        if settings.yt_dlp_cookies and Path(settings.yt_dlp_cookies).exists():
            cmd.extend(["--cookies", settings.yt_dlp_cookies])
        cmd.append(playlist_url)

        import subprocess
        try:
            result = subprocess.run(cmd, capture_output=True, text=True, timeout=settings.yt_dlp_timeout)
        except FileNotFoundError:
            raise RuntimeError("yt-dlp is not installed. Install it via pip or ensure PATH contains yt-dlp.")
        except subprocess.TimeoutExpired:
            raise RuntimeError(f"Playlist extraction timed out ({settings.yt_dlp_timeout}s).")

        if result.returncode != 0 and not result.stdout.strip():
            raise RuntimeError(f"yt-dlp failed: {result.stderr.strip()}")

        data = json.loads(result.stdout)

        # Cache the result (non-blocking on failure)
        try:
            cache = ValkeyService.get_instance()
            await cache.setex(cache_key, 300, json.dumps(data))
        except Exception as e:
            logger.debug("Failed to cache yt-dlp output (non-fatal): %s", e)

        return self._parse_playlist_data(pl_id, playlist_url, data)

    @staticmethod
    def _parse_playlist_data(pl_id: str, playlist_url: str, data: dict) -> PlaylistMetadata:
        tracks_raw = data.get("entries", [])
        title = data.get("title", "Unknown Playlist")
        pl_description = data.get("description", "")

        tracks: list[TrackMetadata] = []
        for entry in tracks_raw:
            if entry is None:
                continue

            title_val = entry.get("title", "") or ""
            if not title_val:
                continue

            artist = entry.get("creator", "") or entry.get("uploader", "") or ""
            album = entry.get("album", {}).get("name", "") if isinstance(entry.get("album"), dict) else (entry.get("album", "") or "")
            if album and title and (album.lower() == title.lower() or title.lower().find(album.lower()) >= 0):
                album = ""
            duration = entry.get("duration") or None
            mbid = entry.get("musicbrainz_id", None)

            tracks.append(TrackMetadata(
                mbid=mbid,
                title=title_val if title_val else None,
                artist_name=artist if artist else None,
                album_name=album if album else None,
                duration_ms=int(duration * 1000) if duration else None,
                source_id=entry.get("id") or None,
            ))

        return PlaylistMetadata(
            source_id=pl_id,
            source="youtube_music",
            title=title,
            description=pl_description,
            tracks=tracks,
            external_url=playlist_url,
        )


