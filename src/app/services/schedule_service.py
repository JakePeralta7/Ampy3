"""Shared data access and validation helpers for scheduled syncs.

The schedules API is intentionally thin: every route that needs a user-scoped
schedule row, a bulk lookup, interval/target validation, the next-run time, or
the API representation goes through this module so the rules live in one place.
"""

from __future__ import annotations

import logging
from datetime import UTC, datetime, timedelta

from fastapi import HTTPException, status
from sqlalchemy import Select, select
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy.orm import selectinload

from src.app.constants import INTERVAL_DELTAS, SOURCE_YOUTUBE_MUSIC
from src.app.core.sources.ytmusic import YouTubeMusicSource
from src.app.models import (
    PlaylistSourceEnum,
    ScheduledPlaylistSync,
    ScheduleIntervalEnum,
    ScheduleTarget,
)
from src.app.schemas.schedules import ScheduledSyncOut
from src.app.services import list_sync_targets

logger = logging.getLogger(__name__)


# ─── Validation ─────────────────────────────────────────────────


def validate_source(source: str, source_url: str) -> None:
    """Reject an unknown playlist source or a malformed source URL."""
    valid_sources = [e.value for e in PlaylistSourceEnum]
    if source not in valid_sources:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail=f"Invalid source. Must be one of: {valid_sources}",
        )
    if source == SOURCE_YOUTUBE_MUSIC and not YouTubeMusicSource.is_valid_url(source_url):
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="Invalid YouTube Music source URL. Must be a valid "
            "https://music.youtube.com/playlist?list=... URL.",
        )


def validate_interval(interval: str) -> None:
    """Reject an interval that is not a member of ``ScheduleIntervalEnum``."""
    valid_intervals = [e.value for e in ScheduleIntervalEnum]
    if interval not in valid_intervals:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail=f"Invalid schedule_interval. Must be one of: {valid_intervals}",
        )


async def validate_target_ids(target_ids: list[str]) -> None:
    """Reject any target id that is not a currently configured sync target."""
    valid_targets = {t["id"] for t in await list_sync_targets()}
    for target_id in target_ids:
        if target_id not in valid_targets:
            raise HTTPException(
                status_code=status.HTTP_400_BAD_REQUEST,
                detail=f"Invalid target_id '{target_id}'. Must be one of: {sorted(valid_targets)}",
            )


def calculate_next_sync(interval: str, *, now: datetime | None = None) -> datetime:
    """Return the next run time for *interval*.

    Raises ValueError if interval is not a known schedule interval.
    """
    delta = INTERVAL_DELTAS.get(interval)
    if delta is None:
        valid = ", ".join(sorted(INTERVAL_DELTAS.keys()))
        raise ValueError(f"Unknown schedule interval: '{interval}'. Valid intervals: {valid}")
    return (now or datetime.now(UTC)) + delta


# ─── Queries ────────────────────────────────────────────────────


def _schedule_query(
    *,
    user_id: str | None = None,
    with_targets: bool = True,
    with_runs: bool = True,
) -> Select:
    """Build a schedule select, optionally scoped to a user and eager-loaded."""
    query = select(ScheduledPlaylistSync)
    if user_id is not None:
        query = query.where(ScheduledPlaylistSync.user_id == user_id)
    if with_targets:
        query = query.options(selectinload(ScheduledPlaylistSync.schedule_targets))
    if with_runs:
        query = query.options(selectinload(ScheduledPlaylistSync.runs))
    return query


async def fetch_schedule(
    db: AsyncSession,
    sync_id: int,
    *,
    user_id: str | None = None,
    with_targets: bool = True,
    with_runs: bool = True,
) -> ScheduledPlaylistSync:
    """Load one schedule or raise 404 (scoped to *user_id* when given)."""
    result = await db.execute(
        _schedule_query(
            user_id=user_id,
            with_targets=with_targets,
            with_runs=with_runs,
        ).where(ScheduledPlaylistSync.id == sync_id)
    )
    sync = result.scalar_one_or_none()
    if not sync:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail=f"Scheduled sync with ID {sync_id} not found",
        )
    return sync


async def fetch_schedules(
    db: AsyncSession,
    sync_ids: list[int],
    *,
    user_id: str,
) -> list[ScheduledPlaylistSync]:
    """Load every schedule among *sync_ids* owned by *user_id*."""
    result = await db.execute(
        _schedule_query(user_id=user_id).where(ScheduledPlaylistSync.id.in_(sync_ids))
    )
    return list(result.scalars().all())


async def list_schedules(
    db: AsyncSession,
    *,
    user_id: str,
    active_only: bool = False,
) -> list[ScheduledPlaylistSync]:
    """List a user's schedules, newest first, optionally active-only."""
    query = _schedule_query(user_id=user_id)
    if active_only:
        query = query.where(ScheduledPlaylistSync.is_active)
    query = query.order_by(ScheduledPlaylistSync.created_at.desc())
    result = await db.execute(query)
    return list(result.scalars().all())


async def replace_schedule_targets(db: AsyncSession, sync_id: int, target_ids: list[str]) -> None:
    """Sync a schedule's target rows to exactly ``target_ids``.

    Only deselected targets are deleted and only new ones inserted, so a target
    that stays selected is never deleted and re-inserted in the same flush.
    SQLAlchemy flushes INSERTs before DELETEs, so that pattern would trip the
    ``uq_schedule_target`` unique constraint on the re-inserted row.
    """
    result = await db.execute(select(ScheduleTarget).where(ScheduleTarget.sync_id == sync_id))
    existing = {st.target_id: st for st in result.scalars().all()}
    desired = set(target_ids)

    for target_id, row in existing.items():
        if target_id not in desired:
            await db.delete(row)
    for target_id in desired:
        if target_id not in existing:
            db.add(ScheduleTarget(sync_id=sync_id, target_id=target_id))


# ─── Serialization ──────────────────────────────────────────────


def schedule_to_out(model: ScheduledPlaylistSync) -> ScheduledSyncOut:
    """Convert a schedule row (with runs loaded) to its API representation."""
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


__all__ = [
    "calculate_next_sync",
    "fetch_schedule",
    "fetch_schedules",
    "list_schedules",
    "replace_schedule_targets",
    "schedule_to_out",
    "validate_interval",
    "validate_source",
    "validate_target_ids",
]
