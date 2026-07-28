"""YouTube Music adapter using yt-dlp for playlist extraction."""

from __future__ import annotations

import json
import re
from pathlib import Path
from typing import Any

from src.app.constants import SOURCE_YOUTUBE_MUSIC, SOURCE_YOUTUBE_MUSIC_DISPLAY
from src.app.core.models import IPlatformSource, PlaylistMetadata, TrackMetadata
from src.app.core.sources.registry import register_source
from src.app.settings import settings


@register_source(SOURCE_YOUTUBE_MUSIC)
class YouTubeMusicSource(IPlatformSource):
    """Extract playlists from YouTube Music via yt-dlp."""

    source_id = SOURCE_YOUTUBE_MUSIC
    display_name = SOURCE_YOUTUBE_MUSIC_DISPLAY

    YTM_URL_PATTERN = re.compile(r"(https?://music\.youtube\.com/playlist\?list=[a-zA-Z0-9_-]+)")

    @classmethod
    def supports_url(cls, url: str) -> bool:
        return bool(cls.YTM_URL_PATTERN.search(url))

    @classmethod
    def _parse_playlist_id(cls, url: str) -> str | None:
        match = cls.YTM_URL_PATTERN.search(url)
        if not match:
            return f"PL{url.split('list=')[-1]}"
        return match.group(1).split("list=")[-1]

    def get_playlist_cache_identifier(self, playlist_url: str) -> str:
        playlist_id = self._parse_playlist_id(playlist_url)
        if not playlist_id:
            raise ValueError(f"Could not parse playlist ID from: {playlist_url}")
        return playlist_id

    async def _fetch_playlist(self, playlist_url: str) -> PlaylistMetadata:
        playlist_id = self.get_playlist_cache_identifier(playlist_url)
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
            result = subprocess.run(
                cmd,
                capture_output=True,
                text=True,
                timeout=settings.yt_dlp_timeout,
            )
        except FileNotFoundError:
            raise RuntimeError(
                "yt-dlp is not installed. Install it via pip or ensure PATH contains yt-dlp."
            ) from None
        except subprocess.TimeoutExpired:
            raise RuntimeError(
                f"Playlist extraction timed out ({settings.yt_dlp_timeout}s)."
            ) from None

        if result.returncode != 0 and not result.stdout.strip():
            raise RuntimeError(f"yt-dlp failed: {result.stderr.strip()}")

        return self._parse_playlist_data(playlist_id, playlist_url, json.loads(result.stdout))

    @staticmethod
    def _parse_playlist_data(
        playlist_id: str, playlist_url: str, data: dict[str, Any]
    ) -> PlaylistMetadata:
        tracks_raw = data.get("entries", [])
        title = data.get("title", "Unknown Playlist")
        description = data.get("description", "")

        tracks: list[TrackMetadata] = []
        for entry in tracks_raw:
            if entry is None:
                continue

            title_value = entry.get("title", "") or ""
            if not title_value:
                continue

            artist = entry.get("creator", "") or entry.get("uploader", "") or ""
            album_value = entry.get("album")
            album = (
                album_value.get("name", "") if isinstance(album_value, dict) else album_value or ""
            )
            if (
                album
                and title
                and (album.lower() == title.lower() or album.lower() in title.lower())
            ):
                album = ""
            duration = entry.get("duration") or None

            tracks.append(
                TrackMetadata(
                    mbid=entry.get("musicbrainz_id"),
                    title=title_value,
                    artist_name=artist or None,
                    album_name=album or None,
                    duration_ms=int(duration * 1000) if duration else None,
                    source_id=entry.get("id") or None,
                )
            )

        return PlaylistMetadata(
            source_id=playlist_id,
            source=SOURCE_YOUTUBE_MUSIC,
            title=title,
            description=description,
            tracks=tracks,
            external_url=playlist_url,
        )
