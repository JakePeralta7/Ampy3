"""HTTP client for Jellyfin playlist and library operations."""

from __future__ import annotations

import logging
from typing import Any

import httpx

from src.app.core.matching import normalize

logger = logging.getLogger(__name__)


class JellyfinClient:
    def __init__(self, api_key: str, base_url: str, user_id: str):
        self._api_key = api_key
        self._base_url = base_url.rstrip("/")
        self._user_id = user_id
        self.client = httpx.AsyncClient(base_url=self._base_url, timeout=15.0)
        self.client.headers.update(
            {
                "X-Emby-Token": self._api_key,
                "Content-Type": "application/json",
            }
        )

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

    @staticmethod
    def _playlist_out(item: dict[str, Any]) -> dict[str, Any]:
        pid = str(item.get("Id", ""))
        return {
            "title": item.get("Name", ""),
            "rating_key": pid,
            "playlist_id": pid,
            "summary": item.get("Overview", "") or "",
            "track_count": int(item.get("ChildCount") or 0),
        }

    @staticmethod
    def _track_out(item: dict[str, Any]) -> dict[str, Any]:
        item_id = str(item.get("Id", ""))
        return {
            "plex_id": item_id,
            "title": item.get("Name", "") or "",
            "artist_name": JellyfinClient._pick_artist(item),
            "album_name": item.get("Album", "") or "",
            "duration": JellyfinClient._to_duration_seconds(item.get("RunTimeTicks")),
            "duration_ms": int((item.get("RunTimeTicks") or 0) / 10_000),
            "playlist_item_id": item.get("PlaylistItemId"),
        }

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
            resp = await self.client.get(
                f"/Playlists/{playlist_id}", params={"UserId": self._user_id}
            )
            resp.raise_for_status()
            item = resp.json()
            return self._playlist_out(item)
        except Exception as exc:
            logger.error("Failed to get Jellyfin playlist %s: %s", playlist_id, exc)
            return None

    async def create_plist_from_results(
        self,
        title: str,
        items: list[dict[str, Any]],
        custom_metadata: dict[str, Any] | None = None,
    ) -> str | None:
        del custom_metadata
        ids = [str(i.get("plex_id") or i.get("id") or "") for i in items]
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
            if str(item.get("plex_id")) in remove_set and item.get("playlist_item_id")
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

    async def update_plist_in_place(self, playlist_id: str, items: list[dict[str, Any]]) -> bool:
        try:
            current = await self.get_items_in_playlist(playlist_id)
            existing_ids = [str(i.get("plex_id")) for i in current if i.get("plex_id")]
            if existing_ids:
                await self.remove_items_from_playlist(playlist_id, existing_ids)

            desired_ids = [str(i.get("plex_id") or i.get("id") or "") for i in items]
            desired_ids = [i for i in desired_ids if i]
            if desired_ids:
                await self.add_items_to_playlist(playlist_id, desired_ids)
            return True
        except Exception as exc:
            logger.error("Failed updating Jellyfin playlist %s: %s", playlist_id, exc)
            return False

    async def delete_plist(self, playlist_id: str) -> bool:
        try:
            resp = await self.client.delete(f"/Items/{playlist_id}")
            resp.raise_for_status()
            return True
        except Exception as exc:
            logger.error("Failed deleting Jellyfin playlist %s: %s", playlist_id, exc)
            return False

    async def get_plist_by_name(self, name: str) -> dict[str, Any] | None:
        results = await self.search_playlists(name)
        target = name.lower().strip()
        for playlist in results:
            if str(playlist.get("title", "")).lower().strip() == target:
                return playlist
        return None

    async def get_library_playlist(self, source_id: str) -> dict[str, Any] | None:
        del source_id
        return None

    async def search_title_only(self, title: str) -> list[dict[str, Any]]:
        return await self.search_library(title=title)

    async def search_artist_tracks(self, artist: str, genre: str = "") -> list[dict[str, Any]]:
        return await self.search_library(artist=artist, genre=genre)

    async def search_library(
        self,
        title: str = "",
        artist: str = "",
        genre: str = "",
        album: str = "",
    ) -> list[dict[str, Any]]:
        search_term = title or artist or album or genre
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
        n_genre = normalize(genre)

        def _matches(item: dict[str, Any]) -> bool:
            if n_title and n_title not in normalize(str(item.get("title", ""))):
                return False
            if n_artist and n_artist not in normalize(str(item.get("artist_name", ""))):
                return False
            if n_album and n_album not in normalize(str(item.get("album_name", ""))):
                return False
            if n_genre:
                return True
            return True

        return [i for i in items if _matches(i)]

    async def close(self) -> None:
        await self.client.aclose()
