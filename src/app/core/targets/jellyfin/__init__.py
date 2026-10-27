"""Jellyfin sync target."""

from __future__ import annotations

from typing import Any, ClassVar

from src.app.constants import TARGET_JELLYFIN
from src.app.core.targets.base import BaseTarget
from src.app.core.targets.factory import TargetFactory, target_factory
from src.app.core.targets.jellyfin.client import JellyfinClient
from src.app.core.targets.jellyfin.playlist import JellyfinPlaylistManager
from src.app.core.targets.jellyfin.search import JellyfinSearchManager
from src.app.core.targets.playlist_lookup import (
    find_playlist_by_name,
    find_playlist_by_source_id,
    meta_from_summary,
)
from src.app.core.targets.registry import TargetRegistry


class JellyfinTarget(BaseTarget):
    """Jellyfin sync target."""

    target_id: ClassVar[str] = TARGET_JELLYFIN
    display_name: ClassVar[str] = TARGET_JELLYFIN

    search_strategy: ClassVar[type] = JellyfinSearchManager.search_strategy

    def __init__(self, api_key: str, base_url: str, user_id: str) -> None:
        self._jellyfin_client = JellyfinClient(api_key, base_url, user_id)
        self._playlist_manager = JellyfinPlaylistManager(self._jellyfin_client)
        self._search_manager = JellyfinSearchManager(self._jellyfin_client)

    # Delegate to client
    @property
    def client(self):
        return self._jellyfin_client.client

    @property
    def base_url(self) -> str:
        return self._jellyfin_client.base_url

    @property
    def user_id(self) -> str:
        return self._jellyfin_client.user_id

    # Test support: allow injection of a pre-configured JellyfinClient for testing
    # This is a cleaner alternative to mocking private attributes
    @classmethod
    def for_test(cls, jellyfin_client: JellyfinClient) -> JellyfinTarget:
        """Create a JellyfinTarget instance with a pre-configured client (for testing)."""
        instance = cls.__new__(cls)
        instance._jellyfin_client = jellyfin_client
        instance._playlist_manager = JellyfinPlaylistManager(jellyfin_client)
        instance._search_manager = JellyfinSearchManager(jellyfin_client)
        return instance

    # Backward compatibility for tests that mock _client directly
    @property
    def _client(self):
        """Backward compatibility for tests that mock _client directly."""
        return self._jellyfin_client

    @_client.setter
    def _client(self, value):
        """Allow tests to inject a fake httpx client."""
        self._jellyfin_client._client = value

    # Delegate to playlist manager
    async def client_url(self, playlist_id: str) -> str:
        return await self._playlist_manager.client_url(playlist_id)

    async def search_playlists(self, query: str) -> list[dict[str, Any]]:
        return await self._playlist_manager.search_playlists(query)

    async def get_playlist_details(self, playlist_id: str) -> dict[str, Any] | None:
        return await self._playlist_manager.get_playlist_details(playlist_id)

    async def create_playlist(
        self,
        title: str,
        items: list[dict[str, Any]],
        custom_metadata: dict[str, Any] | None = None,
    ) -> str | None:
        return await self._playlist_manager.create_playlist(title, items, custom_metadata)

    async def update_playlist(self, playlist_id: str, items: list[dict[str, Any]]) -> bool:
        return await self._playlist_manager.update_playlist(playlist_id, items)

    async def delete_playlist(self, playlist_id: str) -> bool:
        return await self._playlist_manager.delete_playlist(playlist_id)

    async def get_items_in_playlist(self, playlist_id: str) -> list[dict[str, Any]]:
        return await self._playlist_manager.get_items_in_playlist(playlist_id)

    async def add_items_to_playlist(self, playlist_id: str, item_ids: list[str]) -> int:
        return await self._playlist_manager.add_items_to_playlist(playlist_id, item_ids)

    async def remove_items_from_playlist(self, playlist_id: str, item_ids: list[str]) -> int:
        return await self._playlist_manager.remove_items_from_playlist(playlist_id, item_ids)

    # Delegate to playlist manager (lookup)
    async def get_playlist_by_name(self, name: str) -> dict[str, Any] | None:
        """Find a playlist by exact name."""
        return find_playlist_by_name(await self.search_playlists(name), name)

    async def get_playlist_by_source_id(self, source_id: str) -> dict[str, Any] | None:
        """Find a playlist by the exact source id stored in its metadata.

        Every Ampy3-created playlist stores ``{"source_url": ...,
        "sync_id": ...}`` (and, going forward, ``source_id``) as a JSON
        ``Overview`` string. We compare exact values rather than substring
        matching so one id can never match a foreign playlist's metadata.
        """
        return find_playlist_by_source_id(await self.search_playlists(""), source_id)

    # Delegate to search manager
    async def search_artist_tracks(self, artist: str, genre: str = "") -> list[dict[str, Any]]:
        return await self._search_manager.search_artist_tracks(artist, genre)

    async def search_title_only(self, title: str) -> list[dict[str, Any]]:
        return await self._search_manager.search_title_only(title)

    async def search_library(
        self,
        title: str = "",
        artist: str = "",
        genre: str = "",
        album: str = "",
    ) -> list[dict[str, Any]]:
        return await self._search_manager.search_library(
            title=title, artist=artist, genre=genre, album=album
        )

    # Abstract methods required by BaseTarget
    async def _search_by_title_artist_album(
        self,
        title: str,
        artist: str,
        album: str = "",
        genre: str = "",
    ) -> list[dict[str, Any]]:
        return await self._search_manager._search_by_title_artist_album(
            title=title, artist=artist, album=album, genre=genre
        )

    async def _search_by_genre(self, genre: str) -> list[dict[str, Any]]:
        return await self._search_manager._search_by_genre(genre)

    # Static methods for backward compatibility with tests
    @staticmethod
    def _meta_from_overview(playlist: dict[str, Any]) -> dict[str, Any]:
        return meta_from_summary(str(playlist.get("summary") or ""))

    @staticmethod
    def _source_id_from_url(url: str) -> str:
        return JellyfinPlaylistManager._source_id_from_url(url)

    # Connection test
    async def test_connection(self) -> None:
        await self._jellyfin_client.test_connection()

    # Lifecycle
    async def close(self) -> None:
        await self._jellyfin_client.close()


@target_factory(TARGET_JELLYFIN, "Jellyfin")
class JellyfinTargetFactory(TargetFactory):
    REQUIRED_KEYS = ["jellyfin_server_url", "jellyfin_api_key", "jellyfin_user_id"]
    SENSITIVE_KEYS = {"jellyfin_api_key"}
    target_class = JellyfinTarget

    @classmethod
    def _build_kwargs(cls, config: dict[str, str]) -> dict[str, Any]:
        return {
            "api_key": config["jellyfin_api_key"],
            "base_url": config["jellyfin_server_url"],
            "user_id": config["jellyfin_user_id"],
        }
