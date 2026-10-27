"""Plex playlist lookup operations (by name, by source_id)."""

import logging
from typing import Any

from src.app.core.targets.playlist_lookup import PlaylistLookupMixin
from src.app.core.targets.plex.client import PlexClient
from src.app.core.targets.plex.playlist import PlexPlaylistManager

logger = logging.getLogger(__name__)


class PlexPlaylistLookup(PlaylistLookupMixin):
    """Handles playlist lookup operations for Plex.

    Name/source-id resolution lives in :class:`PlaylistLookupMixin`; this class
    only supplies Plex's "list every playlist" call.
    """

    def __init__(self, client: PlexClient, playlist_manager: PlexPlaylistManager) -> None:
        self._client = client
        self._playlist_manager = playlist_manager

    async def _list_playlists(self) -> list[dict[str, Any]]:
        return await self._playlist_manager.search_playlists("")
