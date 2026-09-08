"""Shared YouTube Music client with Valkey caching.

Wraps the synchronous ``ytmusicapi`` SDK behind an async, self-caching
interface shared by the sync source and the Explore provider.

The SDK is not thread-safe, so every call is serialised through
``asyncio.to_thread`` under a lock. The lock rebinds to the current running
loop: Celery workers use ``asyncio.run()`` — a fresh event loop per task —
so a lock bound to one loop would poison the next task.
"""

from __future__ import annotations

import asyncio
import hashlib
import json
from typing import Any

from ytmusicapi import YTMusic

from src.app.core.clients.base import MusicSourceClient
from src.app.services.ytauth import get_ytmusic_auth
from src.app.settings import settings


class YouTubeMusicClient(MusicSourceClient):
    """Cached wrapper around the ``ytmusicapi`` ``YTMusic`` SDK."""

    source_id = "youtube_music"

    def __init__(self) -> None:
        self._client: YTMusic | None = None
        self._client_auth_key: str | None = None
        self._lock: asyncio.Lock | None = None
        self._lock_loop: asyncio.AbstractEventLoop | None = None

    # ── session management ──────────────────────────────────────────

    def _get_client(self) -> YTMusic:
        """Return the SDK instance for the currently stored auth payload.

        The SDK holds its request headers, so it is rebuilt whenever the
        stored authentication changes.
        """
        auth = get_ytmusic_auth()
        key = json.dumps(auth, sort_keys=True) if auth else None
        if self._client is not None and self._client_auth_key == key:
            return self._client
        if auth:
            self._client = YTMusic(auth=auth)
        else:
            self._client = YTMusic()
        self._client_auth_key = key
        return self._client

    def _session_tag(self) -> str:
        """Return a stable tag identifying the current auth session.

        ``get_home`` returns a *personalised* feed, so its cache key is
        annotated with the identity of the session that produced it. After a
        re-auth the stored payload changes, which changes this tag — the old
        session's cached feed is never served afterwards, and simply expires
        at its TTL.
        """
        auth = get_ytmusic_auth()
        if not auth:
            return "anon"
        digest = hashlib.sha256(json.dumps(auth, sort_keys=True).encode()).hexdigest()
        return f"session:{digest[:16]}"

    async def _run(self, method_name: str, *args, **kwargs) -> Any:
        """Run a ytmusicapi method in a thread, serialised by a lock."""
        loop = asyncio.get_running_loop()
        if self._lock is None or self._lock_loop is not loop:
            self._lock = asyncio.Lock()
            self._lock_loop = loop
        async with self._lock:
            return await asyncio.to_thread(
                getattr(self._get_client(), method_name), *args, **kwargs
            )

    # ── cached interface ────────────────────────────────────────────

    async def get_playlist(self, playlist_id: str, limit: int | None = None) -> dict[str, Any]:
        return await self._cached(
            "get_playlist",
            (playlist_id,),
            lambda: asyncio.wait_for(
                self._run("get_playlist", playlist_id, limit=limit),
                timeout=settings.yt_dlp_timeout,
            ),
            self.playlist_cache_ttl,
        )

    async def get_home(self, force: bool = False) -> dict[str, Any]:
        """Return the personalised home feed for the current session."""
        return await self._cached(
            "get_home",
            (self._session_tag(),),
            lambda: self._run("get_home"),
            self.explore_cache_ttl,
            force=force,
        )

    async def get_charts(self, force: bool = False) -> dict[str, Any]:
        return await self._cached(
            "get_charts",
            (),
            lambda: self._run("get_charts"),
            self.explore_cache_ttl,
            force=force,
        )

    async def get_mood_categories(self, force: bool = False) -> dict[str, Any]:
        return await self._cached(
            "get_mood_categories",
            (),
            lambda: self._run("get_mood_categories"),
            self.explore_cache_ttl,
            force=force,
        )

    async def get_mood_playlists(self, mood_id: str, force: bool = False) -> list[dict[str, Any]]:
        return await self._cached(
            "get_mood_playlists",
            (mood_id,),
            lambda: self._run("get_mood_playlists", mood_id),
            self.explore_cache_ttl,
            force=force,
        )

    async def search_playlists(self, query: str, force: bool = False) -> list[dict[str, Any]]:
        return await self._cached(
            "search_playlists",
            (query,),
            lambda: self._run("search", query, filter="playlists"),
            self.explore_cache_ttl,
            force=force,
        )
