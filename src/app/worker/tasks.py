"""Celery task definitions for playlist sync operations."""

import logging
import time
import uuid
from datetime import UTC, datetime
from typing import Any

from celery import Celery
from sqlalchemy import select

from src.app.constants import DEFAULT_SOURCE, DEFAULT_TARGET
from src.app.models import SyncRun
from src.app.services.audit import log_event_sync
from src.app.services.sync_tasks import (
    register_sync_task,
    set_fetch_phase,
    unregister_sync_task,
)
from src.app.worker.app import celery_app
from src.app.worker.context import SyncContext
from src.app.worker.errors import SyncScheduleMissingError
from src.app.worker.log import task_scope, update_log_context
from src.app.worker.matcher import TrackMatcher
from src.app.worker.pipeline import SyncPipeline

logger = logging.getLogger(__name__)


@celery_app.task(bind=True)
def sync_playlists_task(
    self,
    playlist_url: str,
    source: str = DEFAULT_SOURCE,
    target_ids: list[str] | None = None,
    schedule_id: int | None = None,
    target_playlist_name: str | None = None,
):
    """Fetch source playlist once, then dispatch per-target sync tasks."""
    if not target_ids:
        target_ids = [DEFAULT_TARGET]

    if schedule_id is not None:
        register_sync_task(schedule_id, self.request.id)

    resource_id = str(schedule_id) if schedule_id else None
    log_event_sync(
        event_type="sync.started",
        resource_type="playlist",
        resource_id=resource_id,
        summary=(
            f"Sync started for {source} playlist — {playlist_url} ({len(target_ids)} target(s))"
        ),
    )

    sync_id: int | None = None
    started_at: str | None = None
    execution_id = uuid.uuid4().hex

    with task_scope(
        # sync_id is not known until the fetch succeeds (line ~93); carry the
        # schedule_id here so early logs have some correlation, then update.
        task_id=self.request.id,
        task_name=self.name,
        sync_id=schedule_id,
        target_id=",".join(target_ids),
    ):
        t0 = time.monotonic()
        logger.info(
            "Sync started: source=%s url=%s targets=%d",
            source,
            playlist_url,
            len(target_ids),
        )

        try:
            title = target_playlist_name or playlist_url
            started_at = datetime.now(UTC).isoformat()
            if schedule_id is not None:
                set_fetch_phase(
                    schedule_id,
                    "running",
                    started_at=started_at,
                    execution_id=execution_id,
                )

            result = SyncPipeline.fetch_source(
                playlist_url,
                source,
                schedule_id,
                target_ids,
                playlist_title=title,
            )
            sync_id = result["sync_id"]
            update_log_context(sync_id=sync_id)
            track_items = result["track_items"]
            set_fetch_phase(
                sync_id,
                "completed",
                started_at=started_at,
                completed_at=datetime.now(UTC).isoformat(),
                execution_id=execution_id,
            )

            if not track_items:
                logger.info(
                    "No tracks to match for sync %d (Sync finished in %.2fs)",
                    sync_id,
                    time.monotonic() - t0,
                )
                if schedule_id is not None:
                    unregister_sync_task(schedule_id, self.request.id)
                return {"status": "SUCCESS", "stats": {"matched": 0, "failed": 0}}

            for tid in target_ids:
                child = sync_target_task.delay(
                    sync_id=sync_id,
                    target_id=tid,
                    playlist_title=result["playlist_title"],
                    track_rows=result["track_rows"],
                    track_items=track_items,
                    source=source,
                    playlist_url=playlist_url,
                    resource_id=resource_id,
                    execution_id=execution_id,
                )
                register_sync_task(sync_id, child.id)

            if schedule_id is not None:
                unregister_sync_task(schedule_id, self.request.id)
            logger.info(
                "Dispatched %d target task(s) for sync %d in %.2fs",
                len(target_ids),
                sync_id,
                time.monotonic() - t0,
            )
            return {"status": "DISPATCHED", "sync_id": sync_id}
        except SyncScheduleMissingError as e:
            if schedule_id is not None:
                unregister_sync_task(schedule_id, self.request.id)
            set_fetch_phase(
                schedule_id,
                "failed",
                started_at=started_at,
                completed_at=datetime.now(UTC).isoformat(),
                execution_id=execution_id,
            )
            logger.warning("Dropping task: %s", e)
            return {"status": "DROPPED", "sync_id": schedule_id}
        except Exception as e:
            log_event_sync(
                event_type="sync.failed",
                resource_type="playlist",
                resource_id=resource_id,
                summary=f"Sync failed: {e} — {playlist_url}",
                details={"error": str(e), "playlist_url": playlist_url},
            )
            attempt = self.request.retries + 1
            if self.request.retries >= self.max_retries:
                logger.error(
                    "Sync failed permanently after %d attempt(s): %s — %s",
                    attempt,
                    e,
                    playlist_url,
                    exc_info=True,
                )
                set_fetch_phase(
                    sync_id or schedule_id,
                    "failed",
                    started_at=started_at,
                    completed_at=datetime.now(UTC).isoformat(),
                    execution_id=execution_id,
                )
            else:
                logger.warning(
                    "Sync failed (attempt %d/%d), retrying in 60s: %s — %s",
                    attempt,
                    self.max_retries,
                    e,
                    playlist_url,
                    exc_info=True,
                )
            if self.request.retries >= self.max_retries and schedule_id is not None:
                unregister_sync_task(schedule_id, self.request.id)
            raise self.retry(exc=e, countdown=60) from e


@celery_app.task(bind=True)
def sync_target_task(
    self,
    sync_id: int,
    target_id: str = DEFAULT_TARGET,
    playlist_title: str = "",
    track_rows: list[dict[str, Any]] | None = None,
    track_items: list[str] | None = None,
    source: str = DEFAULT_SOURCE,
    playlist_url: str = "",
    resource_id: str | None = None,
    execution_id: str | None = None,
):
    """Match all tracks, then finalize for one target."""
    register_sync_task(sync_id, self.request.id)
    ctx = SyncContext(
        sync_id=sync_id,
        target_id=target_id,
        playlist_title=playlist_title,
        source_url=playlist_url,
        source=source,
        execution_id=execution_id,
    )
    pipeline = SyncPipeline(ctx)

    with task_scope(
        task_id=self.request.id,
        task_name=self.name,
        sync_id=sync_id,
        target_id=target_id,
    ):
        t0 = time.monotonic()
        logger.info(
            "Target sync started: sync_id=%d target=%s tracks=%d",
            sync_id,
            target_id,
            len(track_items or []),
        )
        try:
            stats = pipeline.run_target(track_rows or [], track_items or [])

            log_event_sync(
                event_type="sync.completed",
                resource_type="playlist",
                resource_id=resource_id,
                summary=(
                    f"Sync for {source} playlist — {playlist_url} ({target_id}): "
                    f"{stats.get('matched', 0)} matched, "
                    f"{stats.get('failed', 0)} failed"
                ),
                details=stats,
            )
            logger.info(
                "Target sync completed: sync_id=%d target=%s matched=%d failed=%d (%.2fs)",
                sync_id,
                target_id,
                stats.get("matched", 0),
                stats.get("failed", 0),
                time.monotonic() - t0,
            )
            unregister_sync_task(sync_id, self.request.id)
            return {"status": "SUCCESS", "stats": stats}
        except SyncScheduleMissingError as e:
            unregister_sync_task(sync_id, self.request.id)
            logger.warning("Dropping task: %s", e)
            return {"status": "DROPPED"}
        except Exception as e:
            try:
                with ctx.session() as db:
                    stmt = (
                        select(SyncRun)
                        .where(
                            SyncRun.sync_id == sync_id,
                            SyncRun.target_id == target_id,
                        )
                        .order_by(SyncRun.created_at.desc())
                        .limit(1)
                    )
                    run = db.execute(stmt).scalars().first()
                    if run:
                        run.status = "failed"
            except Exception as db_exc:
                logger.warning(
                    "Failed to mark SyncRun as failed: %s",
                    db_exc,
                    exc_info=True,
                )

            log_event_sync(
                event_type="sync.failed",
                resource_type="playlist",
                resource_id=resource_id,
                summary=f"Sync failed for {target_id}: {e} — {playlist_url}",
                details={"error": str(e), "target_id": target_id},
            )
            attempt = self.request.retries + 1
            if self.request.retries >= self.max_retries:
                logger.error(
                    "Target sync failed permanently: sync_id=%d target=%s after %d attempt(s): %s",
                    sync_id,
                    target_id,
                    attempt,
                    e,
                    exc_info=True,
                )
            else:
                logger.warning(
                    "Target sync failed (attempt %d/%d), retrying: sync_id=%d target=%s: %s",
                    attempt,
                    self.max_retries,
                    sync_id,
                    target_id,
                    e,
                    exc_info=True,
                )
            if self.request.retries >= self.max_retries:
                unregister_sync_task(sync_id, self.request.id)
            raise self.retry(exc=e, countdown=60) from e


@celery_app.task(bind=True)
def match_track_task(
    self,
    sync_id: int,
    target_id: str = DEFAULT_TARGET,
    item_id: str | None = None,
):
    """Match a single track (for manual re-match from the UI)."""
    ctx = SyncContext(sync_id=sync_id, target_id=target_id)
    matcher = TrackMatcher(ctx)

    with task_scope(
        task_id=self.request.id,
        task_name=self.name,
        sync_id=sync_id,
        target_id=target_id,
    ):
        logger.info(
            "Match request: sync_id=%d target=%s item=%s",
            sync_id,
            target_id,
            item_id or "",
        )
        try:
            result = matcher.match(item_id or "")
        except Exception as e:
            logger.error(
                "Match failed: sync_id=%d item=%s: %s",
                sync_id,
                item_id or "",
                e,
                exc_info=True,
            )
            raise
        logger.info("Match result: matched=%s item=%s", result.matched, item_id or "")
        return result


def get_sync_status_task(task_id: str):
    """Poll the Celery backend for task status and result."""
    from celery.result import AsyncResult

    result = AsyncResult(task_id, app=celery_app)
    return {
        "task_id": task_id,
        "status": result.state,
        "ready": result.ready(),
        "result": result.result if result.ready() else None,
    }
