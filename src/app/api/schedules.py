"""Scheduled syncs endpoints — CRUD and ad-hoc actions."""

import logging
from datetime import UTC, datetime, timedelta
from typing import Any

from fastapi import APIRouter, Depends, HTTPException, Query, status
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy.orm import selectinload

from src.app.auth.dependencies import get_current_user
from src.app.constants import SOURCE_YOUTUBE_MUSIC
from src.app.core.sources.ytmusic import YouTubeMusicSource
from src.app.db import get_async_session
from src.app.models import (
    PlaylistSourceEnum,
    ScheduledPlaylistSync,
    ScheduleIntervalEnum,
    ScheduleTarget,
)
from src.app.schemas.common import DeleteResponse
from src.app.schemas.schedules import (
    BulkDeleteInput,
    BulkResponse,
    BulkSyncNowInput,
    BulkToggleActiveInput,
    CreateScheduledSyncInput,
    ScheduledSyncOut,
    SchedulerReloadResponse,
    SyncNowResponse,
    UpdateScheduledSyncInput,
)
from src.app.services import list_sync_targets
from src.app.services.audit import log_event

logger = logging.getLogger(__name__)

router = APIRouter(prefix="/api/v1/schedules", tags=["schedules"])


def _sync_to_out(model: ScheduledPlaylistSync) -> ScheduledSyncOut:
    # Check if any run for this sync is currently running
    running_run = next((r for r in model.runs if r.status == "running"), None)
    return ScheduledSyncOut(
        id=model.id,
        source=model.source,
        target_ids=model.target_ids,
        source_url=model.source_url,
        target_playlist_name=model.target_playlist_name,
        schedule_interval=model.schedule_interval,
        is_active=model.is_active,
        last_synced_at=model.last_synced_at.isoformat() if model.last_synced_at else None,
        next_sync_at=model.next_sync_at.isoformat() if model.next_sync_at else None,
        created_at=model.created_at.isoformat() if model.created_at else None,
        updated_at=model.updated_at.isoformat() if model.updated_at else None,
        error_message=model.error_message,
        status="running" if running_run else None,
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
    db: AsyncSession = Depends(get_async_session),  # noqa: B008
    _user: dict[str, Any] = Depends(get_current_user),  # noqa: B008
):
    """Create a new scheduled playlist sync."""
    if body.source not in [e.value for e in PlaylistSourceEnum]:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail=f"Invalid source. Must be one of: {[e.value for e in PlaylistSourceEnum]}",
        )
    if body.source == SOURCE_YOUTUBE_MUSIC and not YouTubeMusicSource.is_valid_url(body.source_url):
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="Invalid YouTube Music source URL. Must be a valid "
            "https://music.youtube.com/playlist?list=... URL.",
        )
    if body.schedule_interval not in [e.value for e in ScheduleIntervalEnum]:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail=(
                "Invalid schedule_interval. Must be one of: "
                f"{[e.value for e in ScheduleIntervalEnum]}"
            ),
        )

    valid_targets = {t["id"] for t in await list_sync_targets()}
    for tid in body.target_ids:
        if tid not in valid_targets:
            raise HTTPException(
                status_code=status.HTTP_400_BAD_REQUEST,
                detail=f"Invalid target_id '{tid}'. Must be one of: {sorted(valid_targets)}",
            )

    db_sync = ScheduledPlaylistSync(
        source=body.source,
        source_url=body.source_url,
        target_playlist_name=body.target_playlist_name,
        schedule_interval=body.schedule_interval,
        next_sync_at=_calculate_next_sync(body.schedule_interval),
    )
    db.add(db_sync)
    await db.flush()

    for tid in body.target_ids:
        db.add(ScheduleTarget(sync_id=db_sync.id, target_id=tid))

    await db.commit()

    result = await db.execute(
        select(ScheduledPlaylistSync)
        .where(ScheduledPlaylistSync.id == db_sync.id)
        .options(
            selectinload(ScheduledPlaylistSync.schedule_targets),
            selectinload(ScheduledPlaylistSync.runs),
        )
    )
    db_sync = result.scalar_one()

    from src.app.services.scheduler import SchedulerService

    try:
        await SchedulerService.reload_schedules()
        await SchedulerService.trigger_sync_now(db_sync)
    except Exception:
        logger.exception(
            "Failed to reload/trigger scheduler after creating schedule %s", db_sync.id
        )

    await log_event(
        event_type="schedule.created",
        resource_type="schedule",
        resource_id=str(db_sync.id),
        summary=(
            f"Schedule created — {body.source} → {', '.join(body.target_ids)} / "
            f"{db_sync.target_playlist_name}, "
            f"every {body.schedule_interval}"
        ),
    )

    result = _sync_to_out(db_sync)
    return result


@router.get("/", response_model=list[ScheduledSyncOut])
async def list_scheduled_syncs(
    db: AsyncSession = Depends(get_async_session),  # noqa: B008
    active_only: bool = Query(False, description="Filter by active schedules only"),
    _user: dict[str, Any] = Depends(get_current_user),  # noqa: B008
):
    """List all scheduled syncs, optionally filtered to active only."""
    query = select(ScheduledPlaylistSync).options(
        selectinload(ScheduledPlaylistSync.schedule_targets),
        selectinload(ScheduledPlaylistSync.runs),
    )
    if active_only:
        query = query.where(ScheduledPlaylistSync.is_active)
    query = query.order_by(ScheduledPlaylistSync.created_at.desc())
    result = await db.execute(query)
    return [_sync_to_out(s) for s in result.scalars().all()]


@router.get("/{sync_id}", response_model=ScheduledSyncOut)
async def get_scheduled_sync(
    sync_id: int,
    db: AsyncSession = Depends(get_async_session),  # noqa: B008
    _user: dict[str, Any] = Depends(get_current_user),  # noqa: B008
):
    """Get a specific scheduled sync by ID."""
    result = await db.execute(
        select(ScheduledPlaylistSync)
        .where(ScheduledPlaylistSync.id == sync_id)
        .options(selectinload(ScheduledPlaylistSync.schedule_targets)),
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
    db: AsyncSession = Depends(get_async_session),  # noqa: B008
    _user: dict[str, Any] = Depends(get_current_user),  # noqa: B008
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

    if body.schedule_interval is not None and body.schedule_interval not in [
        e.value for e in ScheduleIntervalEnum
    ]:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail=(
                "Invalid schedule_interval. Must be one of: "
                f"{[e.value for e in ScheduleIntervalEnum]}"
            ),
        )

    if body.target_ids is not None:
        valid_targets = {t["id"] for t in await list_sync_targets()}
        for tid in body.target_ids:
            if tid not in valid_targets:
                raise HTTPException(
                    status_code=status.HTTP_400_BAD_REQUEST,
                    detail=f"Invalid target_id '{tid}'. Must be one of: {sorted(valid_targets)}",
                )

        # Replace targets in junction table
        existing_targets = await db.execute(
            select(ScheduleTarget).where(ScheduleTarget.sync_id == sync_id)
        )
        for st in existing_targets.scalars().all():
            await db.delete(st)
        for tid in body.target_ids:
            db.add(ScheduleTarget(sync_id=sync_id, target_id=tid))

    simple_fields = ["target_playlist_name", "schedule_interval", "is_active"]
    for field in simple_fields:
        value = getattr(body, field, None)
        if value is not None:
            setattr(sync, field, value)

    if body.schedule_interval is not None:
        sync.next_sync_at = _calculate_next_sync(body.schedule_interval)

    await db.commit()

    result = await db.execute(
        select(ScheduledPlaylistSync)
        .where(ScheduledPlaylistSync.id == sync_id)
        .options(selectinload(ScheduledPlaylistSync.schedule_targets))
    )
    sync = result.scalar_one()

    changed = [k for k, v in body.model_dump(exclude_unset=True).items() if v is not None]
    await log_event(
        event_type="schedule.updated",
        resource_type="schedule",
        resource_id=str(sync_id),
        summary=f"Schedule '{sync.target_playlist_name}' updated — changed: {', '.join(changed)}",
    )

    return _sync_to_out(sync)


@router.delete("/{sync_id}", response_model=DeleteResponse)
async def delete_scheduled_sync(
    sync_id: int,
    db: AsyncSession = Depends(get_async_session),  # noqa: B008
    _user: dict[str, Any] = Depends(get_current_user),  # noqa: B008
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
        summary=f"Schedule '{sync.target_playlist_name}' deleted",
    )

    return DeleteResponse(id=sync_id)


# ─── Bulk actions ────────────────────────────────────────────────
# These must be defined before /{sync_id} routes.


@router.post("/bulk/sync-now", response_model=BulkResponse)
async def bulk_sync_now(
    body: BulkSyncNowInput,
    db: AsyncSession = Depends(get_async_session),  # noqa: B008
    _user: dict[str, Any] = Depends(get_current_user),  # noqa: B008
):
    """Trigger an immediate sync for multiple scheduled syncs."""
    from src.app.services.scheduler import SchedulerService

    result = await db.execute(
        select(ScheduledPlaylistSync).where(ScheduledPlaylistSync.id.in_(body.ids)),
    )
    syncs = {s.id: s for s in result.scalars().all()}

    found_ids = list(syncs.keys())
    if not found_ids:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="No matching schedules found for the provided IDs",
        )

    task_ids = []
    for sync_id in found_ids:
        task_ids.append(f"schedule_{sync_id}")

    await SchedulerService.reload_schedules()

    await log_event(
        event_type="sync.bulk_triggered",
        resource_type="schedule",
        summary=(
            f"Bulk sync triggered for {len(found_ids)} schedule(s): "
            f"{', '.join(s.target_playlist_name for s in syncs.values())}"
        ),
    )

    return BulkResponse(processed=len(found_ids), task_ids=task_ids)


@router.post("/bulk/toggle-active", response_model=BulkResponse)
async def bulk_toggle_active(
    body: BulkToggleActiveInput,
    db: AsyncSession = Depends(get_async_session),  # noqa: B008
    _user: dict[str, Any] = Depends(get_current_user),  # noqa: B008
):
    """Pause or resume multiple scheduled syncs."""
    result = await db.execute(
        select(ScheduledPlaylistSync).where(ScheduledPlaylistSync.id.in_(body.ids)),
    )
    syncs = result.scalars().all()

    if not syncs:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="No matching schedules found for the provided IDs",
        )

    for sync in syncs:
        sync.is_active = body.is_active
    await db.commit()

    names = [s.target_playlist_name for s in syncs]
    action = "resumed" if body.is_active else "paused"
    await log_event(
        event_type="schedule.bulk_updated",
        resource_type="schedule",
        summary=f"Bulk {action} {len(syncs)} schedule(s): {', '.join(names)}",
    )

    return BulkResponse(processed=len(syncs))


@router.post("/bulk/delete", response_model=BulkResponse)
async def bulk_delete(
    body: BulkDeleteInput,
    db: AsyncSession = Depends(get_async_session),  # noqa: B008
    _user: dict[str, Any] = Depends(get_current_user),  # noqa: B008
):
    """Delete multiple scheduled syncs."""
    result = await db.execute(
        select(ScheduledPlaylistSync).where(ScheduledPlaylistSync.id.in_(body.ids)),
    )
    syncs = result.scalars().all()

    if not syncs:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="No matching schedules found for the provided IDs",
        )

    names = [s.target_playlist_name for s in syncs]
    for sync in syncs:
        await db.delete(sync)
    await db.commit()

    await log_event(
        event_type="schedule.bulk_deleted",
        resource_type="schedule",
        summary=f"Bulk deleted {len(syncs)} schedule(s): {', '.join(names)}",
    )

    return BulkResponse(processed=len(syncs))


# ─── Actions ─────────────────────────────────────────────────────


@router.post("/{sync_id}/sync-now", response_model=SyncNowResponse)
async def trigger_sync_now(
    sync_id: int,
    db: AsyncSession = Depends(get_async_session),  # noqa: B008
    _user: dict[str, Any] = Depends(get_current_user),  # noqa: B008
):
    """Manually trigger an immediate sync for a scheduled sync."""
    result = await db.execute(
        select(ScheduledPlaylistSync)
        .where(ScheduledPlaylistSync.id == sync_id)
        .options(selectinload(ScheduledPlaylistSync.schedule_targets)),
    )
    sync = result.scalar_one_or_none()
    if not sync:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail=f"Scheduled sync with ID {sync_id} not found",
        )

    from src.app.services.scheduler import SchedulerService

    await SchedulerService.trigger_sync_now(sync)

    await log_event(
        event_type="sync.manually_triggered",
        resource_type="schedule",
        resource_id=str(sync_id),
        summary=f"Manual sync triggered for '{sync.target_playlist_name}'",
    )

    return SyncNowResponse(
        task_id=f"schedule_{sync_id}",
        message=f"Sync triggered for {sync.target_playlist_name}",
    )


@router.post("/scheduler/reload", response_model=SchedulerReloadResponse)
async def reload_scheduler(
    _user: dict[str, Any] = Depends(get_current_user),  # noqa: B008
):
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
        ) from e
