"""Plex Media Server service."""
import logging
from typing import Optional

logger = logging.getLogger(__name__)


class PlexService:
    """Service for managing Plex client instance."""

    _instance: object | None = None

    @classmethod
    async def get_client(cls):
        """Get or initialize Plex client instance (lazy singleton).

        Reads the owner's token and server URL from the config table.
        """
        if cls._instance is None:
            from src.app.auth.router import get_owner_plex_token, get_plex_server_url
            from src.app.core.plex.client import PlexClient

            token = await get_owner_plex_token()
            server_url = await get_plex_server_url()

            if not token or not server_url:
                raise RuntimeError("Plex server not configured. Complete the setup at /setup.")

            cls._instance = PlexClient(token=token, base_url=server_url)
            logger.info("Initialized PlexClient with server %s", server_url)
        return cls._instance

    @classmethod
    def reset(cls):
        """Reset Plex client instance."""
        cls._instance = None
        logger.info("Plex client reset")
