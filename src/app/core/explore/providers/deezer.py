"""Deezer Explore provider.

Uses the shared :class:`DeezerClient` against Deezer's public REST API
(``api.deezer.com``), which serves public content — editorial playlists and
playlist search — with **no authentication** required. Client responses are
cached in Valkey, shared with the sync source.
"""

from __future__ import annotations

import logging
from typing import Any

import httpx

from src.app.core.clients import get_deezer_client
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

SOURCE_ID = "deezer"


def _first_url(raw: dict) -> str | None:
    if not isinstance(raw, dict):
        return None
    for key in ("picture_xl", "picture_big", "picture_medium", "cover_xl", "cover_big"):
        value = raw.get(key)
        if value:
            return value
    return None


def _playlist_item(raw: dict) -> ExploreItem:
    playlist_id = str(raw.get("id", ""))
    creator = raw.get("creator", {})
    creator_name = creator.get("name", "") if isinstance(creator, dict) else ""
    subtitle_parts = [creator_name] if creator_name else []
    nb_tracks = raw.get("nb_tracks")
    if nb_tracks:
        subtitle_parts.append(f"{nb_tracks} tracks")
    return ExploreItem(
        id=playlist_id,
        title=raw.get("title", ""),
        subtitle=" · ".join(subtitle_parts),
        item_type=ExploreItemType.PLAYLIST,
        thumbnail_url=_first_url(raw),
        url=f"https://www.deezer.com/playlist/{playlist_id}",
        source_id=SOURCE_ID,
    )


def _song_item(raw: dict) -> ExploreItem:
    artist = raw.get("artist", {})
    artist_name = artist.get("name", "") if isinstance(artist, dict) else ""
    return ExploreItem(
        id=str(raw.get("id", "")),
        title=raw.get("title", ""),
        subtitle=artist_name,
        item_type=ExploreItemType.SONG,
        thumbnail_url=_first_url(
            raw.get("album", {}) if isinstance(raw.get("album"), dict) else raw
        ),
        url=f"https://www.deezer.com/track/{raw.get('id', '')}",
        source_id=SOURCE_ID,
    )


def _artist_item(raw: dict) -> ExploreItem:
    return ExploreItem(
        id=str(raw.get("id", "")),
        title=raw.get("name", ""),
        subtitle="Artist",
        item_type=ExploreItemType.ARTIST,
        thumbnail_url=_first_url(raw),
        url=f"https://www.deezer.com/artist/{raw.get('id', '')}",
        source_id=SOURCE_ID,
    )


@register_explore_provider("deezer")
class DeezerExploreProvider(ExploreProvider):
    provider_id = "deezer"
    display_name = "Deezer"
    anonymous = True

    async def _list(self, method: str, *args, force: bool = False) -> list[dict]:
        """Fetch a list-backed endpoint, returning [] on failure."""
        try:
            payload: Any = await getattr(get_deezer_client(), method)(*args, force=force)
        except (httpx.HTTPError, ValueError) as exc:
            logger.warning("Deezer API request failed: %s", exc)
            return []
        if not isinstance(payload, dict):
            return []
        data = payload.get("data")
        return data if isinstance(data, list) else []

    # ── interface ───────────────────────────────────────────────────

    async def get_home(self, force: bool = False) -> ExploreHome:
        sections: list[ExploreSection] = []

        playlists = await self._list("get_trending_playlists", force=force)
        if playlists:
            sections.append(
                ExploreSection(
                    title="Trending Playlists",
                    items=[_playlist_item(p) for p in playlists[:12]],
                )
            )

        return ExploreHome(sections=sections)

    async def get_charts(self, force: bool = False) -> ChartsBundle:
        tracks = await self._list("get_top_tracks", force=force)
        artists = await self._list("get_top_artists", force=force)
        return ChartsBundle(
            top_songs=[_song_item(t) for t in tracks[:20]],
            top_artists=[_artist_item(a) for a in artists[:20]],
        )

    async def get_moods(self, force: bool = False) -> list[MoodCategory]:
        try:
            raw = await get_deezer_client().get_moods(force=force)
        except (httpx.HTTPError, ValueError) as exc:
            logger.warning("Deezer API request failed: %s", exc)
            return []
        moods = []
        for raw_mood in raw if isinstance(raw, list) else []:
            moods.append(
                MoodCategory(
                    id=str(raw_mood.get("id", "")),
                    name=raw_mood.get("name", ""),
                    icon=_first_url(raw_mood),
                    playlist_count=raw_mood.get("nb_playlists"),
                )
            )
        return moods

    async def get_mood_playlists(self, mood_id: str, force: bool = False) -> list[ExploreItem]:
        playlists = await self._list("get_mood_playlists", mood_id, force=force)
        return [_playlist_item(p) for p in playlists]

    async def search_playlists(self, query: str, force: bool = False) -> list[ExploreItem]:
        playlists = await self._list("search_playlists", query, force=force)
        return [_playlist_item(p) for p in playlists]
