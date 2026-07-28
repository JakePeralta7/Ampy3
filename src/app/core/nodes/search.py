"""Search node handlers (plex_search legacy + search)."""

from __future__ import annotations

import logging

from src.app.core.models import TrackMetadata
from src.app.core.nodes.base import NodeHandlerBase, NodeInputs, NodeOutputs
from src.app.core.nodes.registry import get_current_target, register_node

logger = logging.getLogger(__name__)


@register_node("plex_search")
class PlexSearchNode(NodeHandlerBase):
    async def execute(self, track: TrackMetadata, inputs: NodeInputs) -> NodeOutputs:
        target = get_current_target()
        data = inputs.get("in", {})
        search_type = self._config.get("search_type", "title_artist_album")
        max_results = self._config.get("max_results", 50)

        if search_type in ("artist_tracks", "artist_only"):
            artist = data.get("artist_name", "")
            if not artist:
                return {"out": []}
            results = await target.search_artist_tracks(artist)
            return {"out": results[:max_results]}

        if search_type == "title_only":
            title = data.get("title", "")
            if not title:
                return {"out": []}
            results = await target.search_title_only(title)
            return {"out": results[:max_results]}

        if search_type == "album_only":
            album = data.get("album_name", "")
            if not album:
                return {"out": []}
            results = await target.search_library(album=album)
            return {"out": results[:max_results]}

        if search_type == "title_artist":
            results = await target.search_library(
                title=data.get("title", ""),
                artist=data.get("artist_name", ""),
            )
            return {"out": results[:max_results]}

        if search_type == "artist_album":
            results = await target.search_library(
                artist=data.get("artist_name", ""),
                album=data.get("album_name", ""),
            )
            return {"out": results[:max_results]}

        results = await target.search_library(
            title=data.get("title", ""),
            artist=data.get("artist_name", ""),
            album=data.get("album_name", ""),
        )
        return {"out": results[:max_results] if results else []}


@register_node("search")
class SearchNode(NodeHandlerBase):
    """New simplified search node - uses checkbox config."""

    async def execute(self, track: TrackMetadata, inputs: NodeInputs) -> NodeOutputs:
        target = get_current_target()

        data = inputs.get("in", {})
        if not data or not isinstance(data, dict):
            data = {
                "title": track.title or "",
                "artist_name": track.artist_name or "",
                "album_name": track.album_name or "",
            }

        if "fields_to_search" in self._config:
            fields = self._config.get("fields_to_search", [])
            search_title = "search_title" in fields
            search_artist = "search_artist" in fields
            search_album = "search_album" in fields
        else:
            search_title = self._config.get("search_title", True)
            search_artist = self._config.get("search_artist", True)
            search_album = self._config.get("search_album", True)

        max_results = self._config.get("max_results", 50)

        title = data.get("title", "") if search_title else ""
        artist = data.get("artist_name", "") if search_artist else ""
        album = data.get("album_name", "") if search_album else ""

        logger.debug(
            "[SEARCH] Input track: title=%s, artist=%s, album=%s",
            track.title,
            track.artist_name,
            track.album_name,
        )
        logger.debug(
            "[SEARCH] Search config: title=%s, artist=%s, album=%s",
            search_title,
            search_artist,
            search_album,
        )
        logger.debug(
            "[SEARCH] Search params: title=%s, artist=%s, album=%s",
            title,
            artist,
            album,
        )

        if not search_title and not search_artist and not search_album:
            return {"out": []}

        if search_title and not search_artist and not search_album:
            if not title:
                return {"out": []}
            results = await target.search_title_only(title)
            logger.debug(f"[SEARCH] Title-only search returned {len(results)} results")
            return {"out": results[:max_results]}

        if search_artist and not search_title and not search_album:
            if not artist:
                return {"out": []}
            results = await target.search_artist_tracks(artist)
            logger.debug(f"[SEARCH] Artist-only search returned {len(results)} results")
            return {"out": results[:max_results]}

        if search_album and not search_title and not search_artist:
            if not album:
                return {"out": []}
            results = await target.search_library(album=album)
            logger.debug(f"[SEARCH] Album-only search returned {len(results)} results")
            return {"out": results[:max_results]}

        results = await target.search_library(title=title, artist=artist, album=album)
        count = len(results) if results else 0
        logger.debug("[SEARCH] Multi-field search returned %d results", count)
        return {"out": results[:max_results] if results else []}
