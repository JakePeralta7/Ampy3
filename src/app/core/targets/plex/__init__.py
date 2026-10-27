"""Plex Media Server sync target."""

from __future__ import annotations

from typing import Any, ClassVar

from src.app.constants import TARGET_PLEX
from src.app.core.targets.base import BaseTarget
from src.app.core.targets.factory import TargetFactory, target_factory
from src.app.core.targets.plex.client import PlexClient
from src.app.core.targets.plex.lookup import PlexPlaylistLookup
from src.app.core.targets.plex.playlist import PlexPlaylistManager
from src.app.core.targets.plex.search import PlexSearchManager
from src.app.core.targets.plex.sections import PlexSectionsManager
from src.app.core.targets.registry import TargetRegistry


class PlexTarget(BaseTarget):
    """Plex Media Server sync target."""

    target_id: ClassVar[str] = TARGET_PLEX
    display_name: ClassVar[str] = TARGET_PLEX

    search_strategy: ClassVar[type] = PlexSearchManager.search_strategy

    def __init__(self, token: str, base_url: str) -> None:
        self._plex_client = PlexClient(token, base_url)
        self._playlist_manager = PlexPlaylistManager(self._plex_client)
        self._search_manager = PlexSearchManager(self._plex_client)
        self._lookup_manager = PlexPlaylistLookup(self._plex_client, self._playlist_manager)
        self._sections_manager = PlexSectionsManager(self._plex_client)

    # Delegate to client
    @property
    def client(self):
        return self._plex_client.client

    @property
    def base_url(self) -> str:
        return self._plex_client.base_url

    # Test support: allow injection of a pre-configured PlexClient for testing
    # This is a cleaner alternative to mocking private attributes
    @classmethod
    def for_test(cls, plex_client: PlexClient) -> PlexTarget:
        """Create a PlexTarget instance with a pre-configured client (for testing)."""
        instance = cls.__new__(cls)
        instance._plex_client = plex_client
        instance._playlist_manager = PlexPlaylistManager(plex_client)
        instance._search_manager = PlexSearchManager(plex_client)
        instance._lookup_manager = PlexPlaylistLookup(plex_client, instance._playlist_manager)
        instance._sections_manager = PlexSectionsManager(plex_client)
        return instance

    # Backward compatibility for tests that mock _client directly
    @property
    def _client(self):
        """Backward compatibility for tests that mock _client directly."""
        return self._plex_client

    @_client.setter
    def _client(self, value):
        """Allow tests to inject a fake httpx client."""
        self._plex_client._client = value

    async def _ensure_machine_id(self) -> str:
        return await self._client._ensure_machine_id()

    def _rating_key(self, item_id: str) -> str:
        return self._client._rating_key(item_id)

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

    # Delegate to lookup manager
    async def get_playlist_by_name(self, name: str) -> dict[str, Any] | None:
        return await self._lookup_manager.get_playlist_by_name(name)

    async def get_playlist_by_source_id(self, source_id: str) -> dict[str, Any] | None:
        return await self._lookup_manager.get_playlist_by_source_id(source_id)

    # Delegate to sections manager
    async def get_sections(self) -> list[dict[str, Any]]:
        return await self._sections_manager.get_sections()

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
    def _meta_from_summary(summary: str) -> dict[str, Any]:
        return PlexPlaylistLookup._meta_from_summary(summary)

    @staticmethod
    def _source_id_from_url(url: str) -> str:
        return PlexPlaylistLookup._source_id_from_url(url)

    # Connection test
    async def test_connection(self) -> None:
        await self._client.test_connection()

    # Lifecycle
    async def close(self) -> None:
        await self._client.close()


@target_factory(TARGET_PLEX, "Plex Media Server")
class PlexTargetFactory(TargetFactory):
    REQUIRED_KEYS = ["plex_host", "plex_token"]
    SENSITIVE_KEYS = {"plex_token"}
    target_class = PlexTarget

    @classmethod
    def _build_kwargs(cls, config: dict[str, str]) -> dict[str, Any]:
        return {"token": config["plex_token"], "base_url": config["plex_host"]}
