"""Valkey/Redis cache service."""
import logging

import valkey.asyncio as valkey_async

from src.app.settings import settings

logger = logging.getLogger(__name__)


class ValkeyService:
    """Service for managing Valkey/Redis client instance."""

    _instance: valkey_async.Valkey | None = None

    @classmethod
    def get_client(cls) -> valkey_async.Valkey:
        """Get or initialize Valkey/Redis client instance (lazy singleton)."""
        if cls._instance is None:
            url = settings.celery_broker_url.replace("redis://", "valkey://")
            cls._instance = valkey_async.from_url(url, decode_responses=True)
            logger.info("Valkey client initialized")
        return cls._instance

    @classmethod
    def reset(cls):
        """Reset Valkey client instance."""
        cls._instance = None
        logger.info("Valkey client reset")
