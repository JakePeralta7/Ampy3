"""Plex playlist operations (CRUD, search, details)."""

import json
import logging
import urllib.parse
import xml.etree.ElementTree as ET
from typing import Any

import httpx

from src.app.core.targets.plex.client import PlexClient

logger = logging.getLogger(__name__)


class PlexPlaylistManager:
    """Handles all playlist operations for Plex."""

    def __init__(self, client: PlexClient) -> None:
        self._client = client

    async def client_url(self, playlist_id: str) -> str:
        """Return the Plex web-app URL that opens the given playlist."""
        machine_id = await self._client._ensure_machine_id()
        rating_key = self._client._rating_key(playlist_id)
        key_param = urllib.parse.quote(f"/playlists/{rating_key}", safe="")
        return (
            f"{self._client.base_url.rstrip('/')}/web/index.html"
            f"#!/server/{machine_id}/playlist?key={key_param}"
        )

    async def search_playlists(self, query: str) -> list[dict[str, Any]]:
        """Searches for playlists matching a title or description."""
        try:
            response = await self._client.client.get("/playlists")
            response.raise_for_status()

            root = ET.fromstring(response.text)
            results = []
            for pl in root.findall(".//Playlist"):
                title = pl.get("title", "")
                if not query or query.lower() in title.lower():
                    results.append(
                        {
                            "title": title,
                            "rating_key": pl.get("ratingKey"),
                            "playlist_id": pl.get("ratingKey"),
                            "summary": pl.get("summary", ""),
                            "track_count": int(pl.get("leafCount", 0)),
                        }
                    )

            logger.debug("Found %d playlists matching query: %s", len(results), query or "*")
            return results
        except httpx.HTTPStatusError as e:
            self._client._log_plex_error("search_playlists", e)
            return []
        except httpx.RequestError as e:
            self._client._log_plex_error("search_playlists", e)
            return []
        except ET.ParseError as e:
            logger.error("XML parse error in search_playlists: %s", e)
            return []

    async def get_playlist_details(self, playlist_id: str) -> dict[str, Any] | None:
        """Gets full details for a specific playlist."""
        try:
            response = await self._client.client.get(f"/playlists/{playlist_id}")
            response.raise_for_status()
            root = ET.fromstring(response.text)
            playlist = root.find("Playlist")
            if playlist is None:
                return None
            return playlist.attrib
        except ET.ParseError:
            logger.warning("Failed to parse playlist details XML for %s", playlist_id)
            return None
        except httpx.HTTPStatusError as e:
            self._client._log_plex_error(f"get_playlist_details({playlist_id})", e)
            return None

    async def create_playlist(
        self,
        title: str,
        items: list[dict[str, Any]],
        custom_metadata: dict[str, Any] | None = None,
    ) -> str | None:
        """Creates a new Plex playlist and adds matched tracks to it."""
        try:
            mi = await self._client._ensure_machine_id()
            params = [
                ("title", title),
                ("type", "audio"),
                ("smart", "0"),
            ]
            if custom_metadata:
                params.append(("summary", json.dumps(custom_metadata)))

            if items:
                key = self._client._rating_key(items[0].get("item_id", ""))
                if key:
                    params.append(
                        ("uri", f"server://{mi}/com.plexapp.plugins.library/library/metadata/{key}")
                    )

            qs = "&".join(f"{k}={urllib.parse.quote(str(v))}" for k, v in params)
            request = self._client.client.build_request("POST", f"/playlists?{qs}")
            request.headers.pop("Content-Type", None)
            response = await self._client.client.send(request)
            response.raise_for_status()

            root = ET.fromstring(response.text)
            playlist = root.find(".//Playlist")
            if playlist is None:
                logger.error("No playlist in response after creation")
                return None

            playlist_id = playlist.get("ratingKey")
            if playlist_id is None:
                logger.error("Created playlist has no ratingKey")
                return None
            logger.info("Created playlist '%s' with ID: %s", title, playlist_id)

            remaining = [item["item_id"] for item in items[1:] if item.get("item_id")]
            if remaining:
                await self.add_items_to_playlist(playlist_id, remaining)

            return playlist_id
        except httpx.HTTPStatusError as e:
            self._client._log_plex_error("create_playlist", e)
            return None
        except ET.ParseError as e:
            logger.error("XML parse error in create_playlist: %s", e)
            return None

    async def update_playlist(self, playlist_id: str, items: list[dict[str, Any]]) -> bool:
        """Update playlist items in place while preserving its Plex ID."""
        try:
            current_items = await self.get_items_in_playlist(playlist_id)
            current_ids = [item["item_id"] for item in current_items if item.get("item_id")]
            desired_ids = [item["item_id"] for item in items if item.get("item_id")]

            if current_ids == desired_ids:
                logger.debug(
                    "Playlist %s already up to date (%d items)",
                    playlist_id,
                    len(current_ids),
                )
                return True

            current_set = set(current_ids)
            desired_set = set(desired_ids)

            to_remove = [pid for pid in current_ids if pid not in desired_set]
            to_add_ids = [pid for pid in desired_ids if pid not in current_set]

            if to_remove:
                removed = await self.remove_items_from_playlist(playlist_id, to_remove)
                if removed < len(to_remove):
                    logger.error(
                        "Playlist %s: only removed %d/%d stale items",
                        playlist_id,
                        removed,
                        len(to_remove),
                    )
                    return False

            to_remove_set = set(to_remove)
            remaining_ids = [pid for pid in current_ids if pid not in to_remove_set]

            needs_reorder = self._playlist_needs_reorder(remaining_ids, to_add_ids, desired_ids)

            if needs_reorder:
                if remaining_ids:
                    removed = await self.remove_items_from_playlist(playlist_id, remaining_ids)
                    if removed < len(remaining_ids):
                        logger.error(
                            "Playlist %s: only removed %d/%d items during reorder",
                            playlist_id,
                            removed,
                            len(remaining_ids),
                        )
                        return False
                if desired_ids:
                    added = await self.add_items_to_playlist(playlist_id, desired_ids)
                    if added < len(desired_ids):
                        logger.error(
                            "Playlist %s: only added %d/%d items during reorder",
                            playlist_id,
                            added,
                            len(desired_ids),
                        )
                        return False
                logger.info("Reordered playlist %s: %d items", playlist_id, len(desired_ids))
            else:
                if to_add_ids:
                    added = await self.add_items_to_playlist(playlist_id, to_add_ids)
                    if added < len(to_add_ids):
                        logger.error(
                            "Playlist %s: only added %d/%d new items",
                            playlist_id,
                            added,
                            len(to_add_ids),
                        )
                        return False
                logger.info(
                    "Updated playlist %s: removed %d, added %d",
                    playlist_id,
                    len(to_remove),
                    len(to_add_ids),
                )

            return True
        except Exception as e:
            logger.error("Failed to update playlist %s in place: %s", playlist_id, e)
            return False

    @staticmethod
    def _playlist_needs_reorder(
        remaining_ids: list[str],
        to_add_ids: list[str],
        desired_ids: list[str],
    ) -> bool:
        """Check if the playlist needs a full reorder to match desired order."""
        if not remaining_ids:
            return False

        it = iter(desired_ids)
        for rid in remaining_ids:
            found = False
            for did in it:
                if did == rid:
                    found = True
                    break
            if not found:
                return True

        if to_add_ids:
            last_remaining_pos = max(desired_ids.index(rid) for rid in remaining_ids)
            for aid in to_add_ids:
                if desired_ids.index(aid) < last_remaining_pos:
                    return True

        return False

    async def delete_playlist(self, playlist_id: str) -> bool:
        """Deletes a playlist from Plex."""
        try:
            response = await self._client.client.delete(f"/playlists/{playlist_id}")
            response.raise_for_status()
            logger.info("Successfully deleted playlist %s", playlist_id)
            return True
        except httpx.HTTPStatusError as e:
            self._client._log_plex_error(f"delete_playlist({playlist_id})", e)
            return False

    async def get_items_in_playlist(self, playlist_id: str) -> list[dict[str, Any]]:
        """Retrieves all individual items within a given playlist with pagination."""
        items = []
        offset = 0
        limit = 500

        try:
            while True:
                url = f"/playlists/{playlist_id}/items?limit={limit}&offset={offset}"
                response = await self._client.client.get(url)
                response.raise_for_status()

                root = ET.fromstring(response.text)
                tracks = root.findall(".//Track")

                logger.debug(
                    "Playlist %s: Retrieved %d tracks at offset %d",
                    playlist_id,
                    len(tracks),
                    offset,
                )

                if not tracks:
                    logger.debug(
                        "Playlist %s: No more tracks at offset %s, stopping pagination",
                        playlist_id,
                        offset,
                    )
                    break

                for track in tracks:
                    artist_name = track.get("grandparentTitle", "")
                    raw_dur = track.get("duration", 0)
                    dur = int(raw_dur) // 1000 if track.get("duration") else 0
                    items.append(
                        {
                            "item_id": track.get("key"),
                            "title": track.get("title"),
                            "artist_name": artist_name,
                            "album_name": track.get("parentTitle"),
                            "duration": dur,
                        }
                    )

                if len(tracks) < limit:
                    logger.debug(
                        "Playlist %s: Got %d tracks (less than limit %s), stopping pagination",
                        playlist_id,
                        len(tracks),
                        limit,
                    )
                    break

                offset += limit

            logger.debug("Playlist %s: Total items retrieved: %d", playlist_id, len(items))
            return items
        except httpx.HTTPStatusError as e:
            self._client._log_plex_error(f"get_items_in_playlist({playlist_id})", e)
            return []

    async def add_items_to_playlist(self, playlist_id: str, item_ids: list[str]) -> int:
        """Adds tracks to a playlist one at a time to avoid URL length issues."""
        if not item_ids:
            return 0

        mi = await self._client._ensure_machine_id()
        added_count = 0

        for i, raw_id in enumerate(item_ids):
            uri = f"server://{mi}/com.plexapp.plugins.library/library/metadata/{self._client._rating_key(raw_id)}"
            params = {"uri": uri}
            try:
                response = await self._client.client.put(
                    f"/playlists/{playlist_id}/items", params=params
                )
                response.raise_for_status()
                added_count += 1
                logger.debug(
                    "Added item %d/%d to playlist %s",
                    i + 1,
                    len(item_ids),
                    playlist_id,
                )
            except httpx.HTTPStatusError as e:
                self._client._log_plex_error(f"add_items_to_playlist({playlist_id})", e)

        return added_count

    async def remove_items_from_playlist(self, playlist_id: str, item_ids: list[str]) -> int:
        """Removes tracks from a playlist one at a time to avoid URL length issues."""
        if not item_ids:
            return 0

        mi = await self._client._ensure_machine_id()
        removed_count = 0

        for i, raw_id in enumerate(item_ids):
            uri = f"server://{mi}/com.plexapp.plugins.library/library/metadata/{self._client._rating_key(raw_id)}"
            params = {"uri": uri}
            try:
                response = await self._client.client.delete(
                    f"/playlists/{playlist_id}/items", params=params
                )
                response.raise_for_status()
                removed_count += 1
                logger.debug(
                    "Removed item %d/%d from playlist %s",
                    i + 1,
                    len(item_ids),
                    playlist_id,
                )
            except httpx.HTTPStatusError as e:
                self._client._log_plex_error(f"remove_items_from_playlist({playlist_id})", e)

        return removed_count
