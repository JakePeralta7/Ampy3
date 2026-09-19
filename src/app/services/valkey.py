"""Valkey/Redis cache service."""

import logging
from typing import Any

import valkey as valkey_sync
import valkey.asyncio as valkey_async

from src.app.services.base import ServiceBase
from src.app.settings import settings

logger = logging.getLogger(__name__)

# Lua script for atomic config fingerprint check-and-set.
# Returns (changed: int, status: str) where changed=1 means fingerprint was updated,
# changed=0 means unchanged. Status is one of: 'set', 'unchanged', 'changed'.
FINGERPRINT_SCRIPT = """
local key = KEYS[1]
local new_fp = ARGV[1]
local current = redis.call('GET', key)
if not current then
    redis.call('SET', key, new_fp)
    return {1, 'set'}
end
if current == new_fp then
    return {0, 'unchanged'}
end
redis.call('SET', key, new_fp)
return {1, 'changed'}
"""


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
    _fingerprint_script_sha: str | None = None

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
    async def _get_fingerprint_script_sha(cls) -> str:
        """Get or load the fingerprint Lua script SHA (cached)."""
        if cls._fingerprint_script_sha is None:
            client = cls.get_instance()
            cls._fingerprint_script_sha = await client.script_load(FINGERPRINT_SCRIPT)
        assert cls._fingerprint_script_sha is not None
        return cls._fingerprint_script_sha

    @classmethod
    async def check_and_update_fingerprint(cls, new_fp: str) -> tuple[bool, str]:
        """Atomically check and update the config fingerprint.

        Uses a Lua script to ensure atomicity: prevents thundering herd when
        multiple workers simultaneously detect a config change.

        Returns:
            (changed, status) where changed=True means fingerprint was updated,
            status is one of: 'set' (first write), 'unchanged', 'changed'.
        """
        client = cls.get_instance()
        sha = await cls._get_fingerprint_script_sha()
        try:
            result = await client.evalsha(sha, 1, "config:fingerprint", new_fp)
        except valkey_async.exceptions.NoScriptError:
            # Script was flushed from cache; reload and retry once
            cls._fingerprint_script_sha = None
            sha = await cls._get_fingerprint_script_sha()
            result = await client.evalsha(sha, 1, "config:fingerprint", new_fp)
        # result is [changed_int, status_str]
        return bool(result[0]), result[1]

    @classmethod
    def reset(cls) -> None:
        cls._instance = None
        cls._sync_instance = None
        cls._fingerprint_script_sha = None
        logger.info("Reset ValkeyService")
