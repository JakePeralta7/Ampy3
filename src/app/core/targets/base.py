"""Abstract base class for sync targets (media servers)."""

from __future__ import annotations

import logging
from abc import ABC, abstractmethod
from typing import Any, ClassVar

logger = logging.getLogger(__name__)


class BaseTarget(ABC):
    """Contract that all sync target adapters must fulfill.

    A sync target is the destination where matched playlists are created or
    updated — e.g. Plex Media Server, Jellyfin, Navidrome, etc.
    """

    target_id: ClassVar[str]
    """Unique identifier, e.g. ``"Plex"``."""

    display_name: ClassVar[str]
    """Human-readable name, e.g. ``"Plex Media Server"``."""

    # ── Playlist operations ──────────────────────────────────────

    @abstractmethod
    async def search_playlists(self, query: str) -> list[dict[str, Any]]:
        """Search for playlists matching *query*.

        Returns a list of dicts with at least ``title``, ``id``,
        ``track_count``.
        """

    @abstractmethod
    async def get_playlist_details(self, playlist_id: str) -> dict[str, Any] | None:
        """Return full details for a single playlist."""

    @abstractmethod
    async def create_playlist(
        self,
        title: str,
        items: list[dict[str, Any]],
        custom_metadata: dict[str, Any] | None = None,
    ) -> str | None:
        """Create a new playlist with the given *items*.

        Returns the new playlist ID on success, ``None`` on failure.
        """

    @abstractmethod
    async def update_playlist(self, playlist_id: str, items: list[dict[str, Any]]) -> bool:
        """Replace *playlist_id*'s items with *items*.

        Returns ``True`` on success.
        """

    @abstractmethod
    async def delete_playlist(self, playlist_id: str) -> bool:
        """Delete a playlist by ID."""

    @abstractmethod
    async def get_items_in_playlist(self, playlist_id: str) -> list[dict[str, Any]]:
        """Return all track items in a playlist."""

    # ── Playlist lookup ──────────────────────────────────────────

    @abstractmethod
    async def get_playlist_by_name(self, name: str) -> dict[str, Any] | None:
        """Find a playlist by exact name.

        Returns the playlist dict or ``None``.
        """

    @abstractmethod
    async def get_playlist_by_source_id(self, source_id: str) -> dict[str, Any] | None:
        """Find a playlist by its source platform ID stored in metadata.

        Returns the playlist dict or ``None``.
        """

    # ── Item management ──────────────────────────────────────────

    @abstractmethod
    async def add_items_to_playlist(self, playlist_id: str, item_ids: list[str]) -> int:
        """Append items to an existing playlist.

        Returns the number of items added.
        """

    @abstractmethod
    async def remove_items_from_playlist(self, playlist_id: str, item_ids: list[str]) -> int:
        """Remove items from a playlist.

        Returns the number of items removed.
        """

    # ── Library search ───────────────────────────────────────────

    @abstractmethod
    async def search_library(
        self,
        title: str = "",
        artist: str = "",
        genre: str = "",
        album: str = "",
    ) -> list[dict[str, Any]]:
        """Search the media library for tracks matching the given criteria.

        Returns a list of dicts with at least ``item_id``/`id``,
        ``title``, ``artist_name``, ``album_name``, ``duration_ms``.
        """

    @abstractmethod
    async def search_artist_tracks(self, artist: str, genre: str = "") -> list[dict[str, Any]]:
        """Search the library for all tracks by an artist."""

    @abstractmethod
    async def search_title_only(self, title: str) -> list[dict[str, Any]]:
        """Search the library by title only."""

    # ── Connection test ─────────────────────────────────────────

    @abstractmethod
    async def test_connection(self) -> None:
        """Verify connectivity with the target server.

        Raises an exception if the connection fails. Returns ``None`` on success.
        """

    # ── Lifecycle ────────────────────────────────────────────────

    @abstractmethod
    async def close(self) -> None:
        """Release any resources held by this target."""
