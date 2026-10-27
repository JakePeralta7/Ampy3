"""Shared playlist identity helpers for sync targets.

Plex and Jellyfin both persist an Ampy3 playlist's identity as a JSON metadata
blob in the playlist's summary/overview field, and both resolve playlists by
exact name or exact source id. This module centralises that logic so each
target only supplies its own "list all playlists" call.

Exact comparison (never substring) is deliberate: one source id must never
match a playlist whose metadata merely happens to *contain* it.
"""

from __future__ import annotations

import json
import logging
from typing import Any

from src.app.core.urls import source_id_from_url

logger = logging.getLogger(__name__)


def meta_from_summary(summary: str | None) -> dict[str, Any]:
    """Parse the JSON metadata blob stored in a playlist's summary/overview.

    Returns ``{}`` for empty, non-JSON, or non-object payloads rather than
    raising — a foreign playlist may carry arbitrary text in that field.
    """
    if not summary:
        return {}
    try:
        data = json.loads(summary)
    except ValueError, TypeError:
        return {}
    return data if isinstance(data, dict) else {}


def find_playlist_by_name(playlists: list[dict[str, Any]], name: str) -> dict[str, Any] | None:
    """Return the playlist whose title matches *name* exactly (case-insensitive)."""
    target = name.lower().strip()
    for playlist in playlists:
        if str(playlist.get("title", "")).lower().strip() == target:
            return playlist
    return None


def find_playlist_by_source_id(
    playlists: list[dict[str, Any]], source_id: str
) -> dict[str, Any] | None:
    """Return the playlist whose stored metadata carries *source_id* exactly."""
    if not source_id:
        return None
    wanted = str(source_id).strip()
    for playlist in playlists:
        meta = meta_from_summary(str(playlist.get("summary") or ""))
        if meta.get("source_id") == wanted:
            return playlist
        url = meta.get("source_url")
        if isinstance(url, str) and source_id_from_url(url) == wanted:
            return playlist
    return None


class PlaylistLookupMixin:
    """Mixin for target playlist managers that resolve playlists by identity.

    Subclasses implement :meth:`_list_playlists`, which must return every
    playlist visible to the target as a list of ``{"title", "summary", ...}``
    dicts. The mixin then supplies name/source-id resolution.
    """

    async def _list_playlists(self) -> list[dict[str, Any]]:
        raise NotImplementedError

    async def get_playlist_by_name(self, name: str) -> dict[str, Any] | None:
        """Find a playlist by exact (case-insensitive) title."""
        return find_playlist_by_name(await self._list_playlists(), name)

    async def get_playlist_by_source_id(self, source_id: str) -> dict[str, Any] | None:
        """Find a playlist by the exact source id stored in its metadata."""
        return find_playlist_by_source_id(await self._list_playlists(), source_id)

    # Backwards-compatible static helpers used by target classes/tests.
    _meta_from_summary = staticmethod(meta_from_summary)
    _source_id_from_url = staticmethod(source_id_from_url)
