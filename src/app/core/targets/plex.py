"""Plex Media Server sync target adapter."""
from __future__ import annotations

import logging

from src.app.core.plex.client import PlexClient
from src.app.core.targets.base import BaseTarget
from src.app.core.targets.registry import register_target

logger = logging.getLogger(__name__)


@register_target("plex")
class PlexTarget(BaseTarget):
    """Plex Media Server target.

    Delegates all HTTP operations to :class:`PlexClient` while presenting
    the generic :class:`BaseTarget` interface used by the orchestrator and
    node-graph match engine.
    """

    target_id = "plex"
    display_name = "Plex Media Server"

    def __init__(self, client: PlexClient) -> None:
        self._client = client

    @property
    def client(self) -> PlexClient:
        """Expose the underlying client for Plex-specific operations."""
        return self._client

    # ── Playlist operations ──────────────────────────────────────

    async def search_playlists(self, query: str) -> list[dict]:
        return await self._client.search_playlists(query)

    async def get_playlist_details(self, playlist_id: str) -> dict | None:
        return await self._client.get_playlist_details(playlist_id)

    async def create_playlist(
        self,
        title: str,
        items: list[dict],
        custom_metadata: dict | None = None,
    ) -> str | None:
        return await self._client.create_plist_from_results(
            title=title, items=items, custom_metadata=custom_metadata,
        )

    async def update_playlist(self, playlist_id: str, items: list[dict]) -> bool:
        return await self._client.update_plist_in_place(playlist_id, items)

    async def delete_playlist(self, playlist_id: str) -> bool:
        return await self._client.delete_plist(playlist_id)

    async def get_items_in_playlist(self, playlist_id: str) -> list[dict]:
        return await self._client.get_items_in_playlist(playlist_id)

    # ── Playlist lookup ──────────────────────────────────────────

    async def get_playlist_by_name(self, name: str) -> dict | None:
        return await self._client.get_plist_by_name(name)

    async def get_playlist_by_source_id(self, source_id: str) -> dict | None:
        return await self._client.get_library_playlist(source_id)

    # ── Item management ──────────────────────────────────────────

    async def add_items_to_playlist(self, playlist_id: str, item_ids: list[str]) -> int:
        return await self._client.add_items_to_playlist(playlist_id, item_ids)

    async def remove_items_from_playlist(self, playlist_id: str, item_ids: list[str]) -> int:
        return await self._client.remove_items_from_playlist(playlist_id, item_ids)

    # ── Library search ───────────────────────────────────────────

    async def search_library(
        self,
        title: str = "",
        artist: str = "",
        genre: str = "",
        album: str = "",
    ) -> list[dict]:
        return await self._client.search_library(
            title=title, artist=artist, genre=genre, album=album,
        )

    async def search_artist_tracks(self, artist: str, genre: str = "") -> list[dict]:
        return await self._client.search_artist_tracks(artist, genre)

    async def search_title_only(self, title: str) -> list[dict]:
        return await self._client.search_title_only(title)

    # ── Lifecycle ────────────────────────────────────────────────

    async def close(self) -> None:
        await self._client.close()
