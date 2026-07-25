"""Jellyfin service."""

import logging

from src.app.services.base import ServiceBase

logger = logging.getLogger(__name__)


class JellyfinService(ServiceBase):
    @classmethod
    def create(cls):
        raise NotImplementedError("Use create_async() for JellyfinService")

    @classmethod
    async def create_async(cls):
        from sqlalchemy import select

        from src.app.core.jellyfin.client import JellyfinClient
        from src.app.db import AsyncSessionLocal
        from src.app.models import Config

        async with AsyncSessionLocal() as session:
            result = await session.execute(
                select(Config).where(
                    Config.key.in_(
                        [
                            "jellyfin_server_url",
                            "jellyfin_api_key",
                            "jellyfin_user_id",
                        ]
                    )
                )
            )
            rows = {row.key: row.value for row in result.scalars().all()}

        server_url = rows.get("jellyfin_server_url", "").strip()
        api_key = rows.get("jellyfin_api_key", "").strip()
        user_id = rows.get("jellyfin_user_id", "").strip()

        if not server_url or not api_key or not user_id:
            raise RuntimeError(
                "Jellyfin target not configured. Set jellyfin_server_url, jellyfin_api_key, "
                "and jellyfin_user_id in Settings."
            )

        client = JellyfinClient(api_key=api_key, base_url=server_url, user_id=user_id)
        logger.debug("Initialized JellyfinClient with server %s", server_url)
        return client
