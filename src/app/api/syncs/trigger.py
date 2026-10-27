"""Sync trigger endpoint — initiating background sync jobs."""

import asyncio
import logging
import uuid
from datetime import UTC, datetime
from typing import Any

from fastapi import APIRouter, Depends, HTTPException
from sqlalchemy import select
from sqlalchemy.exc import IntegrityError

from src.app.auth.dependencies import get_current_user
from src.app.constants import (
    AD_HOC_INTERVAL,
    DEFAULT_SOURCE,
    SOURCE_DEEZER,
    SOURCE_YOUTUBE_MUSIC,
)
from src.app.core.sources.ytmusic import YouTubeMusicSource
from src.app.models import ScheduledPlaylistSync
from src.app.schemas.syncs import SyncTriggerRequest, SyncTriggerResponse
from src.app.services import get_sync_target
from src.app.services.audit import log_event
from src.app.services.websocket_manager import broadcast_sync_event
from src.app.worker.tasks import sync_playlists_task

logger = logging.getLogger(__name__)

router = APIRouter()


def _is_execution_id_conflict(exc: IntegrityError) -> bool:
    """True when an integrity failure is the idempotency unique index.

    Other integrity errors (foreign key violations, value overflows) must not
    be mistaken for an idempotency race — they need to surface as they are.
    """
    return "uq_sync_execution_per_user" in str(getattr(exc, "orig", exc))


async def _discard_unenqueued_sync(
    sync_id: int | None,
    schedule_id: int | None,
    previous_execution_id: str | None,
) -> None:
    """Undo the sync record created for a task that could not be enqueued.

    The record is created before the task is published so the idempotency
    constraint can be enforced in the API. If the publish fails the record
    would linger as a phantom sync: listed in the UI, never populated, never
    completed.
    """
    if sync_id is None:
        return
    try:
        from src.app.api.syncs import AsyncSessionLocal

        async with AsyncSessionLocal() as session:
            if schedule_id is None:
                # Ad-hoc sync: delete the record we created
                record = await session.get(ScheduledPlaylistSync, sync_id)
                if record is not None:
                    await session.delete(record)
            else:
                # Scheduled sync: restore the previous execution_id
                record = await session.get(ScheduledPlaylistSync, schedule_id)
                if record is not None:
                    record.execution_id = previous_execution_id
            await session.commit()
    except Exception as e:
        logger.warning("Failed to clean up sync %s after enqueue failure: %s", sync_id, e)


@router.post("/", response_model=SyncTriggerResponse)
async def trigger_sync(
    body: SyncTriggerRequest,
    _user: dict[str, Any] = Depends(get_current_user),  # noqa: B008
):
    """Initiate a background sync job for a playlist.

    Supports idempotency via execution_id parameter:
    - If execution_id provided and sync exists, returns 200 OK with existing sync
    - If execution_id provided but sync doesn't exist, creates new sync
    - If execution_id omitted, auto-generates UUID

    The key is scoped to the request target: a request carrying ``schedule_id``
    resolves against that schedule, an ad-hoc request against the ad-hoc sync
    it created. The same key can therefore be reused for a second schedule.
    """
    try:
        # Validate source
        valid_sources = {SOURCE_YOUTUBE_MUSIC, SOURCE_DEEZER}
        if body.source not in valid_sources:
            raise HTTPException(
                status_code=422,
                detail=f"Invalid source: {body.source}. Valid sources: {', '.join(valid_sources)}",
            )

        is_yt_music = body.source == DEFAULT_SOURCE and not YouTubeMusicSource.is_valid_url(
            body.playlist_url
        )
        if is_yt_music:
            raise HTTPException(
                status_code=422,
                detail="Invalid YouTube Music URL format. Must be a valid "
                "https://music.youtube.com/playlist?list=... URL.",
            )

        # Validate target_id
        from . import list_sync_targets

        available_targets = {t["id"] for t in await list_sync_targets()}
        if body.target_id not in available_targets:
            raise HTTPException(
                status_code=422,
                detail=(
                    f"Unknown target: {body.target_id}. "
                    f"Available targets: {', '.join(sorted(available_targets))}"
                ),
            )

        # ─ Idempotency Check & Sync Creation ────────────────────────────────
        # If execution_id provided, check for existing sync (idempotency)
        user_id = _user["plex_user_id"]
        execution_id = body.execution_id or uuid.uuid4().hex

        sync_id: int | None = None
        previous_execution_id: str | None = None

        # The idempotency key is scoped to the request target: a scheduled
        # request resolves against its own schedule row, an ad-hoc request
        # against the ad-hoc row it created. Without that scoping the same key
        # would resolve to whichever row happened to carry it, and a second
        # schedule would silently never run.
        if body.schedule_id is not None:
            existing_stmt = select(ScheduledPlaylistSync).where(
                ScheduledPlaylistSync.id == body.schedule_id,
                ScheduledPlaylistSync.user_id == user_id,
                ScheduledPlaylistSync.execution_id == execution_id,
            )
        else:
            existing_stmt = select(ScheduledPlaylistSync).where(
                ScheduledPlaylistSync.user_id == user_id,
                ScheduledPlaylistSync.execution_id == execution_id,
                ScheduledPlaylistSync.schedule_interval == AD_HOC_INTERVAL,
            )

        # Check for an existing sync with this execution_id
        from src.app.api.syncs import AsyncSessionLocal

        async with AsyncSessionLocal() as session:
            existing = await session.execute(existing_stmt)
            existing_sync = existing.scalar_one_or_none()

            if existing_sync:
                # Return existing sync (idempotent response)
                logger.info(
                    f"Idempotent sync request: execution_id={execution_id}, "
                    f"sync_id={existing_sync.id} (already exists)"
                )
                await log_event(
                    event_type="sync.idempotent_request",
                    resource_type="playlist",
                    resource_id=str(existing_sync.id),
                    summary=(
                        f"Sync request for {body.source} playlist (idempotent, sync already exists)"
                    ),
                    details={
                        "execution_id": execution_id,
                        "sync_id": existing_sync.id,
                        "playlist_url": body.playlist_url,
                    },
                )
                return SyncTriggerResponse(
                    message="Sync already exists (idempotent response)",
                    task_id=None,
                    status_url=None,
                    sync_id=existing_sync.id,
                )

            # No existing sync with this execution_id
            if body.schedule_id is not None:
                # Scheduled sync: verify the schedule exists and belongs to user
                schedule = await session.execute(
                    select(ScheduledPlaylistSync).where(
                        ScheduledPlaylistSync.id == body.schedule_id,
                        ScheduledPlaylistSync.user_id == user_id,
                    )
                )
                schedule_record = schedule.scalar_one_or_none()
                if not schedule_record:
                    raise HTTPException(status_code=404, detail="Schedule not found")
                # Persist the idempotency key on the schedule so a retried
                # request with the same execution_id resolves to this sync
                # instead of triggering a second run. The id is read before the
                # commit — expire_on_commit would otherwise turn the attribute
                # access into an implicit (non-awaitable) IO in the async session.
                sync_id = schedule_record.id
                previous_execution_id = schedule_record.execution_id
                schedule_record.execution_id = execution_id
                await session.commit()
            else:
                # Ad-hoc sync: create new sync record NOW (before enqueueing task)
                # This ensures the unique constraint on (user_id, execution_id) is
                # checked in the API handler, not in the worker
                new_sync = ScheduledPlaylistSync(
                    user_id=user_id,
                    source=body.source,
                    source_url=body.playlist_url,
                    target_playlist_name=body.target_playlist_name or body.playlist_url,
                    schedule_interval=AD_HOC_INTERVAL,
                    is_active=False,
                    next_sync_at=datetime.now(UTC),
                    execution_id=execution_id,
                )
                session.add(new_sync)
                try:
                    await session.flush()
                except IntegrityError as exc:
                    # Only the idempotency index is recoverable here. Any other
                    # integrity error (foreign key, value overflow) is a real
                    # failure and must not be reported as "already exists".
                    if not _is_execution_id_conflict(exc):
                        raise
                    # Race condition: another request created the same execution_id
                    await session.rollback()
                    existing = await session.execute(existing_stmt)
                    existing_sync = existing.scalar_one_or_none()
                    if existing_sync is None:
                        raise HTTPException(
                            status_code=409,
                            detail=(
                                "execution_id conflicts with an existing sync — "
                                "retry with a different key"
                            ),
                        ) from exc
                    logger.info(
                        f"Idempotent sync request (race): execution_id={execution_id}, "
                        f"sync_id={existing_sync.id} (already exists)"
                    )
                    await log_event(
                        event_type="sync.idempotent_request",
                        resource_type="playlist",
                        resource_id=str(existing_sync.id),
                        summary=(
                            f"Sync request for {body.source} playlist "
                            f"(idempotent, sync already exists)"
                        ),
                        details={
                            "execution_id": execution_id,
                            "sync_id": existing_sync.id,
                            "playlist_url": body.playlist_url,
                        },
                    )
                    return SyncTriggerResponse(
                        message="Sync already exists (idempotent response)",
                        task_id=None,
                        status_url=None,
                        sync_id=existing_sync.id,
                    )
                # Read the generated id *before* committing: expire_on_commit
                # would otherwise turn the attribute access into an implicit
                # (non-awaitable) IO in the async session.
                sync_id = new_sync.id
                # The session is closed when the block exits — without an
                # explicit commit the INSERT would be rolled back and the
                # worker would never find the record.
                await session.commit()
                logger.info(
                    f"Created ad-hoc sync record id={sync_id} with execution_id={execution_id}"
                )

        # Now enqueue the task with the sync_id
        try:
            task = sync_playlists_task.delay(
                playlist_url=body.playlist_url,
                source=body.source,
                target_ids=[body.target_id],
                schedule_id=body.schedule_id,
                target_playlist_name=body.target_playlist_name,
                execution_id=execution_id,
                user_id=user_id,
                sync_id=sync_id,
            )
        except Exception as exc:
            # The broker refused the task: undo the record created above so no
            # phantom sync is left behind.
            logger.error("Failed to enqueue sync task for sync %s: %s", sync_id, exc)
            await _discard_unenqueued_sync(
                sync_id=sync_id,
                schedule_id=body.schedule_id,
                previous_execution_id=previous_execution_id,
            )
            raise HTTPException(status_code=500, detail="Failed to start sync job") from exc

        # Register task → sync before answering. The worker registers the
        # mapping too, but only once it picks the task up; a client that polls
        # the status URL right away would otherwise get a 404.
        from . import register_sync_task_async

        await register_sync_task_async(sync_id, task.id)

        # Real-time update for this user's open WebSocket clients only.
        await broadcast_sync_event(
            user_id,
            "sync_started",
            {"sync_id": sync_id, "task_id": task.id, "source": body.source},
        )

        logger.info(
            f"Triggered sync task {task.id} for {body.source} playlist "
            f"(execution_id={execution_id}, sync_id={sync_id})"
        )

        await log_event(
            event_type="sync.manually_triggered",
            resource_type="playlist",
            resource_id=str(body.schedule_id) if body.schedule_id is not None else None,
            summary=f"Sync triggered for {body.source} playlist - {body.playlist_url}",
            details={
                "playlist_url": body.playlist_url,
                "source": body.source,
                "target_id": body.target_id,
                "schedule_id": body.schedule_id,
                "execution_id": execution_id,
                "sync_id": sync_id,
            },
        )

        return SyncTriggerResponse(
            message="Sync job started successfully.",
            task_id=task.id,
            status_url=f"/api/v1/syncs/status/{task.id}",
            sync_id=sync_id,
        )
    except HTTPException:
        raise
    except Exception as e:
        logger.error(f"Error triggering sync: {e}")
        raise HTTPException(status_code=500, detail="Failed to start sync job") from e
