"""Sync task status endpoint."""

import asyncio
import logging
from typing import Any

from fastapi import APIRouter, Depends, HTTPException
from sqlalchemy import select

from src.app.auth.dependencies import get_current_user
from src.app.models import ScheduledPlaylistSync

logger = logging.getLogger(__name__)

router = APIRouter()


async def _celery_task_is_pending(task_id: str) -> bool:
    """True when the Celery backend does not know the task (yet).

    Used as a fallback when the ``task_id → sync_id`` mapping is missing: the
    task may simply not have been picked up by a worker yet, in which case the
    mapping was never written.
    """
    from . import get_sync_status_task

    try:
        status = await asyncio.to_thread(get_sync_status_task, task_id)
    except Exception as e:
        logger.warning("Failed to read Celery status for task %s: %s", task_id, e)
        return False
    return status.get("status") == "PENDING"


@router.get("/status/{task_id}")
async def get_sync_status(
    task_id: str,
    _user: dict[str, Any] = Depends(get_current_user),  # noqa: B008
):
    """Poll the Celery backend for sync job status and result."""
    from . import get_sync_id_for_task_async, get_sync_status_task

    # Look up sync_id from task_id
    sync_id = await get_sync_id_for_task_async(task_id)
    if not sync_id:
        # The task may not have been picked up by a worker yet, so its mapping
        # does not exist. Report "pending" instead of 404 — a client that
        # starts polling right after the request must keep polling.
        if await _celery_task_is_pending(task_id):
            return {"task_id": task_id, "status": "PENDING", "ready": False, "result": None}

        # Mapping lost (e.g., Valkey restart). Try to get ownership from Celery task result.
        try:
            task_status = await asyncio.to_thread(get_sync_status_task, task_id)
            if task_status.get("ready") and task_status.get("result"):
                result = task_status["result"]
                # Check if result contains user_id or sync_id for ownership verification
                if isinstance(result, dict):
                    result_sync_id = result.get("sync_id")
                    result_user_id = result.get("user_id")
                    if result_sync_id and result_user_id == _user["plex_user_id"]:
                        return task_status
        except Exception:
            pass

        raise HTTPException(status_code=404, detail="Task not found")

    # Verify user owns this sync
    from src.app.api.syncs import AsyncSessionLocal

    async with AsyncSessionLocal() as session:
        sync = await session.execute(
            select(ScheduledPlaylistSync).where(ScheduledPlaylistSync.id == sync_id)
        )
        sync_record = sync.scalar_one_or_none()
        if not sync_record or sync_record.user_id != _user["plex_user_id"]:
            raise HTTPException(status_code=404, detail="Task not found")

    return await asyncio.to_thread(get_sync_status_task, task_id)
