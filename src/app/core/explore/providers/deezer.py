"""Deezer Explore provider.

Uses Deezer's public REST API (``api.deezer.com``), which serves public
content — charts, editorial playlists, and playlist search — with **no
authentication** required.
"""

from __future__ import annotations

import logging

import httpx

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

BASE_URL = "https://api.deezer.com"
REQUEST_TIMEOUT = 15
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


def _album_item(raw: dict) -> ExploreItem:
    artist = raw.get("artist", {})
    artist_name = artist.get("name", "") if isinstance(artist, dict) else ""
    subtitle_parts = [artist_name] if artist_name else []
    release_date = raw.get("release_date")
    if release_date:
        subtitle_parts.append(release_date[:4])
    return ExploreItem(
        id=str(raw.get("id", "")),
        title=raw.get("title", ""),
        subtitle=" · ".join(subtitle_parts),
        item_type=ExploreItemType.ALBUM,
        thumbnail_url=_first_url(raw),
        url=f"https://www.deezer.com/album/{raw.get('id', '')}",
        source_id=SOURCE_ID,
    )


@register_explore_provider("deezer")
class DeezerExploreProvider(ExploreProvider):
    provider_id = "deezer"
    display_name = "Deezer"
    anonymous = True

    def _get(self, endpoint: str, params: dict | None = None) -> dict | None:
        try:
            resp = httpx.get(
                f"{BASE_URL}/{endpoint}",
                params=params,
                timeout=REQUEST_TIMEOUT,
            )
            resp.raise_for_status()
            return resp.json()
        except (httpx.HTTPError, ValueError) as exc:
            logger.warning("Deezer API request to %r failed: %s", endpoint, exc)
            return None

    def _data(self, endpoint: str, params: dict | None = None) -> list[dict]:
        payload = self._get(endpoint, params)
        if not isinstance(payload, dict):
            return []
        data = payload.get("data")
        return data if isinstance(data, list) else []

    # ── interface ───────────────────────────────────────────────────

    async def get_home(self) -> ExploreHome:
        sections: list[ExploreSection] = []

        playlists = self._data("chart/0/playlists")
        if playlists:
            sections.append(
                ExploreSection(
                    title="Trending Playlists",
                    items=[_playlist_item(p) for p in playlists[:12]],
                )
            )

        albums = self._data("album/recent")
        if albums:
            sections.append(
                ExploreSection(
                    title="New Releases",
                    items=[_album_item(a) for a in albums[:12]],
                )
            )

        return ExploreHome(sections=sections)

    async def get_charts(self) -> ChartsBundle:
        return ChartsBundle(
            top_songs=[_song_item(t) for t in self._data("chart/0/tracks")[:20]],
            top_artists=[_artist_item(a) for a in self._data("chart/0/artists")[:20]],
        )

    async def get_moods(self) -> list[MoodCategory]:
        moods = []
        for raw in self._data("editorial"):
            moods.append(
                MoodCategory(
                    id=str(raw.get("id", "")),
                    name=raw.get("name", ""),
                    icon=_first_url(raw),
                    playlist_count=raw.get("nb_playlists"),
                )
            )
        return moods

    async def get_mood_playlists(self, mood_id: str) -> list[ExploreItem]:
        return [_playlist_item(p) for p in self._data(f"editorial/{mood_id}/playlists")]

    async def search_playlists(self, query: str) -> list[ExploreItem]:
        return [_playlist_item(p) for p in self._data("search/playlist", {"q": query})]
