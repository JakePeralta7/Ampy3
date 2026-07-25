"""Valkey/Redis cache service."""

import logging

import valkey.asyncio as valkey_async

from src.app.services.base import ServiceBase
from src.app.settings import settings

logger = logging.getLogger(__name__)


class ValkeyService(ServiceBase):
    """Service for managing Valkey/Redis client instance."""

    @classmethod
    def create(cls) -> valkey_async.Valkey:
        url = settings.celery_broker_url.replace("redis://", "valkey://")
        instance = valkey_async.from_url(url, decode_responses=True)
        logger.debug("Valkey client initialized")
        return instance
