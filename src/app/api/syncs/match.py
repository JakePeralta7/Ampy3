"""Sync match endpoint — dispatching manual match tasks."""

import logging
from typing import Any

from fastapi import APIRouter, Depends, HTTPException, Query
from sqlalchemy import select

from src.app.auth.dependencies import get_current_user
from src.app.constants import DEFAULT_TARGET
from src.app.models import ScheduledPlaylistSync
from src.app.schemas.syncs import MatchTrackInput, MatchTrackResponse
from src.app.services.sync_tasks import register_sync_task_async
from src.app.services.websocket_manager import broadcast_sync_event
from src.app.worker.tasks import match_track_task

logger = logging.getLogger(__name__)

router = APIRouter()


@router.post("/{sync_id}/match-track", response_model=MatchTrackResponse)
async def match_track(
    sync_id: int,
    body: MatchTrackInput,
    target_id: str = Query(default=DEFAULT_TARGET, description="Target platform ID"),
    item_id: str | None = Query(default=None, description="Source track item ID"),
    user: dict[str, Any] = Depends(get_current_user),  # noqa: B008
):
    """Dispatch a match task for a track via sync ID, running in a Celery worker."""
    try:
        from src.app.api.syncs import AsyncSessionLocal

        async with AsyncSessionLocal() as session:
            stmt = select(ScheduledPlaylistSync).where(ScheduledPlaylistSync.id == sync_id)
            result = await session.execute(stmt)
            sync_record = result.scalar_one_or_none()
            if not sync_record:
                raise HTTPException(status_code=404, detail=f"Sync {sync_id} not found")
            if sync_record.user_id != user["plex_user_id"]:
                raise HTTPException(status_code=404, detail=f"Sync {sync_id} not found")

        task = match_track_task.delay(
            sync_id=sync_id,
            item_id=item_id,
            target_id=target_id,
            user_id=user["plex_user_id"],
        )

        # Register task → sync before answering so the UI can resolve the
        # task status immediately, without waiting for a worker to pick it up.
        await register_sync_task_async(sync_id, task.id)

        # Real-time update for this user's open WebSocket clients only.
        await broadcast_sync_event(
            user["plex_user_id"],
            "match_queued",
            {"sync_id": sync_id, "item_id": item_id, "target_id": target_id},
        )

        return MatchTrackResponse(
            matched=False,
            message=f"Match queued for '{body.title}'",
            task_id=task.id,
        )
    except HTTPException:
        raise
    except Exception as e:
        logger.error(f"Error dispatching match for sync {sync_id}: {e}")
        raise HTTPException(status_code=500, detail="Failed to dispatch match") from e
