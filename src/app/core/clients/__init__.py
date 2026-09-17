"""Shared music-platform API clients.

One cached client class per platform (`YouTubeMusicClient`, `DeezerClient`)
used by **both** the sync sources and the Explore providers, so they share
the same Valkey cache entries instead of duplicating fetches.
"""

from __future__ import annotations

from typing import TYPE_CHECKING

from src.app.core.clients.base import MusicSourceClient

if TYPE_CHECKING:
    from src.app.core.clients.deezer import DeezerClient
    from src.app.core.clients.ytmusic import YouTubeMusicClient

_ytmusic_client: YouTubeMusicClient | None = None
_deezer_client: DeezerClient | None = None


def get_ytmusic_client() -> YouTubeMusicClient:
    """Return the shared ``YouTubeMusicClient`` instance (lazy singleton)."""
    global _ytmusic_client
    if _ytmusic_client is None:
        from src.app.core.clients.ytmusic import YouTubeMusicClient

        _ytmusic_client = YouTubeMusicClient()
    return _ytmusic_client


def get_deezer_client() -> DeezerClient:
    """Return the shared ``DeezerClient`` instance (lazy singleton)."""
    global _deezer_client
    if _deezer_client is None:
        from src.app.core.clients.deezer import DeezerClient

        _deezer_client = DeezerClient()
    return _deezer_client


def reset_clients() -> None:
    """Drop cached client instances (used by tests between cases)."""
    global _ytmusic_client, _deezer_client
    _ytmusic_client = None
    _deezer_client = None


__all__ = [
    "MusicSourceClient",
    "DeezerClient",
    "YouTubeMusicClient",
    "get_ytmusic_client",
    "get_deezer_client",
    "reset_clients",
]
