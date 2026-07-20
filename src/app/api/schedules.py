"""Scheduled syncs endpoints — CRUD and ad-hoc actions."""

import logging
from datetime import UTC, datetime, timedelta

from fastapi import APIRouter, Depends, HTTPException, Query, status
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from src.app.db import get_async_session
from src.app.models import PlaylistSourceEnum, ScheduledPlaylistSync, ScheduleIntervalEnum
from src.app.schemas.schedules import (
    CreateScheduledSyncInput,
    ScheduledSyncOut,
    SchedulerReloadResponse,
    SyncNowResponse,
    UpdateScheduledSyncInput,
)
from src.app.services.audit import log_event

logger = logging.getLogger(__name__)

router = APIRouter(prefix="/api/v1/schedules", tags=["scheduled-syncs"])


def _sync_to_out(model: ScheduledPlaylistSync) -> ScheduledSyncOut:
    return ScheduledSyncOut(
        id=model.id,
        source=model.source,
        source_url=model.source_url,
        plex_playlist_name=model.plex_playlist_name,
        plex_playlist_id=model.plex_playlist_id,
        schedule_interval=model.schedule_interval,
        is_active=model.is_active,
        replace_existing=model.replace_existing,
        last_synced_at=model.last_synced_at.isoformat() if model.last_synced_at else None,
        next_sync_at=model.next_sync_at.isoformat() if model.next_sync_at else None,
        created_at=model.created_at.isoformat() if model.created_at else None,
        updated_at=model.updated_at.isoformat() if model.updated_at else None,
        error_message=model.error_message,
    )


def _calculate_next_sync(interval: str) -> datetime:
    now = datetime.now(UTC)
    interval_map = {
        ScheduleIntervalEnum.EVERY_6H: timedelta(hours=6),
        ScheduleIntervalEnum.EVERY_12H: timedelta(hours=12),
        ScheduleIntervalEnum.EVERY_24H: timedelta(hours=24),
        ScheduleIntervalEnum.DAILY: timedelta(days=1),
        ScheduleIntervalEnum.WEEKLY: timedelta(weeks=1),
    }
    delta = interval_map.get(interval, timedelta(days=1))
    return now + delta


# ─── CRUD ────────────────────────────────────────────────────────


@router.post("/", response_model=ScheduledSyncOut, status_code=201)
async def create_scheduled_sync(
    body: CreateScheduledSyncInput,
    db: AsyncSession = Depends(get_async_session),
):
    """Create a new scheduled playlist sync."""
    if body.source not in [e.value for e in PlaylistSourceEnum]:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail=f"Invalid source. Must be one of: {[e.value for e in PlaylistSourceEnum]}",
        )
    if body.schedule_interval not in [e.value for e in ScheduleIntervalEnum]:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail=f"Invalid schedule_interval. Must be one of: {[e.value for e in ScheduleIntervalEnum]}",
        )

    db_sync = ScheduledPlaylistSync(
        source=body.source,
        source_url=body.source_url,
        plex_playlist_name=body.plex_playlist_name,
        schedule_interval=body.schedule_interval,
        replace_existing=body.replace_existing,
        next_sync_at=_calculate_next_sync(body.schedule_interval),
    )
    db.add(db_sync)
    await db.commit()
    await db.refresh(db_sync)

    from src.app.tasks import scheduled_sync_task

    task = scheduled_sync_task.delay(db_sync.id)

    await log_event(
        event_type="schedule.created",
        resource_type="schedule",
        resource_id=str(db_sync.id),
        summary=f"Schedule created — {body.source} → {db_sync.plex_playlist_name}, every {body.schedule_interval}",
    )

    result = _sync_to_out(db_sync)
    return result


@router.get("/", response_model=list[ScheduledSyncOut])
async def list_scheduled_syncs(
    db: AsyncSession = Depends(get_async_session),
    active_only: bool = Query(False, description="Filter by active schedules only"),
):
    """List all scheduled syncs, optionally filtered to active only."""
    query = select(ScheduledPlaylistSync)
    if active_only:
        query = query.where(ScheduledPlaylistSync.is_active)
    query = query.order_by(ScheduledPlaylistSync.created_at.desc())
    result = await db.execute(query)
    return [_sync_to_out(s) for s in result.scalars().all()]


@router.get("/{sync_id}", response_model=ScheduledSyncOut)
async def get_scheduled_sync(
    sync_id: int,
    db: AsyncSession = Depends(get_async_session),
):
    """Get a specific scheduled sync by ID."""
    result = await db.execute(
        select(ScheduledPlaylistSync).where(ScheduledPlaylistSync.id == sync_id),
    )
    sync = result.scalar_one_or_none()
    if not sync:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail=f"Scheduled sync with ID {sync_id} not found",
        )
    return _sync_to_out(sync)


@router.put("/{sync_id}", response_model=ScheduledSyncOut)
async def update_scheduled_sync(
    sync_id: int,
    body: UpdateScheduledSyncInput,
    db: AsyncSession = Depends(get_async_session),
):
    """Update a scheduled sync's configuration."""
    result = await db.execute(
        select(ScheduledPlaylistSync).where(ScheduledPlaylistSync.id == sync_id),
    )
    sync = result.scalar_one_or_none()
    if not sync:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail=f"Scheduled sync with ID {sync_id} not found",
        )

    if body.schedule_interval is not None and body.schedule_interval not in [e.value for e in ScheduleIntervalEnum]:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail=f"Invalid schedule_interval. Must be one of: {[e.value for e in ScheduleIntervalEnum]}",
        )

    for field, value in body.model_dump(exclude_unset=True).items():
        setattr(sync, field, value)
    if body.schedule_interval is not None:
        sync.next_sync_at = _calculate_next_sync(body.schedule_interval)

    await db.commit()
    await db.refresh(sync)

    changed = [k for k, v in body.model_dump(exclude_unset=True).items() if v is not None]
    await log_event(
        event_type="schedule.updated",
        resource_type="schedule",
        resource_id=str(sync_id),
        summary=f"Schedule '{sync.plex_playlist_name}' updated — changed: {', '.join(changed)}",
    )

    return _sync_to_out(sync)


@router.delete("/{sync_id}")
async def delete_scheduled_sync(
    sync_id: int,
    db: AsyncSession = Depends(get_async_session),
):
    """Delete a scheduled sync."""
    result = await db.execute(
        select(ScheduledPlaylistSync).where(ScheduledPlaylistSync.id == sync_id),
    )
    sync = result.scalar_one_or_none()
    if not sync:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail=f"Scheduled sync with ID {sync_id} not found",
        )
    await db.delete(sync)
    await db.commit()

    await log_event(
        event_type="schedule.deleted",
        resource_type="schedule",
        resource_id=str(sync_id),
        summary=f"Schedule '{sync.plex_playlist_name}' deleted",
    )

    return {"message": f"Scheduled sync with ID {sync_id} deleted successfully"}


# ─── Actions ─────────────────────────────────────────────────────


@router.post("/{sync_id}/sync-now", response_model=SyncNowResponse)
async def trigger_sync_now(
    sync_id: int,
    db: AsyncSession = Depends(get_async_session),
):
    """Manually trigger an immediate sync for a scheduled sync."""
    result = await db.execute(
        select(ScheduledPlaylistSync).where(ScheduledPlaylistSync.id == sync_id),
    )
    sync = result.scalar_one_or_none()
    if not sync:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail=f"Scheduled sync with ID {sync_id} not found",
        )
    from src.app.tasks import scheduled_sync_task

    task = scheduled_sync_task.delay(sync.id)

    await log_event(
        event_type="sync.manually_triggered",
        resource_type="schedule",
        resource_id=str(sync_id),
        summary=f"Manual sync triggered for '{sync.plex_playlist_name}'",
    )

    return SyncNowResponse(
        task_id=task.id,
        message=f"Sync triggered for {sync.plex_playlist_name}",
    )


@router.post("/scheduler/reload", response_model=SchedulerReloadResponse)
async def reload_scheduler():
    """Reload APScheduler with the latest schedule configuration."""
    from src.app.services.scheduler import SchedulerService

    try:
        await SchedulerService.reload_schedules()
        await log_event(
            event_type="scheduler.reloaded",
            summary="Scheduler reloaded with latest schedules",
        )
        return SchedulerReloadResponse(message="Scheduler reloaded successfully")
    except Exception as e:
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail=f"Failed to reload scheduler: {str(e)}",
        )
