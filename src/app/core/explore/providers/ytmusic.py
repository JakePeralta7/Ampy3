"""YouTube Music Explore provider.

Fetches raw content through the shared :class:`YouTubeMusicClient` (which
caches responses in Valkey, shared with the sync source) and maps it to
Explore models. Works fully anonymously; endpoints that require an
authenticated account (such as the personalised home feed) degrade
gracefully instead of erroring out.
"""

from __future__ import annotations

import logging

from src.app.core.clients import get_ytmusic_client
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
    auth_required = True

    async def get_home(self, force: bool = False) -> ExploreHome:
        try:
            raw = await get_ytmusic_client().get_home(force=force)
        except Exception as exc:  # noqa: BLE001 - degrade on auth-required errors only
            if _AUTH_REQUIRED_HINT not in str(exc).lower():
                raise
            logger.warning("get_home requires an authenticated YouTube Music account; skipping.")
            raw = {}
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

    async def get_charts(self, force: bool = False) -> ChartsBundle:
        try:
            raw = await get_ytmusic_client().get_charts(force=force)
        except Exception as exc:  # noqa: BLE001 - degrade on auth-required errors only
            if _AUTH_REQUIRED_HINT not in str(exc).lower():
                raise
            logger.warning("get_charts requires an authenticated YouTube Music account; skipping.")
            raw = {}
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

    async def get_moods(self, force: bool = False) -> list[MoodCategory]:
        raw = await get_ytmusic_client().get_mood_categories(force=force)
        if not isinstance(raw, dict):
            return []
        moods = []
        seen_ids: set[str] = set()
        seen_names: set[str] = set()
        for _section_name, section_items in raw.items():
            for raw_cat in section_items:
                mood_id = raw_cat.get("params", "")
                name = raw_cat.get("title", "")
                if mood_id in seen_ids or name.casefold() in seen_names:
                    continue
                seen_ids.add(mood_id)
                seen_names.add(name.casefold())
                moods.append(
                    MoodCategory(
                        id=mood_id,
                        name=name,
                        icon=None,
                        playlist_count=raw_cat.get("playlistCount"),
                    )
                )
        return moods

    async def get_mood_playlists(self, mood_id: str, force: bool = False) -> list[ExploreItem]:
        try:
            raw_playlists = await get_ytmusic_client().get_mood_playlists(mood_id, force=force)
        except (KeyError, TypeError, IndexError) as exc:
            logger.warning("Could not fetch playlists for mood %s: %s", mood_id, exc)
            return []
        return [
            _make_item(raw_pl, ExploreItemType.PLAYLIST, "youtube_music")
            for raw_pl in raw_playlists
            if isinstance(raw_pl, dict)
        ]

    async def search_playlists(self, query: str, force: bool = False) -> list[ExploreItem]:
        try:
            results = await get_ytmusic_client().search_playlists(query, force=force)
        except (KeyError, TypeError, IndexError) as exc:
            logger.warning("Could not search playlists for %r: %s", query, exc)
            return []
        items = []
        for raw in results:
            if not isinstance(raw, dict) or not raw.get("title"):
                continue
            items.append(_make_item(raw, ExploreItemType.PLAYLIST, "youtube_music"))
        return items
