"""Jellyfin playlist operations (CRUD, search, details)."""

import json
import logging
from typing import Any

import httpx

from src.app.core.targets.jellyfin.client import JellyfinClient
from src.app.core.targets.playlist_lookup import meta_from_summary
from src.app.core.urls import source_id_from_url

logger = logging.getLogger(__name__)


class JellyfinPlaylistManager:
    """Handles all playlist operations for Jellyfin."""

    def __init__(self, client: JellyfinClient) -> None:
        self._client = client

    async def client_url(self, playlist_id: str) -> str:
        """Return the Jellyfin web-app URL that opens the given playlist item."""
        return f"{self._client.base_url}/web/index.html#/details?id={playlist_id}"

    async def search_playlists(self, query: str) -> list[dict[str, Any]]:
        """Search for playlists matching a title or description."""
        try:
            items = await self._client._get_all_items(
                f"/Users/{self._client.user_id}/Items",
                {
                    "IncludeItemTypes": "Playlist",
                    "Recursive": "true",
                    "Fields": "ChildCount,Overview",
                    "SortBy": "SortName",
                },
            )
            out = [self._client._playlist_out(item) for item in items]
            if not query:
                return out
            q = query.lower().strip()
            return [p for p in out if q in str(p.get("title", "")).lower()]
        except Exception as exc:
            logger.error("Failed to search Jellyfin playlists: %s", exc)
            return []

    async def get_playlist_details(self, playlist_id: str) -> dict[str, Any] | None:
        """Gets full details for a specific playlist."""
        try:
            resp = await self._client.client.get(
                f"/Users/{self._client.user_id}/Items/{playlist_id}"
            )
            resp.raise_for_status()
            item = resp.json()
            return self._client._playlist_out(item)
        except Exception as exc:
            logger.error("Failed to get Jellyfin playlist %s: %s", playlist_id, exc)
            return None

    async def create_playlist(
        self,
        title: str,
        items: list[dict[str, Any]],
        custom_metadata: dict[str, Any] | None = None,
    ) -> str | None:
        """Creates a new Jellyfin playlist and adds matched tracks to it."""
        ids = [str(i.get("item_id") or i.get("id") or "") for i in items]
        ids = [i for i in ids if i]
        try:
            params = {
                "Name": title,
                "UserId": self._client.user_id,
                "MediaType": "Audio",
            }
            if ids:
                params["Ids"] = ",".join(ids)
            resp = await self._client.client.post("/Playlists", params=params)
            resp.raise_for_status()
            data = resp.json()
            playlist_id = data.get("Id")
            if (not isinstance(playlist_id, str) or not playlist_id) and isinstance(
                data.get("ItemId"), str
            ):
                playlist_id = data["ItemId"]
            if not isinstance(playlist_id, str) or not playlist_id:
                logger.error("Jellyfin playlist creation response missing Id: %s", data)
                return None

            # CreatePlaylistDto has no Overview field: write metadata via a
            # follow-up item update so get_playlist_by_source_id can locate
            # this playlist by its source identity later.
            if custom_metadata:
                try:
                    meta_resp = await self._client.client.post(
                        f"/Items/{playlist_id}",
                        json={"Overview": json.dumps(custom_metadata, default=str)},
                    )
                    meta_resp.raise_for_status()
                except Exception as exc:
                    logger.warning(
                        "Created Jellyfin playlist %s but failed to store metadata: %s",
                        playlist_id,
                        exc,
                    )

            return playlist_id
        except Exception as exc:
            logger.error("Failed to create Jellyfin playlist '%s': %s", title, exc)
            return None

    async def update_playlist(self, playlist_id: str, items: list[dict[str, Any]]) -> bool:
        """Update playlist items in place while preserving its Jellyfin ID."""
        try:
            current = await self.get_items_in_playlist(playlist_id)
            existing_ids = [str(i.get("item_id")) for i in current if i.get("item_id")]
            if existing_ids:
                removed = await self.remove_items_from_playlist(playlist_id, existing_ids)
                if removed < len(existing_ids):
                    logger.error(
                        "Jellyfin playlist %s: only removed %d/%d stale items",
                        playlist_id,
                        removed,
                        len(existing_ids),
                    )
                    return False

            desired_ids = [str(i.get("item_id") or i.get("id") or "") for i in items]
            desired_ids = [i for i in desired_ids if i]
            if desired_ids:
                added = await self.add_items_to_playlist(playlist_id, desired_ids)
                if added < len(desired_ids):
                    logger.error(
                        "Jellyfin playlist %s: only added %d/%d desired items",
                        playlist_id,
                        added,
                        len(desired_ids),
                    )
                    return False
            return True
        except Exception as exc:
            logger.error("Failed updating Jellyfin playlist %s: %s", playlist_id, exc)
            return False

    async def delete_playlist(self, playlist_id: str) -> bool:
        """Deletes a playlist from Jellyfin."""
        try:
            resp = await self._client.client.delete(f"/Items/{playlist_id}")
            resp.raise_for_status()
            return True
        except Exception as exc:
            logger.error("Failed deleting Jellyfin playlist %s: %s", playlist_id, exc)
            return False

    async def get_items_in_playlist(self, playlist_id: str) -> list[dict[str, Any]]:
        """Retrieves all individual items within a given playlist with pagination."""
        try:
            items = await self._client._get_all_items(
                f"/Playlists/{playlist_id}/Items",
                {
                    "UserId": self._client.user_id,
                    "Fields": "RunTimeTicks,ArtistItems,Album,PlaylistItemId",
                },
            )
            return [self._client._track_out(item) for item in items]
        except Exception as exc:
            logger.error("Failed to list Jellyfin playlist items for %s: %s", playlist_id, exc)
            return []

    @staticmethod
    def _meta_from_overview(playlist: dict[str, Any]) -> dict[str, Any]:
        return meta_from_summary(str(playlist.get("summary") or ""))

    @staticmethod
    def _source_id_from_url(url: str) -> str:
        return source_id_from_url(url)

    # ── Item management ──────────────────────────────────────────

    async def add_items_to_playlist(self, playlist_id: str, item_ids: list[str]) -> int:
        """Adds tracks to a playlist."""
        if not item_ids:
            return 0
        ids = [str(i) for i in item_ids if i]
        try:
            resp = await self._client.client.post(
                f"/Playlists/{playlist_id}/Items",
                params={
                    "UserId": self._client.user_id,
                    "Ids": ",".join(ids),
                },
            )
            resp.raise_for_status()
            return len(ids)
        except Exception as exc:
            logger.error("Failed adding items to Jellyfin playlist %s: %s", playlist_id, exc)
            return 0

    async def remove_items_from_playlist(self, playlist_id: str, item_ids: list[str]) -> int:
        """Removes tracks from a playlist."""
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
            resp = await self._client.client.delete(
                f"/Playlists/{playlist_id}/Items",
                params={
                    "UserId": self._client.user_id,
                    "EntryIds": ",".join(entry_ids),
                },
            )
            resp.raise_for_status()
            return len(entry_ids)
        except Exception as exc:
            logger.error("Failed removing items from Jellyfin playlist %s: %s", playlist_id, exc)
            return 0
