"""Shared Deezer client with Valkey caching.

Wraps the public Deezer REST API (``api.deezer.com``) behind a cached async
interface shared by the sync source and the Explore provider. No
authentication is used, so no cache entries are session-annotated.
"""

from __future__ import annotations

import asyncio
from typing import Any

import httpx

from src.app.core.clients.base import MusicSourceClient

BASE_URL = "https://api.deezer.com"
REQUEST_TIMEOUT = 15


class DeezerAPIError(RuntimeError):
    """Raised when the Deezer API returns an error payload.

    Deezer returns HTTP 200 with a body like ``{"error": {"message": ...}}``
    for many failures, so it must be checked explicitly or the error dict
    would be cached and served as a successful result.
    """

    def __init__(self, endpoint: str, message: str) -> None:
        super().__init__(f"Deezer API error for /{endpoint}: {message}")
        self.endpoint = endpoint
        self.message = message


class DeezerClient(MusicSourceClient):
    """Cached wrapper around the public Deezer API."""

    source_id = "deezer"

    async def _get(self, endpoint: str, params: dict | None = None) -> Any:
        resp = await asyncio.to_thread(
            httpx.get,
            f"{BASE_URL}/{endpoint}",
            params=params,
            timeout=REQUEST_TIMEOUT,
        )
        resp.raise_for_status()
        data = resp.json()
        if isinstance(data, dict):
            error = data.get("error")
            if isinstance(error, dict) and error.get("message"):
                raise DeezerAPIError(endpoint, error["message"])
        return data

    async def get_playlist(self, playlist_id: str) -> dict[str, Any]:
        return await self._cached(
            "get_playlist",
            (playlist_id,),
            lambda: self._get(f"playlist/{playlist_id}"),
            self.playlist_cache_ttl,
        )

    async def get_trending_playlists(self, force: bool = False) -> dict[str, Any]:
        return await self._cached(
            "get_trending_playlists",
            (),
            lambda: self._get("chart/0/playlists"),
            self.explore_cache_ttl,
            force=force,
        )

    async def get_moods(self, force: bool = False) -> list[dict[str, Any]]:
        return await self._cached(
            "get_moods",
            (),
            lambda: self._get("editorial"),
            self.explore_cache_ttl,
            force=force,
        )

    async def get_mood_playlists(self, mood_id: str, force: bool = False) -> dict[str, Any]:
        return await self._cached(
            "get_mood_playlists",
            (mood_id,),
            lambda: self._get(f"editorial/{mood_id}/playlists"),
            self.explore_cache_ttl,
            force=force,
        )

    async def search_playlists(self, query: str, force: bool = False) -> dict[str, Any]:
        return await self._cached(
            "search_playlists",
            (query,),
            lambda: self._get("search/playlist", {"q": query}),
            self.explore_cache_ttl,
            force=force,
        )

    async def get_top_tracks(self, force: bool = False) -> dict[str, Any]:
        return await self._cached(
            "get_top_tracks",
            (),
            lambda: self._get("chart/0/tracks"),
            self.explore_cache_ttl,
            force=force,
        )

    async def get_top_artists(self, force: bool = False) -> dict[str, Any]:
        return await self._cached(
            "get_top_artists",
            (),
            lambda: self._get("chart/0/artists"),
            self.explore_cache_ttl,
            force=force,
        )
