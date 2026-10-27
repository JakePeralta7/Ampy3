"""Plex library search operations."""

import asyncio
import logging
import re
import xml.etree.ElementTree as ET
from typing import Any

import httpx

from src.app.core.matching import (
    _best_match,
    _extract_primary_artist,
    _normalize_album,
    normalize,
)
from src.app.core.targets.plex.client import PlexClient
from src.app.core.targets.search import SearchStrategy, TitleArtistAlbumSearch
from src.app.core.urls import source_id_from_url

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


class PlexSearchManager:
    """Handles all library search operations for Plex."""

    search_strategy: SearchStrategy = TitleArtistAlbumSearch()

    def __init__(self, client: PlexClient) -> None:
        self._client = client

    async def _expand_artists(
        self, dirs: list[ET.Element], genre: str = ""
    ) -> list[dict[str, Any]]:
        """Expands Directory (artist) entries into their tracks via allLeaves.

        Uses bounded concurrency (max 5 parallel requests) to avoid overwhelming
        the Plex server with sequential allLeaves calls.
        """
        semaphore = asyncio.Semaphore(5)

        async def fetch_artist_tracks(d: ET.Element) -> list[dict[str, Any]]:
            artist_name = d.get("title", "")
            artist_key = d.get("key", "")
            leaf_key = artist_key.replace("/children", "/allLeaves")
            async with semaphore:
                try:
                    leaf_resp = await self._client.client.get(leaf_key)
                    leaf_resp.raise_for_status()
                    leaf_root = ET.fromstring(leaf_resp.text)
                    tracks = []
                    for track in leaf_root.findall(".//Track"):
                        duration_ms = int(track.get("duration", 0))
                        tracks.append(
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
                    return tracks
                except Exception as e:
                    logger.warning("Failed to fetch tracks for artist %s: %s", artist_name, e)
                    return []

        results = await asyncio.gather(*[fetch_artist_tracks(d) for d in dirs])
        return [track for artist_tracks in results for track in artist_tracks]

    async def search_artist_tracks(self, artist: str, genre: str = "") -> list[dict[str, Any]]:
        """Search Plex for an artist directory and expand all their tracks."""
        query = _normalize_search_query(artist)
        if not query:
            return []
        params = {"query": query, "limit": "50"}
        artist_resp = await self._client.client.get("/search", params=params)
        artist_resp.raise_for_status()
        artist_root = ET.fromstring(artist_resp.text)
        dirs = artist_root.findall(".//Directory")
        if not dirs:
            words = query.split()
            if len(words) > 1:
                fallback_query = words[0]
                params = {"query": fallback_query, "limit": "50"}
                artist_resp = await self._client.client.get("/search", params=params)
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
        response = await self._client.client.get("/hubs/search", params=params)
        response.raise_for_status()
        root = ET.fromstring(response.text)
        tracks = root.findall(".//Track")
        return self._parse_tracks(tracks) if tracks else []

    async def _search_by_title_artist_album(
        self,
        title: str,
        artist: str,
        album: str = "",
        genre: str = "",
    ) -> list[dict[str, Any]]:
        """Search by title, artist, and optional album (Plex-specific combined search)."""
        try:
            primary_artist = _extract_primary_artist(artist)
            log_msg = f"Searching for track by artist='{primary_artist}', title='{title}'"
            if album:
                log_msg += f", album='{album}'"
            if genre:
                log_msg += f", genre='{genre}'"
            logger.debug(log_msg)

            result_tracks = await self.search_artist_tracks(primary_artist, genre)

            if result_tracks:
                logger.debug("Expanded artist '%s' to %d tracks", artist, len(result_tracks))

                if album:
                    norm_album = _normalize_album(album)
                    album_tracks = [
                        t
                        for t in result_tracks
                        if _normalize_album(t.get("album_name", "")) == norm_album
                    ]
                    logger.debug("Found %d tracks in album '%s'", len(album_tracks), album)
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

                logger.debug("No match found for '%s' by '%s'", title, artist)
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
        except httpx.HTTPStatusError as e:
            self._client._log_plex_error("search_library", e)
            return []
        except ET.ParseError as e:
            logger.error("XML parse error in _search_by_title_artist_album: %s", e)
            return []

    async def _search_by_genre(self, genre: str) -> list[dict[str, Any]]:
        """Search for artists by genre."""
        try:
            response = await self._client.client.get(
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
                logger.debug("Found %d artists matching genre '%s'", len(results), genre)
            return results
        except httpx.HTTPStatusError as e:
            self._client._log_plex_error("search_by_genre", e)
            return []
        except ET.ParseError as e:
            logger.error("XML parse error in _search_by_genre: %s", e)
            return []

    async def search_library(
        self,
        title: str = "",
        artist: str = "",
        genre: str = "",
        album: str = "",
    ) -> list[dict[str, Any]]:
        """Search the Plex music library using the configured search strategy."""
        return await self._search_via_strategy(title=title, artist=artist, genre=genre, album=album)

    async def _search_via_strategy(
        self,
        title: str = "",
        artist: str = "",
        genre: str = "",
        album: str = "",
    ) -> list[dict[str, Any]]:
        """Dispatch to the configured search strategy.

        The strategy calls back into this manager (``_do_search``,
        ``_search_by_title_artist_album``, ``search_artist_tracks``,
        ``search_title_only``, ``_search_by_genre``), which is why the manager
        is passed as the strategy's ``target``.
        """
        from src.app.core.targets.search import SearchCriteria

        criteria = SearchCriteria(title=title, artist=artist, genre=genre, album=album)
        candidates = await self.search_strategy.search(self, criteria)
        return [candidate.to_dict() for candidate in candidates]

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
