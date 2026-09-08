"""Shared music-platform API clients with Valkey caching.

Both the sync sources and the Explore providers fetch the same upstream
data (a playlist, the home feed, moods, …). These clients centralise those
fetches behind a single cached interface so the two features share cache
entries instead of duplicating them.
"""

from __future__ import annotations

import asyncio
import json
import logging
from abc import ABC
from collections.abc import Awaitable, Callable
from typing import Any

from src.app.services.valkey import ValkeyService
from src.app.settings import settings

logger = logging.getLogger(__name__)

_CACHE_MISS = object()
"""Sentinel distinguishing a cache miss/error from a cached value."""


class MusicSourceClient(ABC):
    """Base class for cached music-platform API clients.

    Subclasses set ``source_id`` (namespaces cache keys) and call
    ``self._cached(...)`` from their public async methods to transparently
    short-circuit on a Valkey cache hit. Caching is fail-open: if Valkey is
    unreachable the client simply fetches from the upstream API.

    Cache write TTL is passed by the caller — playlist fetches use
    ``SOURCE_PLAYLIST_CACHE_TTL_SECONDS`` and Explore content uses
    ``EXPLORE_CACHE_TTL_SECONDS``.
    """

    source_id: str

    @property
    def playlist_cache_ttl(self) -> int:
        return settings.source_playlist_cache_ttl_seconds

    @property
    def explore_cache_ttl(self) -> int:
        return settings.explore_cache_ttl_seconds

    def _cache_key(self, method: str, *key_parts: str) -> str:
        return ":".join((self.source_id, method, *key_parts))

    async def _cached(
        self,
        method: str,
        key_parts: tuple[str, ...],
        fetch: Callable[[], Awaitable[Any]],
        ttl: int,
        *,
        force: bool = False,
    ) -> Any:
        """Return *fetch()*'s result, caching it under a Valkey key.

        :param force: skip the cache read (the result is still written).
        Raises propagate: a failed upstream fetch is never cached.
        """
        key = self._cache_key(method, *key_parts)
        if not force:
            cached = await self._cache_get(key)
            if cached is not _CACHE_MISS:
                logger.debug("Cache hit for %s", key)
                return cached
        value = await fetch()
        await self._cache_set(key, value, ttl)
        return value

    async def _cache_get(self, key: str) -> Any:
        try:
            client = ValkeyService.get_sync_instance()
            raw: str | None = await asyncio.to_thread(client.get, key)  # type: ignore[arg-type]
            if raw is None:
                return _CACHE_MISS
            value = json.loads(raw)
            if not isinstance(value, (dict, list)):
                logger.debug("Ignoring malformed cache entry for %s", key)
                return _CACHE_MISS
            return value
        except Exception as exc:  # noqa: BLE001 - the cache must never block a fetch
            logger.debug("Cache read failed for %s (non-fatal): %s", key, exc)
            return _CACHE_MISS

    async def _cache_set(self, key: str, value: Any, ttl: int) -> None:
        try:
            client = ValkeyService.get_sync_instance()
            await asyncio.to_thread(client.setex, key, ttl, json.dumps(value))
        except Exception as exc:  # noqa: BLE001 - the cache must never break a fetch
            logger.debug("Cache write failed for %s (non-fatal): %s", key, exc)
