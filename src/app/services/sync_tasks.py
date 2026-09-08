"""Registry of in-flight Celery sync tasks keyed by schedule.

Lets the API revoke every queued/running task for a schedule when the
schedule is deleted, instead of letting orphaned tasks crash on a
foreign-key violation later.
"""

import asyncio
import logging
from typing import Any

from src.app.services.valkey import ValkeyService

logger = logging.getLogger(__name__)

KEY_PREFIX = "ampy3:sync-tasks:"
KEY_TTL_SECONDS = 24 * 3600


def _key(sync_id: int) -> str:
    return f"{KEY_PREFIX}{sync_id}"


def _client() -> Any:
    return ValkeyService.get_sync_instance()


def register_sync_task(sync_id: int | None, task_id: str) -> None:
    """Track a Celery task under a schedule id so it can be revoked on delete."""
    if sync_id is None or not task_id:
        return
    try:
        client = _client()
        key = _key(sync_id)
        client.sadd(key, task_id)
        client.expire(key, KEY_TTL_SECONDS)
    except Exception as e:
        logger.warning("Failed to register task %s for sync %s: %s", task_id, sync_id, e)


def unregister_sync_task(sync_id: int | None, task_id: str) -> None:
    """Stop tracking a task once it has completed."""
    if sync_id is None or not task_id:
        return
    try:
        _client().srem(_key(sync_id), task_id)
    except Exception as e:
        logger.warning("Failed to unregister task %s for sync %s: %s", task_id, sync_id, e)


def _revoke_sync(sync_id: int) -> None:
    """Revoke and terminate all tracked tasks for a schedule (run off-loop)."""
    client = _client()
    key = _key(sync_id)
    task_ids = list(client.smembers(key) or [])
    if task_ids:
        from src.app.worker.app import celery_app

        celery_app.control.revoke(task_ids, terminate=True)
        logger.info("Revoked %d task(s) for sync %d", len(task_ids), sync_id)
    client.delete(key)


async def revoke_schedule_tasks(sync_id: int | None) -> None:
    """Cancel all queued/running tasks for a schedule (best effort).

    Never raises — a broker hiccup must not block deleting a schedule.
    """
    if sync_id is None:
        return
    try:
        await asyncio.to_thread(_revoke_sync, sync_id)
    except Exception as e:
        logger.warning("Failed to revoke tasks for sync %d: %s", sync_id, e)
