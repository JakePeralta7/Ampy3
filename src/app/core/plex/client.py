"""Handles all interaction with the Plex Media Server API."""
import logging
import re
import urllib.parse
import xml.etree.ElementTree as ET
from typing import Any

import httpx

from src.app.core.matching import _best_match, _extract_primary_artist, _normalize_album

logger = logging.getLogger(__name__)


def _normalize_for_compare(text: str) -> str:
    """Normalize a string for quote-insensitive comparison.

    Plex stores artist names with curly quotes (U+2018/2019) while YTMusic
    sends straight quotes (U+0027).  This strips all quote characters so
    comparisons succeed regardless of the Unicode code point used.
    """
    text = text.replace("\u2018", "'").replace("\u2019", "'")
    text = text.replace("\u201c", '"').replace("\u201d", '"')
    text = re.sub(r"['''`]", "", text)
    return text.lower().strip()


def _normalize_search_query(query: str) -> str:
    """Strip characters that cause Plex search API issues."""
    query = re.sub(r"\(.*?\)", "", query)   # remove parenthesized groups
    query = re.sub(r"\[.*?\]", "", query)   # remove bracketed groups
    query = re.sub(r"\{.*?\}", "", query)   # remove braced groups
    query = re.sub(r"[(){}\[\]]", "", query)  # remove stray parens/brackets
    query = re.sub(r"\.{2,}", " ", query)   # collapse ellipses
    # Replace commas with spaces — Plex search API returns no results for
    # comma-separated multi-artist queries like "Post Malone, Swae Lee".
    query = query.replace(",", " ")
    # Normalize Unicode quotes to straight equivalents.  Plex's search API
    # cannot match straight quotes (U+0027) against curly quotes (U+2018/19)
    # stored in its database.  Stripping all quotes avoids this mismatch.
    query = query.replace("\u2018", "'").replace("\u2019", "'")
    query = query.replace("\u201c", '"').replace("\u201d", '"')
    query = re.sub(r"['''`]", " ", query)   # strip all quote chars
    query = re.sub(r"\s{2,}", " ", query)   # collapse whitespace
    return query.strip()


class PlexClient:

    def __init__(self, token: str, base_url: str):
        self._token = token
        self._base_url = base_url
        self.client = httpx.AsyncClient(base_url=self._base_url, timeout=10.0)
        self.client.headers.update({
            "X-Plex-Token": self._token,
            "Content-Type": "application/json",
        })
        self._machine_identifier: str | None = None

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

    async def get_section(self, section_id: str) -> Any | None:
        """Retrieves a specific media library section (e.g., 'Playlists')."""
        try:
            response = await self.client.get(f"/sections/{section_id}")
            response.raise_for_status()
            return response.json()
        except httpx.HTTPStatusError as e:
            print(f"HTTP error getting section {section_id}: {e}")
            return None

    async def get_sections(self) -> list[dict]:
        """Lists all library sections available in Plex."""
        try:
            response = await self.client.get("/library/sections")
            response.raise_for_status()
            root = ET.fromstring(response.text)
            sections = []
            for dir_elem in root.findall(".//Directory"):
                sections.append({
                    "key": dir_elem.get("key"),
                    "title": dir_elem.get("title"),
                    "type": dir_elem.get("type"),
                    "agent": dir_elem.get("agent"),
                })
            return sections
        except httpx.HTTPStatusError as e:
            logger.error(f"HTTP error getting sections: {e}")
            return []
        except ET.ParseError as e:
            logger.error(f"XML parse error in get_sections: {e}")
            return []

    @staticmethod
    def _rating_key(plex_id: str) -> str:
        """Extracts the numeric rating_key from a plex_id.

        Accepts either '/library/metadata/97300' or bare '97300'.
        """
        if plex_id.startswith("/library/metadata/"):
            return plex_id.split("/")[-1]
        if plex_id.startswith("/"):
            return plex_id.rsplit("/", 1)[-1]
        return plex_id

    async def add_items_to_playlist(self, playlist_id: str, plex_ids: list[str]) -> int:
        """Adds tracks to a playlist one at a time to avoid URL length issues.

        Args:
            playlist_id: The playlist rating_key
            plex_ids: List of Plex track rating_keys to add

        Returns:
            Number of successfully added items
        """
        if not plex_ids:
            return 0

        mi = await self._ensure_machine_id()
        added_count = 0

        for i, raw_id in enumerate(plex_ids):
            uri = f"server://{mi}/com.plexapp.plugins.library/library/metadata/{self._rating_key(raw_id)}"
            params = [("uri", uri)]
            try:
                response = await self.client.put(f"/playlists/{playlist_id}/items", params=params)
                response.raise_for_status()
                added_count += 1
                logger.debug(
                    "Added item %d/%d to playlist %s",
                    i + 1,
                    len(plex_ids),
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

    async def remove_items_from_playlist(self, playlist_id: str, plex_ids: list[str]) -> int:
        """Removes tracks from a playlist one at a time to avoid URL length issues.

        Args:
            playlist_id: The playlist rating_key
            plex_ids: List of Plex track rating_keys to remove

        Returns:
            Number of successfully removed items
        """
        if not plex_ids:
            return 0

        mi = await self._ensure_machine_id()
        removed_count = 0

        for i, raw_id in enumerate(plex_ids):
            uri = f"server://{mi}/com.plexapp.plugins.library/library/metadata/{self._rating_key(raw_id)}"
            params = [("uri", uri)]
            try:
                response = await self.client.delete(
                    f"/playlists/{playlist_id}/items", params=params
                )
                response.raise_for_status()
                removed_count += 1
                logger.debug(
                    "Removed item %d/%d from playlist %s",
                    i + 1,
                    len(plex_ids),
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

    async def search_playlists(self, query: str) -> list[dict]:
        """Searches for playlists matching a title or description."""
        try:
            response = await self.client.get("/playlists")
            response.raise_for_status()

            root = ET.fromstring(response.text)
            results = []
            for pl in root.findall(".//Playlist"):
                title = pl.get("title", "")
                if not query or query.lower() in title.lower():
                    results.append({
                        "title": title,
                        "rating_key": pl.get("ratingKey"),
                        "playlist_id": pl.get("ratingKey"),
                        "summary": pl.get("summary", ""),
                        "track_count": int(pl.get("leafCount", 0)),
                    })

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

    async def get_playlist_details(self, playlist_id: str) -> dict | None:
        """Gets full details for a specific playlist."""
        try:
            response = await self.client.get(f"/playlists/{playlist_id}")
            response.raise_for_status()
            return response.json().get("data")
        except httpx.HTTPStatusError as e:
            print(f"HTTP error getting playlist {playlist_id}: {e}")
            return None

    async def add_item_to_playlist(self, playlist_id: str, item_metadata: dict) -> bool:
        """Adds a structured piece of media (track/video) to the target Plex playlist."""
        # The actual endpoint structure is generally POST /playlists/{id}/items
        payload = {
            "items": [
                {
                    "media_type": "music", # Or video/tv depending on content source
                    "title": item_metadata["title"],
                    "artist": item_metadata.get("artist"),
                }
            ]
        }
        try:
            response = await self.client.post(f"/playlists/{playlist_id}/items", json=payload)
            response.raise_for_status()
            print(f"Successfully added item to playlist {playlist_id}.")
            return True
        except httpx.HTTPStatusError as e:
            print(f"Failed to add item to Plex playlist {playlist_id}: {e}")
            return False

    async def get_items_in_playlist(self, playlist_id: str) -> list[dict]:
        """Retrieves all individual items within a given playlist with pagination."""
        items = []
        offset = 0
        limit = 500  # Plex supports high limits; use a reasonable batch size

        try:
            while True:
                url = f"/playlists/{playlist_id}/items?limit={limit}&offset={offset}"
                response = await self.client.get(url)
                response.raise_for_status()

                root = ET.fromstring(response.text)
                tracks = root.findall(".//Track")

                logger.debug("Playlist %s: Retrieved %d tracks at offset %d", playlist_id, len(tracks), offset)

                if not tracks:
                    # No more items returned, exit the loop
                    logger.debug(f"Playlist {playlist_id}: No more tracks at offset {offset}, stopping pagination")
                    break

                for track in tracks:
                    # Get artist name from grandparentTitle attribute or fallback to empty
                    artist_name = track.get("grandparentTitle", "")
                    items.append({
                        "plex_id": track.get("key"),
                        "title": track.get("title"),
                        "artist_name": artist_name,
                        "album_name": track.get("parentTitle"),
                        "duration": int(track.get("duration", 0)) // 1000 if track.get("duration") else 0,
                    })

                # If we got fewer items than the limit, we've reached the end
                if len(tracks) < limit:
                    logger.debug(f"Playlist {playlist_id}: Got {len(tracks)} tracks (less than limit {limit}), stopping pagination")
                    break

                offset += limit

            logger.debug(f"Playlist {playlist_id}: Total items retrieved: {len(items)}")
            return items
        except httpx.HTTPStatusError as e:
            logger.error(f"HTTP error getting items in playlist {playlist_id}: {e}")
            return []

    async def _expand_artists(self, dirs: list[ET.Element], genre: str = "") -> list[dict]:
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
                    results.append({
                        "plex_id": track.get("key"),
                        "title": track.get("title"),
                        "artist_name": track.get("grandparentTitle") or artist_name,
                        "album_name": track.get("parentTitle") or "",
                        "duration_ms": duration_ms,
                        "track_number": int(track.get("index", 0)) if track.get("index") else None,
                        "genre": genre or None,
                    })
            except Exception as e:
                logger.warning(f"Failed to fetch tracks for artist {artist_name}: {e}")
        return results

    async def search_artist_tracks(self, artist: str, genre: str = "") -> list[dict]:
        """Search Plex for an artist directory and expand all their tracks.

        Returns:
            List of track dicts, or empty list if artist not found.
        """
        query = _normalize_search_query(artist)
        params = {"query": query, "limit": "50"}
        qs = "&".join(f"{k}={urllib.parse.quote(str(v))}" for k, v in params.items())
        artist_resp = await self.client.get(f"/search?{qs}")
        artist_resp.raise_for_status()
        artist_root = ET.fromstring(artist_resp.text)
        dirs = artist_root.findall(".//Directory")
        if not dirs:
            # Plex search struggles with certain artist names (e.g. those
            # containing apostrophes).  Retry using only the first
            # significant word as a broader query.
            words = query.split()
            if len(words) > 1:
                fallback_query = words[0]
                params = {"query": fallback_query, "limit": "50"}
                qs = "&".join(
                    f"{k}={urllib.parse.quote(str(v))}" for k, v in params.items()
                )
                artist_resp = await self.client.get(f"/search?{qs}")
                artist_resp.raise_for_status()
                artist_root = ET.fromstring(artist_resp.text)
                dirs = artist_root.findall(".//Directory")
            if not dirs:
                return []
        return await self._expand_artists(dirs, genre)

    async def search_title_only(self, title: str) -> list[dict]:
        """Direct Plex track search by title only."""
        params = {"query": _normalize_search_query(title), "limit": "100"}
        qs = "&".join(f"{k}={urllib.parse.quote(str(v))}" for k, v in params.items())
        response = await self.client.get(f"/hubs/search?{qs}")
        response.raise_for_status()
        root = ET.fromstring(response.text)
        tracks = root.findall(".//Track")
        return self._parse_tracks(tracks) if tracks else []

    async def search_library(self, title: str = "", artist: str = "", genre: str = "", album: str = "") -> list[dict]:
        """Searches the Plex music library for tracks matching the criteria.

        Strategy: Always search by artist first to get exact artist Directory entry.
        Then expand all their tracks and use token-based matching on title.
        If album is provided, first try to match within that album, then fall back
        to all artist tracks. This handles track variants (remasters, acoustic, etc.)
        much better than direct track search.

        Args:
            title: Track title to search for
            artist: Artist name to search for
            genre: Genre filter (optional)
            album: Album name to search for (optional, enables fallback matching)

        Returns:
            List of matching tracks with plex_id, title, artist_name, album_name, duration
        """

        try:
            if genre and not title and not artist:
                response = await self.client.get(
                    f"/library/all?type=8&genre={urllib.parse.quote(genre)}"
                )
                response.raise_for_status()
                root = ET.fromstring(response.text)
                dirs = root.findall(".//Directory")
                results = []
                for d in dirs:
                    results.append({
                        "plex_id": d.get("ratingKey"),
                        "title": f"[Artist] {d.get('title', '')}",
                        "artist_name": d.get("title", ""),
                        "album_name": "",
                        "duration_ms": 0,
                        "track_number": None,
                        "genre": genre,
                    })
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

                    # Album-scoped match first
                    if album:
                        norm_album = _normalize_album(album)
                        album_tracks = [t for t in result_tracks if _normalize_album(t.get("album_name", "")) == norm_album]
                        logger.debug(f"Found {len(album_tracks)} tracks in album '{album}'")
                        if album_tracks:
                            match = _best_match(title, album_tracks)
                            if match:
                                logger.debug(f"Album match: '{title}' → '{match.get('title')}' in '{album}'")
                                return [match]

                    # All-artist-tracks match
                    match = _best_match(title, result_tracks)
                    if match:
                        logger.debug(f"Matched '{title}' → '{match.get('title')}' by {match.get('artist_name', '')}")
                        return [match]

                    logger.debug(f"No match found for '{title}' by '{artist}'")
                    return []

                # No artist directory found — fall back to title-only search
                logger.debug(f"Artist directory not found: '{artist}' - falling back to title-only search")
                if title:
                    results = await self.search_title_only(title)
                    if results:
                        norm_artist = _normalize_for_compare(artist)
                        filtered = [
                            t for t in results
                            if norm_artist in _normalize_for_compare(t.get("artist_name", ""))
                            or _normalize_for_compare(t.get("artist_name", "")) in norm_artist
                        ]
                        if filtered:
                            return filtered
                        logger.debug(f"No results matching artist '{artist}' in title-only fallback")
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

    def _parse_tracks(self, track_elements: list[ET.Element]) -> list[dict]:
        """Parses Track XML elements into dicts."""
        results = []
        for track in track_elements:
            duration_ms = int(track.get("duration", 0))
            results.append({
                "plex_id": track.get("key"),
                "title": track.get("title"),
                "artist_name": track.get("grandparentTitle") or "",
                "album_name": track.get("parentTitle") or "",
                "duration_ms": duration_ms,
                "track_number": int(track.get("index", 0)) if track.get("index") else None,
            })
        return results

    async def get_library_playlist(self, source_id: str) -> dict | None:
        """Retrieves a playlist by source_id stored in custom metadata.
        
        Args:
            source_id: The source platform ID (e.g., YouTube playlist ID)
            
        Returns:
            Playlist dict with rating_key if found, None otherwise
        """
        try:
            # Search playlists for custom metadata matching source_id
            # Plex stores custom metadata in the summary field
            response = await self.client.get("/playlists")
            response.raise_for_status()

            root = ET.fromstring(response.text)
            for playlist in root.findall(".//Playlist"):
                summary = playlist.get("summary", "")
                # Check if source_id is stored in summary
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
            logger.error(f"XML parse error in get_library_playlist: {e}")
            return None

    async def create_plist_from_results(self, title: str, items: list[dict], custom_metadata: dict | None = None) -> str | None:
        """Creates a new Plex playlist and adds matched tracks to it.
        
        Creates the playlist with all items in a single request by passing
        multiple uri parameters. Plex API requires at least one uri, and
        rejects Content-Type: application/json.
        
        Args:
            title: Playlist title
            items: List of dicts with plex_id and other track metadata
            custom_metadata: Custom metadata to store in summary (e.g., {"source_playlist_id": "..."})
            
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
                import json
                params.append(("summary", json.dumps(custom_metadata)))

            # Plex accepts only one uri during creation — include just the first track
            if items:
                key = self._rating_key(items[0].get("plex_id", ""))
                if key:
                    params.append(("uri", f"server://{mi}/com.plexapp.plugins.library/library/metadata/{key}"))

            qs = "&".join(f"{k}={urllib.parse.quote(str(v))}" for k, v in params)
            request = self.client.build_request("POST", f"/playlists?{qs}")
            request.headers.pop("Content-Type", None)
            response = await self.client.send(request)
            response.raise_for_status()

            # Extract playlist ID from response
            root = ET.fromstring(response.text)
            playlist = root.find(".//Playlist")
            if playlist is None:
                logger.error("No playlist in response after creation")
                return None

            playlist_id = playlist.get("ratingKey")
            logger.info(f"Created playlist '{title}' with ID: {playlist_id}")

            # Plex only processes the first uri at creation — add the rest via PUT
            remaining = [item["plex_id"] for item in items[1:] if item.get("plex_id")]
            if remaining:
                await self.add_items_to_playlist(playlist_id, remaining)

            return playlist_id
        except httpx.HTTPStatusError as e:
            logger.error(f"HTTP error creating playlist: {e}")
            return None
        except ET.ParseError as e:
            logger.error(f"XML parse error in create_plist_from_results: {e}")
            return None

    async def get_plist_by_name(self, name: str) -> dict | None:
        """Find a playlist by exact (case-insensitive) name match.

        Args:
            name: Playlist title to search for

        Returns:
            Playlist dict with rating_key, title, etc., or None if not found
        """
        playlists = await self.search_playlists(name)
        for pl in playlists:
            if pl["title"].lower() == name.lower():
                return pl
        return None

    async def update_plist_in_place(self, playlist_id: str, items: list[dict]) -> bool:
        """Update playlist items in place while preserving its Plex ID.

        Computes a diff between current and desired items to minimize API calls.
        Only removes stale tracks and adds new ones. If the remaining tracks are
        in the correct relative order and new tracks can be appended, skips the
        full reorder. Otherwise falls back to a full replace for correct ordering.

        Args:
            playlist_id: The Plex playlist rating_key to update
            items: List of dicts with plex_id and other track metadata

        Returns:
            True if successful, False otherwise
        """
        try:
            current_items = await self.get_items_in_playlist(playlist_id)
            current_ids = [item["plex_id"] for item in current_items if item.get("plex_id")]
            desired_ids = [item["plex_id"] for item in items if item.get("plex_id")]

            # Early exit if nothing changed
            if current_ids == desired_ids:
                logger.debug(f"Playlist {playlist_id} already up to date ({len(current_ids)} items)")
                return True

            current_set = set(current_ids)
            desired_set = set(desired_ids)

            to_remove = [pid for pid in current_ids if pid not in desired_set]
            to_add_ids = [pid for pid in desired_ids if pid not in current_set]

            # Remove stale tracks
            if to_remove:
                await self.remove_items_from_playlist(playlist_id, to_remove)

            # Remaining tracks in current playlist order
            to_remove_set = set(to_remove)
            remaining_ids = [pid for pid in current_ids if pid not in to_remove_set]

            # Determine if we can just append, or need a full reorder
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
                logger.info(f"Updated playlist {playlist_id}: removed {len(to_remove)}, added {len(to_add_ids)}")

            return True
        except Exception as e:
            logger.error(f"Failed to update playlist {playlist_id} in place: {e}")
            return False

    @staticmethod
    def _playlist_needs_reorder(remaining_ids: list[str], to_add_ids: list[str], desired_ids: list[str]) -> bool:
        """Check if the playlist needs a full reorder to match desired order.

        A reorder is needed if:
        1. Remaining items are not in the correct relative order, OR
        2. New items need to be inserted before some remaining items

        Args:
            remaining_ids: IDs of items that stay in the playlist (in current order)
            to_add_ids: IDs of new items that need to be added
            desired_ids: Full desired playlist order

        Returns:
            True if a full reorder is needed
        """
        if not remaining_ids:
            return False

        # Check if remaining_ids is a subsequence of desired_ids
        it = iter(desired_ids)
        for rid in remaining_ids:
            found = False
            for did in it:
                if did == rid:
                    found = True
                    break
            if not found:
                return True

        # Check if all to_add items come after the last remaining item in desired_ids
        if to_add_ids:
            last_remaining_pos = max(desired_ids.index(rid) for rid in remaining_ids)
            for aid in to_add_ids:
                if desired_ids.index(aid) < last_remaining_pos:
                    return True

        return False

    async def delete_plist(self, playlist_id: str) -> bool:
        """Deletes a playlist from Plex.
        
        Args:
            playlist_id: The playlist rating_key to delete
            
        Returns:
            True if deletion successful, False otherwise
        """
        try:
            response = await self.client.delete(f"/playlists/{playlist_id}")
            response.raise_for_status()
            logger.info(f"Successfully deleted playlist {playlist_id}")
            return True
        except httpx.HTTPStatusError as e:
            logger.error(f"HTTP error deleting playlist {playlist_id}: {e}")
            return False

    async def close(self):
        """Closes the underlying httpx client session."""
        await self.client.aclose()


# ---------------------------------------------------------------------------
# Plex.tv OAuth helpers (standalone — use the user's token, not the server's)
# ---------------------------------------------------------------------------

PLEX_TV_API = "https://plex.tv/api/v2"


async def exchange_plex_pin(
    pin_id: int,
    pin_code: str,
    client_id: str,
) -> str | None:
    """Exchange a claimed PIN for the user's access token.

    Returns the ``authToken`` string, or ``None`` if the PIN hasn't been
    claimed yet or the request fails.
    """
    async with httpx.AsyncClient(timeout=10.0) as client:
        resp = await client.get(
            f"{PLEX_TV_API}/pins/{pin_id}",
            params={"code": pin_code},
            headers={
                "Accept": "application/json",
                "X-Plex-Client-Identifier": client_id,
                "X-Plex-Product": "Ampy3",
            },
        )
        resp.raise_for_status()
        return resp.json().get("authToken")


async def get_plex_user(plex_token: str) -> dict | None:
    """Fetch the Plex user profile for a given access token.

    Returns a dict with ``id``, ``username``, ``email``, ``thumb`` or
    ``None`` if the token is invalid.
    """
    async with httpx.AsyncClient(timeout=10.0) as client:
        resp = await client.get(
            f"{PLEX_TV_API}/user",
            headers={
                "Accept": "application/json",
                "X-Plex-Token": plex_token,
            },
        )
        if resp.status_code != 200:
            return None
        data = resp.json()
        return {
            "id": data.get("id"),
            "username": data.get("username"),
            "email": data.get("email"),
            "thumb": data.get("thumb"),
        }

