"""YouTube Music Explore provider.

Wraps the ``ytmusicapi`` library (synchronous) via ``asyncio.to_thread``
so it integrates cleanly with the async FastAPI stack.
"""

from __future__ import annotations

import asyncio
import logging
import os

from ytmusicapi import YTMusic

from src.app.core.explore.base import ExploreProvider
from src.app.core.explore.models import (
    ChartsBundle,
    ExploreHome,
    ExploreItem,
    ExploreItemType,
    MoodCategory,
)
from src.app.core.explore.registry import register_explore_provider
from src.app.settings import settings

logger = logging.getLogger(__name__)


def _thumbnail_url(thumbnails: list[dict] | None) -> str | None:
    if not thumbnails:
        return None
    return thumbnails[-1].get("url")


def _subtitle(raw: dict) -> str:
    artists = raw.get("artists")
    if isinstance(artists, list) and artists:
        names = [a.get("name", "") for a in artists if isinstance(a, dict)]
        return ", ".join(names)
    artist = raw.get("artist")
    if isinstance(artist, str):
        return artist
    return raw.get("description", "")


def _make_item(raw: dict, item_type: ExploreItemType, source_id: str) -> ExploreItem:
    return ExploreItem(
        id=raw.get("browseId") or raw.get("videoId") or raw.get("playlistId") or "",
        title=raw.get("title", ""),
        subtitle=_subtitle(raw),
        item_type=item_type,
        thumbnail_url=_thumbnail_url(raw.get("thumbnails")),
        url=_browse_url(raw, item_type),
        source_id=source_id,
    )


def _browse_url(raw: dict, item_type: ExploreItemType) -> str | None:
    if item_type == ExploreItemType.SONG:
        video_id = raw.get("videoId")
        if video_id:
            return f"https://music.youtube.com/watch?v={video_id}"
        return None
    playlist_id = raw.get("playlistId") or raw.get("browseId")
    if not playlist_id:
        return None
    return f"https://music.youtube.com/playlist?list={playlist_id}"


@register_explore_provider("youtube_music")
class YTMusicExploreProvider(ExploreProvider):
    provider_id = "youtube_music"
    display_name = "YouTube Music"

    def __init__(self) -> None:
        self._client: YTMusic | None = None

    # ── client initialisation ───────────────────────────────────────

    def _get_client(self) -> YTMusic:
        if self._client is not None:
            return self._client
        auth_path = settings.yt_dlp_cookies
        if auth_path and os.path.isfile(auth_path):
            logger.debug("Initialising YTMusic with auth from %s", auth_path)
            self._client = YTMusic(auth=auth_path)
        else:
            logger.debug("Initialising YTMusic without authentication")
            self._client = YTMusic()
        return self._client

    # ── interface ───────────────────────────────────────────────────

    async def get_home(self) -> ExploreHome:
        return ExploreHome(sections=[])

    async def get_charts(self) -> ChartsBundle:
        return ChartsBundle()

    async def get_moods(self) -> list[MoodCategory]:
        client = self._get_client()
        raw: dict = await asyncio.to_thread(client.get_mood_categories)
        moods = []
        for _section_name, section_items in raw.items():
            for raw_cat in section_items:
                moods.append(
                    MoodCategory(
                        id=raw_cat.get("params", ""),
                        name=raw_cat.get("title", ""),
                        icon=None,
                        playlist_count=raw_cat.get("playlistCount"),
                    )
                )
        return moods

    async def get_mood_playlists(self, mood_id: str) -> list[ExploreItem]:
        client = self._get_client()
        try:
            raw_playlists: list[dict] = await asyncio.to_thread(client.get_mood_playlists, mood_id)
        except (KeyError, TypeError, IndexError) as exc:
            logger.warning("Could not fetch playlists for mood %s: %s", mood_id, exc)
            return []
        return [
            _make_item(raw_pl, ExploreItemType.PLAYLIST, "youtube_music")
            for raw_pl in raw_playlists
        ]
