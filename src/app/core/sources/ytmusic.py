"""YouTube Music adapter using ytmusicapi for playlist extraction."""

from __future__ import annotations

import asyncio
import re
from typing import Any
from urllib import parse as urlparse

from ytmusicapi import YTMusic

from src.app.constants import SOURCE_YOUTUBE_MUSIC, SOURCE_YOUTUBE_MUSIC_DISPLAY
from src.app.core.models import IPlatformSource, PlaylistMetadata, TrackMetadata
from src.app.core.sources.registry import register_source
from src.app.services.ytauth import get_ytmusic_auth
from src.app.settings import settings


@register_source(SOURCE_YOUTUBE_MUSIC)
class YouTubeMusicSource(IPlatformSource):
    """Extract playlists from YouTube Music via ytmusicapi."""

    source_id = SOURCE_YOUTUBE_MUSIC
    display_name = SOURCE_YOUTUBE_MUSIC_DISPLAY

    YTM_HOSTS = ("music.youtube.com", "www.music.youtube.com")
    YTM_URL_PATTERN = re.compile(r"[a-zA-Z0-9_-]+")

    @classmethod
    def supports_url(cls, url: str) -> bool:
        return cls.is_valid_url(url)

    @classmethod
    def is_valid_url(cls, url: object) -> bool:
        """Return True only for well-formed public YouTube Music playlist URLs.

        Enforces scheme, host, and path so that arbitrary URLs (e.g. for
        SSRF against internal networks) never reach the underlying fetcher.
        Extra query parameters beyond ``list=`` are tolerated, matching how
        YouTube Music share links are commonly generated.
        """
        if not isinstance(url, str) or not url:
            return False
        try:
            parsed = urlparse.urlparse(url)
        except ValueError:
            return False
        if parsed.scheme not in ("http", "https"):
            return False
        if parsed.netloc.lower() not in cls.YTM_HOSTS:
            return False
        if parsed.path.rstrip("/") != "/playlist":
            return False
        playlist_ids = urlparse.parse_qs(parsed.query).get("list")
        return bool(playlist_ids) and bool(cls.YTM_URL_PATTERN.fullmatch(playlist_ids[0]))

    @classmethod
    def _parse_playlist_id(cls, url: str) -> str | None:
        parsed = urlparse.urlparse(url)
        playlist_ids = urlparse.parse_qs(parsed.query).get("list") if parsed.scheme else []
        if playlist_ids:
            return playlist_ids[0]
        return f"PL{url.split('list=')[-1]}"

    def get_playlist_cache_identifier(self, playlist_url: str) -> str:
        playlist_id = self._parse_playlist_id(playlist_url)
        if not playlist_id:
            raise ValueError(f"Could not parse playlist ID from: {playlist_url}")
        return playlist_id

    def _client(self) -> YTMusic:
        return YTMusic(auth=get_ytmusic_auth())

    async def _fetch_playlist(self, playlist_url: str) -> PlaylistMetadata:
        from ytmusicapi.exceptions import YTMusicError

        playlist_id = self.get_playlist_cache_identifier(playlist_url)
        client = self._client()
        try:
            data = await asyncio.wait_for(
                asyncio.to_thread(client.get_playlist, playlist_id, limit=None),
                timeout=settings.yt_dlp_timeout,
            )
        except TimeoutError:
            raise RuntimeError(
                f"Playlist extraction timed out ({settings.yt_dlp_timeout}s)."
            ) from None
        except YTMusicError as exc:
            raise RuntimeError(f"YouTube Music request failed: {exc}") from exc

        return self._parse_playlist_data(playlist_id, playlist_url, data)

    @staticmethod
    def _parse_playlist_data(
        playlist_id: str, playlist_url: str, data: dict[str, Any]
    ) -> PlaylistMetadata:
        tracks_raw = data.get("tracks", [])
        title = data.get("title", "") or "Unknown Playlist"
        description = data.get("description", "") or ""

        tracks: list[TrackMetadata] = []
        for entry in tracks_raw:
            if not isinstance(entry, dict):
                continue

            title_value = entry.get("title", "") or ""
            if not title_value:
                continue

            artists = entry.get("artists") or []
            artist = ", ".join(
                a.get("name", "") for a in artists if isinstance(a, dict) and a.get("name")
            )
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
            duration = entry.get("duration_seconds")

            tracks.append(
                TrackMetadata(
                    mbid=entry.get("musicbrainz_id"),
                    title=title_value,
                    artist_name=artist or None,
                    album_name=album or None,
                    duration_ms=int(duration * 1000) if duration else None,
                    source_id=entry.get("videoId") or None,
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
