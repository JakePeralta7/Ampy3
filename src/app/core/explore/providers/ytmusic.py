"""YouTube Music Explore provider.

Wraps the ``ytmusicapi`` library (synchronous) via ``asyncio.to_thread``
so it integrates cleanly with the async FastAPI stack.

Works fully anonymously.  Endpoints that require an authenticated account
(such as the personalised home feed) degrade gracefully instead of
erroring out.
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
    ExploreSection,
    MoodCategory,
)
from src.app.core.explore.registry import register_explore_provider
from src.app.settings import settings

logger = logging.getLogger(__name__)

_AUTH_REQUIRED_HINT = "provide authentication"

DEFAULT_COUNTRY = "global"


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
    owner = raw.get("owner")
    if isinstance(owner, str):
        return owner
    return raw.get("description", "")


def _item_id(raw: dict) -> str:
    for key in ("browseId", "videoId", "playlistId"):
        value = raw.get(key)
        if value:
            return value
    return ""


def _make_item(raw: dict, item_type: ExploreItemType, source_id: str) -> ExploreItem:
    return ExploreItem(
        id=_item_id(raw),
        title=raw.get("title", ""),
        subtitle=_subtitle(raw),
        item_type=item_type,
        thumbnail_url=_thumbnail_url(raw.get("thumbnails")),
        url=_browse_url(raw, item_type),
        source_id=source_id,
    )


def _browse_url(raw: dict, item_type: ExploreItemType) -> str | None:
    item_id = _item_id(raw)
    if not item_id:
        return None
    if item_type == ExploreItemType.SONG:
        return f"https://music.youtube.com/watch?v={item_id}"
    if item_type == ExploreItemType.ARTIST:
        return f"https://music.youtube.com/artist/{item_id}"
    if item_type == ExploreItemType.ALBUM:
        return f"https://music.youtube.com/album/{item_id}"
    if item_type == ExploreItemType.PLAYLIST:
        playlist_id = raw.get("playlistId") or raw.get("browseId")
        if playlist_id:
            return f"https://music.youtube.com/playlist?list={playlist_id}"
    return None


@register_explore_provider("youtube_music")
class YTMusicExploreProvider(ExploreProvider):
    provider_id = "youtube_music"
    display_name = "YouTube Music"
    anonymous = True

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

    async def _run(
        self,
        method_name: str,
        *args,
        fallback=None,
        **kwargs,
    ):
        """Call a ytmusicapi method in a thread; degrade on auth-required errors."""
        client = self._get_client()
        method = getattr(client, method_name)
        try:
            return await asyncio.to_thread(method, *args, **kwargs)
        except Exception as exc:  # noqa: BLE001 - ytmusicapi raises generic Exception
            if _AUTH_REQUIRED_HINT in str(exc).lower():
                logger.warning(
                    "%s requires an authenticated YouTube Music account; skipping.", method_name
                )
                return fallback
            raise

    # ── interface ───────────────────────────────────────────────────

    async def get_home(self) -> ExploreHome:
        raw = await self._run("get_home", fallback={})
        if not isinstance(raw, dict):
            return ExploreHome(sections=[])
        sections: list[ExploreSection] = []
        for title, items in raw.items():
            if not isinstance(items, list):
                continue
            cards = [self._home_item(i) for i in items]
            cards = [i for i in cards if i is not None]
            if cards:
                sections.append(ExploreSection(title=title, items=cards))
        return ExploreHome(sections=sections)

    def _home_item(self, raw) -> ExploreItem | None:
        if not isinstance(raw, dict):
            return None
        content = raw.get("content")
        if isinstance(content, dict) and "title" in content:
            raw = content
        if not raw.get("title"):
            return None
        if raw.get("videoId"):
            item_type = ExploreItemType.SONG
        elif raw.get("playlistId"):
            item_type = ExploreItemType.PLAYLIST
        else:
            item_type = ExploreItemType.PLAYLIST
        return _make_item(raw, item_type, "youtube_music")

    async def get_charts(self) -> ChartsBundle:
        raw = await self._run("get_charts", fallback={})
        chart = raw.get(DEFAULT_COUNTRY) if isinstance(raw, dict) else None
        if not isinstance(chart, dict):
            return ChartsBundle()
        return ChartsBundle(
            top_songs=[
                _make_item(s, ExploreItemType.SONG, "youtube_music")
                for s in chart.get("top_songs", [])
            ],
            top_artists=[
                _make_item(a, ExploreItemType.ARTIST, "youtube_music")
                for a in chart.get("top_artists", [])
            ],
            top_videos=[
                _make_item(v, ExploreItemType.VIDEO, "youtube_music")
                for v in chart.get("top_videos", [])
            ],
        )

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

    async def search_playlists(self, query: str) -> list[ExploreItem]:
        client = self._get_client()
        try:
            results: list[dict] = await asyncio.to_thread(client.search, query, filter="playlists")
        except (KeyError, TypeError, IndexError) as exc:
            logger.warning("Could not search playlists for %r: %s", query, exc)
            return []
        items = []
        for raw in results:
            if not isinstance(raw, dict) or not raw.get("title"):
                continue
            items.append(_make_item(raw, ExploreItemType.PLAYLIST, "youtube_music"))
        return items
