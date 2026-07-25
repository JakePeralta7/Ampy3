"""Jellyfin sync target adapter."""

from __future__ import annotations

from src.app.core.jellyfin.client import JellyfinClient
from src.app.core.targets.base import BaseTarget
from src.app.core.targets.registry import register_target


@register_target("jellyfin")
class JellyfinTarget(BaseTarget):
    target_id = "jellyfin"
    display_name = "Jellyfin"

    def __init__(self, client: JellyfinClient) -> None:
        self._client = client

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
        return await self._client.create_plist_from_results(title, items, custom_metadata)

    async def update_playlist(self, playlist_id: str, items: list[dict]) -> bool:
        return await self._client.update_plist_in_place(playlist_id, items)

    async def delete_playlist(self, playlist_id: str) -> bool:
        return await self._client.delete_plist(playlist_id)

    async def get_items_in_playlist(self, playlist_id: str) -> list[dict]:
        return await self._client.get_items_in_playlist(playlist_id)

    async def get_playlist_by_name(self, name: str) -> dict | None:
        return await self._client.get_plist_by_name(name)

    async def get_playlist_by_source_id(self, source_id: str) -> dict | None:
        return await self._client.get_library_playlist(source_id)

    async def add_items_to_playlist(self, playlist_id: str, item_ids: list[str]) -> int:
        return await self._client.add_items_to_playlist(playlist_id, item_ids)

    async def remove_items_from_playlist(self, playlist_id: str, item_ids: list[str]) -> int:
        return await self._client.remove_items_from_playlist(playlist_id, item_ids)

    async def search_library(
        self,
        title: str = "",
        artist: str = "",
        genre: str = "",
        album: str = "",
    ) -> list[dict]:
        return await self._client.search_library(
            title=title,
            artist=artist,
            genre=genre,
            album=album,
        )

    async def search_artist_tracks(self, artist: str, genre: str = "") -> list[dict]:
        return await self._client.search_artist_tracks(artist, genre)

    async def search_title_only(self, title: str) -> list[dict]:
        return await self._client.search_title_only(title)

    async def close(self) -> None:
        await self._client.close()
