"""Plex Media Server sync target."""

from __future__ import annotations

import json
import logging
import re
import urllib.parse
import xml.etree.ElementTree as ET
from typing import Any, ClassVar

import httpx

from src.app.constants import TARGET_PLEX
from src.app.core.matching import (
    _best_match,
    _extract_primary_artist,
    _normalize_album,
    normalize,
)
from src.app.core.targets.base import BaseTarget
from src.app.core.targets.registry import TargetRegistry

logger = logging.getLogger(__name__)


def _normalize_for_compare(text: str) -> str:
    """Normalize a string for quote-insensitive comparison.

    Plex stores artist names with curly quotes (U+2018/2019) while YTMusic
    sends straight quotes (U+0027).  This strips all quote characters so
    comparisons succeed regardless of the Unicode code point used.
    """
    return normalize(text, strip_quotes=True)


def _normalize_search_query(query: str) -> str:
    """Strip characters that cause Plex search API issues."""
    query = re.sub(r"\(.*?\)", "", query)
    query = re.sub(r"\[.*?\]", "", query)
    query = re.sub(r"\{.*?\}", "", query)
    query = re.sub(r"[(){}\[\]]", "", query)
    query = re.sub(r"\.{2,}", " ", query)
    query = query.replace(",", " ")
    return normalize(query, strip_quotes=True, collapse_whitespace=True)


class PlexTarget(BaseTarget):
    """Plex Media Server sync target."""

    target_id: ClassVar[str] = TARGET_PLEX
    display_name: ClassVar[str] = TARGET_PLEX

    def __init__(self, token: str, base_url: str) -> None:
        self._token = token
        self._base_url = base_url
        self._client: httpx.AsyncClient | None = None
        self._client_loop_id: int | None = None
        self._machine_identifier: str | None = None

    @property
    def client(self) -> httpx.AsyncClient:
        """Return an httpx.AsyncClient bound to the current event loop.

        Celery workers create a fresh event loop per task via ``_run_async``.
        A client created in a previous loop raises ``Event loop is closed``
        when reused, so we recreate it whenever the loop identity changes.
        """
        import asyncio

        try:
            loop = asyncio.get_running_loop()
            loop_id = id(loop)
        except RuntimeError:
            loop_id = None

        if self._client is not None and self._client_loop_id == loop_id:
            return self._client

        self._client = httpx.AsyncClient(base_url=self._base_url, timeout=10.0)
        self._client.headers.update(
            {
                "X-Plex-Token": self._token,
                "Content-Type": "application/json",
            }
        )
        self._client_loop_id = loop_id
        return self._client

    async def _ensure_machine_id(self) -> str:
        """Lazily fetches and caches the Plex server machine identifier."""
        if self._machine_identifier:
            return self._machine_identifier
        response = await self.client.get("/")
        response.raise_for_status()
        root = ET.fromstring(response.text)
        self._machine_identifier = root.get("machineIdentifier", "")
        if not self._machine_identifier:
            raise RuntimeError("Could not determine Plex server machine identifier")
        return self._machine_identifier

    @staticmethod
    def _rating_key(item_id: str) -> str:
        """Extracts the numeric rating_key from an item_id.

        Accepts either '/library/metadata/97300' or bare '97300'.
        """
        if item_id.startswith("/library/metadata/"):
            return item_id.split("/")[-1]
        if item_id.startswith("/"):
            return item_id.rsplit("/", 1)[-1]
        return item_id

    # ── Library sections ─────────────────────────────────────────

    async def get_sections(self) -> list[dict[str, Any]]:
        """Lists all library sections available in Plex."""
        try:
            response = await self.client.get("/library/sections")
            response.raise_for_status()
            root = ET.fromstring(response.text)
            sections = []
            for dir_elem in root.findall(".//Directory"):
                sections.append(
                    {
                        "key": dir_elem.get("key"),
                        "title": dir_elem.get("title"),
                        "type": dir_elem.get("type"),
                        "agent": dir_elem.get("agent"),
                    }
                )
            return sections
        except httpx.HTTPStatusError as e:
            logger.error(f"HTTP error getting sections: {e}")
            return []
        except ET.ParseError as e:
            logger.error(f"XML parse error in get_sections: {e}")
            return []

    # ── Playlist operations ──────────────────────────────────────

    async def search_playlists(self, query: str) -> list[dict[str, Any]]:
        """Searches for playlists matching a title or description."""
        try:
            response = await self.client.get("/playlists")
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

            logger.debug(f"Found {len(results)} playlists matching query: {query or '*'}")
            return results
        except httpx.HTTPStatusError as e:
            logger.error(f"HTTP error searching playlists: {e}")
            return []
        except httpx.RequestError as e:
            logger.error(f"Request error searching playlists (timeout/connection): {e}")
            return []
        except ET.ParseError as e:
            logger.error(f"XML parse error in search_playlists: {e}")
            return []

    async def get_playlist_details(self, playlist_id: str) -> dict[str, Any] | None:
        """Gets full details for a specific playlist."""
        try:
            response = await self.client.get(f"/playlists/{playlist_id}")
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
            logger.warning("HTTP error getting playlist %s: %s", playlist_id, e)
            return None

    async def create_playlist(
        self,
        title: str,
        items: list[dict[str, Any]],
        custom_metadata: dict[str, Any] | None = None,
    ) -> str | None:
        """Creates a new Plex playlist and adds matched tracks to it.

        Creates the playlist with all items in a single request by passing
        multiple uri parameters. Plex API requires at least one uri, and
        rejects Content-Type: application/json.

        Args:
            title: Playlist title
            items: List of dicts with item_id and other track metadata
            custom_metadata: Custom metadata to store in summary
                (e.g., {"source_playlist_id": "..."})

        Returns:
            Newly created playlist ID (rating_key) or None on failure
        """
        try:
            mi = await self._ensure_machine_id()
            params = [
                ("title", title),
                ("type", "audio"),
                ("smart", "0"),
            ]
            if custom_metadata:
                params.append(("summary", json.dumps(custom_metadata)))

            if items:
                key = self._rating_key(items[0].get("item_id", ""))
                if key:
                    params.append(
                        ("uri", f"server://{mi}/com.plexapp.plugins.library/library/metadata/{key}")
                    )

            qs = "&".join(f"{k}={urllib.parse.quote(str(v))}" for k, v in params)
            request = self.client.build_request("POST", f"/playlists?{qs}")
            request.headers.pop("Content-Type", None)
            response = await self.client.send(request)
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
            logger.info(f"Created playlist '{title}' with ID: {playlist_id}")

            remaining = [item["item_id"] for item in items[1:] if item.get("item_id")]
            if remaining:
                await self.add_items_to_playlist(playlist_id, remaining)

            return playlist_id
        except httpx.HTTPStatusError as e:
            logger.error(f"HTTP error creating playlist: {e}")
            return None
        except ET.ParseError as e:
            logger.error(f"XML parse error in create_playlist: {e}")
            return None

    async def update_playlist(self, playlist_id: str, items: list[dict[str, Any]]) -> bool:
        """Update playlist items in place while preserving its Plex ID.

        Computes a diff between current and desired items to minimize API calls.
        Only removes stale tracks and adds new ones. If the remaining tracks are
        in the correct relative order and new tracks can be appended, skips the
        full reorder. Otherwise falls back to a full replace for correct ordering.
        """
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
                await self.remove_items_from_playlist(playlist_id, to_remove)

            to_remove_set = set(to_remove)
            remaining_ids = [pid for pid in current_ids if pid not in to_remove_set]

            needs_reorder = self._playlist_needs_reorder(remaining_ids, to_add_ids, desired_ids)

            if needs_reorder:
                if remaining_ids:
                    await self.remove_items_from_playlist(playlist_id, remaining_ids)
                if desired_ids:
                    await self.add_items_to_playlist(playlist_id, desired_ids)
                logger.info(f"Reordered playlist {playlist_id}: {len(desired_ids)} items")
            else:
                if to_add_ids:
                    await self.add_items_to_playlist(playlist_id, to_add_ids)
                logger.info(
                    "Updated playlist %s: removed %d, added %d",
                    playlist_id,
                    len(to_remove),
                    len(to_add_ids),
                )

            return True
        except Exception as e:
            logger.error(f"Failed to update playlist {playlist_id} in place: {e}")
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
            response = await self.client.delete(f"/playlists/{playlist_id}")
            response.raise_for_status()
            logger.info(f"Successfully deleted playlist {playlist_id}")
            return True
        except httpx.HTTPStatusError as e:
            logger.error(f"HTTP error deleting playlist {playlist_id}: {e}")
            return False

    async def get_items_in_playlist(self, playlist_id: str) -> list[dict[str, Any]]:
        """Retrieves all individual items within a given playlist with pagination."""
        items = []
        offset = 0
        limit = 500

        try:
            while True:
                url = f"/playlists/{playlist_id}/items?limit={limit}&offset={offset}"
                response = await self.client.get(url)
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

            logger.debug(f"Playlist {playlist_id}: Total items retrieved: {len(items)}")
            return items
        except httpx.HTTPStatusError as e:
            logger.error(f"HTTP error getting items in playlist {playlist_id}: {e}")
            return []

    # ── Playlist lookup ──────────────────────────────────────────

    async def get_playlist_by_name(self, name: str) -> dict[str, Any] | None:
        """Find a playlist by exact (case-insensitive) name match."""
        playlists = await self.search_playlists(name)
        for pl in playlists:
            if pl["title"].lower() == name.lower():
                return pl
        return None

    async def get_playlist_by_source_id(self, source_id: str) -> dict[str, Any] | None:
        """Retrieves a playlist by source_id stored in custom metadata."""
        try:
            response = await self.client.get("/playlists")
            response.raise_for_status()

            root = ET.fromstring(response.text)
            for playlist in root.findall(".//Playlist"):
                summary = playlist.get("summary", "")
                if source_id in summary:
                    return {
                        "rating_key": playlist.get("ratingKey"),
                        "title": playlist.get("title"),
                        "summary": summary,
                    }

            logger.debug(f"No playlist found with source_id: {source_id}")
            return None
        except httpx.HTTPStatusError as e:
            logger.error(f"HTTP error getting library playlist: {e}")
            return None
        except ET.ParseError as e:
            logger.error(f"XML parse error in get_playlist_by_source_id: {e}")
            return None

    # ── Item management ──────────────────────────────────────────

    async def add_items_to_playlist(self, playlist_id: str, item_ids: list[str]) -> int:
        """Adds tracks to a playlist one at a time to avoid URL length issues."""
        if not item_ids:
            return 0

        mi = await self._ensure_machine_id()
        added_count = 0

        for i, raw_id in enumerate(item_ids):
            uri = f"server://{mi}/com.plexapp.plugins.library/library/metadata/{self._rating_key(raw_id)}"
            params = {"uri": uri}
            try:
                response = await self.client.put(f"/playlists/{playlist_id}/items", params=params)
                response.raise_for_status()
                added_count += 1
                logger.debug(
                    "Added item %d/%d to playlist %s",
                    i + 1,
                    len(item_ids),
                    playlist_id,
                )
            except httpx.HTTPStatusError as e:
                logger.warning(
                    "Failed to add item %d to playlist %s: %s",
                    i + 1,
                    playlist_id,
                    e,
                )

        return added_count

    async def remove_items_from_playlist(self, playlist_id: str, item_ids: list[str]) -> int:
        """Removes tracks from a playlist one at a time to avoid URL length issues."""
        if not item_ids:
            return 0

        mi = await self._ensure_machine_id()
        removed_count = 0

        for i, raw_id in enumerate(item_ids):
            uri = f"server://{mi}/com.plexapp.plugins.library/library/metadata/{self._rating_key(raw_id)}"
            params = {"uri": uri}
            try:
                response = await self.client.delete(
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
                logger.warning(
                    "Failed to remove item %d from playlist %s: %s",
                    i + 1,
                    playlist_id,
                    e,
                )

        return removed_count

    # ── Library search ───────────────────────────────────────────

    async def _expand_artists(
        self, dirs: list[ET.Element], genre: str = ""
    ) -> list[dict[str, Any]]:
        """Expands Directory (artist) entries into their tracks via allLeaves."""
        results = []
        for d in dirs:
            artist_name = d.get("title", "")
            artist_key = d.get("key", "")
            leaf_key = artist_key.replace("/children", "/allLeaves")
            try:
                leaf_resp = await self.client.get(leaf_key)
                leaf_resp.raise_for_status()
                leaf_root = ET.fromstring(leaf_resp.text)
                for track in leaf_root.findall(".//Track"):
                    duration_ms = int(track.get("duration", 0))
                    results.append(
                        {
                            "item_id": track.get("key"),
                            "title": track.get("title"),
                            "artist_name": track.get("grandparentTitle") or artist_name,
                            "album_name": track.get("parentTitle") or "",
                            "duration_ms": duration_ms,
                            "track_number": (
                                int(track.get("index", 0)) if track.get("index") else None
                            ),
                            "genre": genre or None,
                        }
                    )
            except Exception as e:
                logger.warning(f"Failed to fetch tracks for artist {artist_name}: {e}")
        return results

    async def search_artist_tracks(self, artist: str, genre: str = "") -> list[dict[str, Any]]:
        """Search Plex for an artist directory and expand all their tracks."""
        query = _normalize_search_query(artist)
        if not query:
            return []
        params = {"query": query, "limit": "50"}
        artist_resp = await self.client.get("/search", params=params)
        artist_resp.raise_for_status()
        artist_root = ET.fromstring(artist_resp.text)
        dirs = artist_root.findall(".//Directory")
        if not dirs:
            words = query.split()
            if len(words) > 1:
                fallback_query = words[0]
                params = {"query": fallback_query, "limit": "50"}
                artist_resp = await self.client.get("/search", params=params)
                artist_resp.raise_for_status()
                artist_root = ET.fromstring(artist_resp.text)
                dirs = artist_root.findall(".//Directory")
            if not dirs:
                return []
        return await self._expand_artists(dirs, genre)

    async def search_title_only(self, title: str) -> list[dict[str, Any]]:
        """Direct Plex track search by title only."""
        query = _normalize_search_query(title)
        if not query:
            return []
        params = {"query": query, "limit": "100"}
        response = await self.client.get("/hubs/search", params=params)
        response.raise_for_status()
        root = ET.fromstring(response.text)
        tracks = root.findall(".//Track")
        return self._parse_tracks(tracks) if tracks else []

    async def search_library(
        self,
        title: str = "",
        artist: str = "",
        genre: str = "",
        album: str = "",
    ) -> list[dict[str, Any]]:
        """Searches the Plex music library for tracks matching the criteria."""
        try:
            if genre and not title and not artist:
                response = await self.client.get(
                    "/library/all", params={"type": "8", "genre": genre}
                )
                response.raise_for_status()
                root = ET.fromstring(response.text)
                dirs = root.findall(".//Directory")
                results = []
                for d in dirs:
                    results.append(
                        {
                            "item_id": d.get("ratingKey"),
                            "title": f"[Artist] {d.get('title', '')}",
                            "artist_name": d.get("title", ""),
                            "album_name": "",
                            "duration_ms": 0,
                            "track_number": None,
                            "genre": genre,
                        }
                    )
                    logger.debug(f"Found {len(results)} artists matching genre '{genre}'")
                return results

            if title and artist:
                primary_artist = _extract_primary_artist(artist)
                log_msg = f"Searching for track by artist='{primary_artist}', title='{title}'"
                if album:
                    log_msg += f", album='{album}'"
                logger.debug(log_msg)

                result_tracks = await self.search_artist_tracks(primary_artist, genre)

                if result_tracks:
                    logger.debug(f"Expanded artist '{artist}' to {len(result_tracks)} tracks")

                    if album:
                        norm_album = _normalize_album(album)
                        album_tracks = [
                            t
                            for t in result_tracks
                            if _normalize_album(t.get("album_name", "")) == norm_album
                        ]
                        logger.debug(f"Found {len(album_tracks)} tracks in album '{album}'")
                        if album_tracks:
                            match = _best_match(title, album_tracks)
                            if match:
                                logger.debug(
                                    "Album match: '%s' -> '%s' in '%s'",
                                    title,
                                    match.get("title"),
                                    album,
                                )
                                return [match]

                    match = _best_match(title, result_tracks)
                    if match:
                        logger.debug(
                            "Matched '%s' -> '%s' by %s",
                            title,
                            match.get("title"),
                            match.get("artist_name", ""),
                        )
                        return [match]

                    logger.debug(f"No match found for '{title}' by '{artist}'")
                    return []

                logger.debug(
                    "Artist directory not found: '%s' - falling back to title-only search",
                    artist,
                )
                if title:
                    results = await self.search_title_only(title)
                    if results:
                        norm_artist = _normalize_for_compare(artist)
                        filtered = [
                            t
                            for t in results
                            if norm_artist in _normalize_for_compare(t.get("artist_name", ""))
                            or _normalize_for_compare(t.get("artist_name", "")) in norm_artist
                        ]
                        if filtered:
                            return filtered
                        logger.debug(
                            "No results matching artist '%s' in title-only fallback",
                            artist,
                        )
                        return []
                return []

            elif artist:
                logger.debug(f"Searching for artist='{artist}'")
                results = await self.search_artist_tracks(artist, genre)
                if results:
                    logger.debug(f"Found {len(results)} tracks for artist '{artist}'")
                    return results
                logger.debug(f"Artist not found: '{artist}'")
                return []

            elif title:
                logger.debug(f"Searching for title='{title}'")
                results = await self.search_title_only(title)
                if results:
                    logger.debug(f"Found {len(results)} tracks for title '{title}'")
                    return results
                logger.debug(f"No tracks found for title '{title}'")
                return []

            logger.debug("No search criteria provided")
            return []
        except httpx.HTTPStatusError as e:
            logger.warning(f"HTTP error searching library: {e}")
            return []
        except ET.ParseError as e:
            logger.error(f"XML parse error in search_library: {e}")
            return []

    def _parse_tracks(self, track_elements: list[ET.Element]) -> list[dict[str, Any]]:
        """Parses Track XML elements into dicts."""
        results = []
        for track in track_elements:
            duration_ms = int(track.get("duration", 0))
            results.append(
                {
                    "item_id": track.get("key"),
                    "title": track.get("title"),
                    "artist_name": track.get("grandparentTitle") or "",
                    "album_name": track.get("parentTitle") or "",
                    "duration_ms": duration_ms,
                    "track_number": int(track.get("index", 0)) if track.get("index") else None,
                }
            )
        return results

    # ── Connection test ─────────────────────────────────────────

    async def test_connection(self) -> None:
        """Verify connectivity with the Plex server."""
        resp = await self.client.get("/library/sections")
        resp.raise_for_status()

    # ── Lifecycle ────────────────────────────────────────────────

    async def close(self) -> None:
        """Closes the underlying httpx client session."""
        if self._client is not None:
            await self._client.aclose()
            self._client = None
            self._client_loop_id = None


async def _create_plex_target() -> PlexTarget:
    """Factory: build a PlexTarget from DB config."""
    from sqlalchemy import select

    from src.app.db import SessionLocal
    from src.app.models import Config

    db = SessionLocal()
    try:
        result = db.execute(select(Config).where(Config.key.in_(["plex_host", "plex_token"])))
        config = {row.key: row.value for row in result.scalars().all()}
    finally:
        db.close()

    token = config.get("plex_token", "").strip()
    server_url = config.get("plex_host", "").strip()

    if not token or not server_url:
        raise RuntimeError("Plex server not configured. Set up the server in Settings.")

    return PlexTarget(token=token, base_url=server_url)


TargetRegistry.register(TARGET_PLEX, PlexTarget, factory=_create_plex_target)
