"""Jellyfin sync target."""

from __future__ import annotations

import logging
import re
from typing import Any, ClassVar

import httpx

from src.app.constants import TARGET_JELLYFIN
from src.app.core.matching import normalize
from src.app.core.targets.base import BaseTarget
from src.app.core.targets.registry import TargetRegistry

logger = logging.getLogger(__name__)


def _normalize_search_query(query: str) -> str:
    """Strip characters that cause Jellyfin Lucene search issues."""
    query = re.sub(r"\(.*?\)", "", query)
    query = re.sub(r"\[.*?\]", "", query)
    query = re.sub(r"\{.*?\}", "", query)
    query = re.sub(r"[(){}\[\]]", "", query)
    query = re.sub(r"\.{2,}", " ", query)
    query = re.sub(r"^[.\u2026]+", "", query)
    query = query.replace(",", " ")
    return normalize(query, strip_quotes=True, collapse_whitespace=True)


class JellyfinTarget(BaseTarget):
    """Jellyfin sync target."""

    target_id: ClassVar[str] = TARGET_JELLYFIN
    display_name: ClassVar[str] = TARGET_JELLYFIN

    def __init__(self, api_key: str, base_url: str, user_id: str) -> None:
        self._api_key = api_key
        self._base_url = base_url.rstrip("/")
        self._user_id = user_id
        self._client: httpx.AsyncClient | None = None
        self._client_loop_id: int | None = None

    @property
    def client(self) -> httpx.AsyncClient:
        """Return an httpx.AsyncClient bound to the current event loop."""
        import asyncio

        try:
            loop = asyncio.get_running_loop()
            loop_id = id(loop)
        except RuntimeError:
            loop_id = None

        if self._client is not None and self._client_loop_id == loop_id:
            return self._client

        self._client = httpx.AsyncClient(base_url=self._base_url, timeout=15.0)
        self._client.headers.update(
            {
                "X-Emby-Token": self._api_key,
                "Content-Type": "application/json",
                "MediaBrowser": "Ampy3, test connection",
            }
        )
        self._client_loop_id = loop_id
        return self._client

    # ── Helpers ──────────────────────────────────────────────────

    @staticmethod
    def _to_duration_seconds(runtime_ticks: int | None) -> int:
        if not runtime_ticks:
            return 0
        return int(runtime_ticks / 10_000_000)

    @staticmethod
    def _pick_artist(item: dict[str, Any]) -> str:
        artists = item.get("ArtistItems") or []
        if artists and isinstance(artists, list):
            first = artists[0] or {}
            name = first.get("Name")
            if isinstance(name, str):
                return name
        artist = item.get("Artists") or []
        if artist and isinstance(artist, list) and isinstance(artist[0], str):
            return artist[0]
        return ""

    def _playlist_out(self, item: dict[str, Any]) -> dict[str, Any]:
        pid = str(item.get("Id", ""))
        return {
            "title": item.get("Name", ""),
            "rating_key": pid,
            "playlist_id": pid,
            "summary": item.get("Overview", "") or "",
            "track_count": int(item.get("ChildCount") or 0),
        }

    def _track_out(self, item: dict[str, Any]) -> dict[str, Any]:
        item_id = str(item.get("Id", ""))
        return {
            "item_id": item_id,
            "title": item.get("Name", "") or "",
            "artist_name": self._pick_artist(item),
            "album_name": item.get("Album", "") or "",
            "duration": self._to_duration_seconds(item.get("RunTimeTicks")),
            "duration_ms": int((item.get("RunTimeTicks") or 0) / 10_000),
            "playlist_item_id": item.get("PlaylistItemId"),
        }

    # ── Playlist operations ──────────────────────────────────────

    async def search_playlists(self, query: str) -> list[dict[str, Any]]:
        try:
            resp = await self.client.get(
                f"/Users/{self._user_id}/Items",
                params={
                    "IncludeItemTypes": "Playlist",
                    "Recursive": "true",
                    "Fields": "ChildCount,Overview",
                    "SortBy": "SortName",
                    "Limit": "200",
                },
            )
            resp.raise_for_status()
            items = resp.json().get("Items", [])
            out = [self._playlist_out(item) for item in items]
            if not query:
                return out
            q = query.lower().strip()
            return [p for p in out if q in str(p.get("title", "")).lower()]
        except Exception as exc:
            logger.error("Failed to search Jellyfin playlists: %s", exc)
            return []

    async def get_playlist_details(self, playlist_id: str) -> dict[str, Any] | None:
        try:
            resp = await self.client.get(f"/Users/{self._user_id}/Items/{playlist_id}")
            resp.raise_for_status()
            item = resp.json()
            return self._playlist_out(item)
        except Exception as exc:
            logger.error("Failed to get Jellyfin playlist %s: %s", playlist_id, exc)
            return None

    async def create_playlist(
        self,
        title: str,
        items: list[dict[str, Any]],
        custom_metadata: dict[str, Any] | None = None,
    ) -> str | None:
        del custom_metadata
        ids = [str(i.get("item_id") or i.get("id") or "") for i in items]
        ids = [i for i in ids if i]
        try:
            params = {
                "Name": title,
                "UserId": self._user_id,
                "MediaType": "Audio",
            }
            if ids:
                params["Ids"] = ",".join(ids)
            resp = await self.client.post("/Playlists", params=params)
            resp.raise_for_status()
            data = resp.json()
            playlist_id = data.get("Id")
            if isinstance(playlist_id, str) and playlist_id:
                return playlist_id
            if isinstance(data.get("ItemId"), str):
                return data["ItemId"]
            logger.error("Jellyfin playlist creation response missing Id: %s", data)
            return None
        except Exception as exc:
            logger.error("Failed to create Jellyfin playlist '%s': %s", title, exc)
            return None

    async def update_playlist(self, playlist_id: str, items: list[dict[str, Any]]) -> bool:
        try:
            current = await self.get_items_in_playlist(playlist_id)
            existing_ids = [str(i.get("item_id")) for i in current if i.get("item_id")]
            if existing_ids:
                await self.remove_items_from_playlist(playlist_id, existing_ids)

            desired_ids = [str(i.get("item_id") or i.get("id") or "") for i in items]
            desired_ids = [i for i in desired_ids if i]
            if desired_ids:
                await self.add_items_to_playlist(playlist_id, desired_ids)
            return True
        except Exception as exc:
            logger.error("Failed updating Jellyfin playlist %s: %s", playlist_id, exc)
            return False

    async def delete_playlist(self, playlist_id: str) -> bool:
        try:
            resp = await self.client.delete(f"/Items/{playlist_id}")
            resp.raise_for_status()
            return True
        except Exception as exc:
            logger.error("Failed deleting Jellyfin playlist %s: %s", playlist_id, exc)
            return False

    async def get_items_in_playlist(self, playlist_id: str) -> list[dict[str, Any]]:
        try:
            resp = await self.client.get(
                f"/Playlists/{playlist_id}/Items",
                params={
                    "UserId": self._user_id,
                    "Limit": "1000",
                    "Fields": "RunTimeTicks,ArtistItems,Album,PlaylistItemId",
                },
            )
            resp.raise_for_status()
            items = resp.json().get("Items", [])
            return [self._track_out(item) for item in items]
        except Exception as exc:
            logger.error("Failed to list Jellyfin playlist items for %s: %s", playlist_id, exc)
            return []

    # ── Playlist lookup ──────────────────────────────────────────

    async def get_playlist_by_name(self, name: str) -> dict[str, Any] | None:
        results = await self.search_playlists(name)
        target = name.lower().strip()
        for playlist in results:
            if str(playlist.get("title", "")).lower().strip() == target:
                return playlist
        return None

    async def get_playlist_by_source_id(self, source_id: str) -> dict[str, Any] | None:
        del source_id
        return None

    # ── Item management ──────────────────────────────────────────

    async def add_items_to_playlist(self, playlist_id: str, item_ids: list[str]) -> int:
        if not item_ids:
            return 0
        ids = [str(i) for i in item_ids if i]
        try:
            resp = await self.client.post(
                f"/Playlists/{playlist_id}/Items",
                params={
                    "UserId": self._user_id,
                    "Ids": ",".join(ids),
                },
            )
            resp.raise_for_status()
            return len(ids)
        except Exception as exc:
            logger.error("Failed adding items to Jellyfin playlist %s: %s", playlist_id, exc)
            return 0

    async def remove_items_from_playlist(self, playlist_id: str, item_ids: list[str]) -> int:
        if not item_ids:
            return 0
        items = await self.get_items_in_playlist(playlist_id)
        remove_set = {str(i) for i in item_ids}
        entry_ids = [
            str(item.get("playlist_item_id"))
            for item in items
            if str(item.get("item_id")) in remove_set and item.get("playlist_item_id")
        ]
        if not entry_ids:
            return 0
        try:
            resp = await self.client.delete(
                f"/Playlists/{playlist_id}/Items",
                params={
                    "UserId": self._user_id,
                    "EntryIds": ",".join(entry_ids),
                },
            )
            resp.raise_for_status()
            return len(entry_ids)
        except Exception as exc:
            logger.error("Failed removing items from Jellyfin playlist %s: %s", playlist_id, exc)
            return 0

    # ── Library search ───────────────────────────────────────────

    async def search_library(
        self,
        title: str = "",
        artist: str = "",
        genre: str = "",
        album: str = "",
    ) -> list[dict[str, Any]]:
        search_term = title or artist or album or genre
        search_term = _normalize_search_query(search_term) if search_term else ""
        params = {
            "IncludeItemTypes": "Audio",
            "Recursive": "true",
            "Limit": "200",
            "Fields": "RunTimeTicks,ArtistItems,Album",
        }
        if search_term:
            params["SearchTerm"] = search_term

        try:
            resp = await self.client.get(f"/Users/{self._user_id}/Items", params=params)
            resp.raise_for_status()
            items = [self._track_out(item) for item in resp.json().get("Items", [])]
        except Exception as exc:
            logger.error("Failed searching Jellyfin library: %s", exc)
            return []

        n_title = normalize(title)
        n_artist = normalize(artist)
        n_album = normalize(album)

        def _matches(item: dict[str, Any]) -> bool:
            if n_title and n_title not in normalize(str(item.get("title", ""))):
                return False
            if n_artist and n_artist not in normalize(str(item.get("artist_name", ""))):
                return False
            return not (n_album and n_album not in normalize(str(item.get("album_name", ""))))

        return [i for i in items if _matches(i)]

    async def search_artist_tracks(self, artist: str, genre: str = "") -> list[dict[str, Any]]:
        return await self.search_library(artist=artist, genre=genre)

    async def search_title_only(self, title: str) -> list[dict[str, Any]]:
        return await self.search_library(title=title)

    # ── Connection test ─────────────────────────────────────────

    async def test_connection(self) -> None:
        """Verify connectivity with the Jellyfin server."""
        resp = await self.client.get(f"/Users/{self._user_id}")
        resp.raise_for_status()

    # ── Lifecycle ────────────────────────────────────────────────

    async def close(self) -> None:
        if self._client is not None:
            await self._client.aclose()
            self._client = None
            self._client_loop_id = None


async def _create_jellyfin_target() -> JellyfinTarget:
    """Factory: build a JellyfinTarget from DB config."""
    from sqlalchemy import select

    from src.app.db import SessionLocal
    from src.app.models import Config

    db = SessionLocal()
    try:
        result = db.execute(
            select(Config).where(
                Config.key.in_(["jellyfin_server_url", "jellyfin_api_key", "jellyfin_user_id"])
            )
        )
        rows = {row.key: row.value for row in result.scalars().all()}
    finally:
        db.close()

    server_url = rows.get("jellyfin_server_url", "").strip()
    api_key = rows.get("jellyfin_api_key", "").strip()
    user_id = rows.get("jellyfin_user_id", "").strip()

    if not server_url or not api_key or not user_id:
        raise RuntimeError(
            "Jellyfin target not configured. Set jellyfin_server_url, jellyfin_api_key, "
            "and jellyfin_user_id in Settings."
        )

    return JellyfinTarget(api_key=api_key, base_url=server_url, user_id=user_id)


TargetRegistry.register(TARGET_JELLYFIN, JellyfinTarget, factory=_create_jellyfin_target)
