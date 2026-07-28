"""Valkey/Redis cache service."""

import logging
from typing import Any

import valkey as valkey_sync
import valkey.asyncio as valkey_async

from src.app.services.base import ServiceBase
from src.app.settings import settings

logger = logging.getLogger(__name__)


class ValkeyService(ServiceBase):
    """Service for managing Valkey/Redis client instances.

    Provides two singleton clients:
    * ``get_instance()`` — async ``valkey.asyncio.Valkey`` (for FastAPI)
    * ``get_sync_instance()`` — sync ``valkey.Valkey`` (for Celery workers)

    The sync client is not bound to any event loop, so it works correctly
    when used inside ``asyncio.run()`` calls that create temporary loops.
    """

    _instance: Any = None
    _sync_instance: Any = None

    @classmethod
    def create(cls) -> valkey_async.Valkey:
        url = settings.celery_broker_url.replace("redis://", "valkey://")
        instance = valkey_async.from_url(url, decode_responses=True)
        logger.debug("Valkey async client initialized")
        return instance

    @classmethod
    def get_sync_instance(cls) -> valkey_sync.Valkey:
        if cls._sync_instance is None:
            url = settings.celery_broker_url.replace("redis://", "valkey://")
            cls._sync_instance = valkey_sync.from_url(url, decode_responses=True)
            logger.debug("Valkey sync client initialized")
        return cls._sync_instance

    @classmethod
    def reset(cls) -> None:
        cls._instance = None
        cls._sync_instance = None
        logger.info("Reset ValkeyService")
