"""Plex Media Server service."""
import logging

from src.app.services.base import ServiceBase

logger = logging.getLogger(__name__)


class PlexService(ServiceBase):
    """Service for managing Plex client instance (async initialization)."""

    @classmethod
    def create(cls):
        raise NotImplementedError("Use create_async() for PlexService")

    @classmethod
    async def create_async(cls):
        """Get or initialize Plex client instance.

        Reads the owner's token and server URL from the config table.
        """
        from src.app.auth.router import get_owner_plex_token, get_plex_server_url
        from src.app.core.plex.client import PlexClient

        token = await get_owner_plex_token()
        server_url = await get_plex_server_url()

        if not token or not server_url:
            raise RuntimeError("Plex server not configured. Complete the setup at /setup.")

        client = PlexClient(token=token, base_url=server_url)
        logger.info("Initialized PlexClient with server %s", server_url)
        return client
