"""Celery task definitions for playlist sync operations."""

import logging
from typing import Any

from celery import Celery
from sqlalchemy import select

from src.app.constants import DEFAULT_SOURCE, DEFAULT_TARGET
from src.app.models import SyncRun
from src.app.services.audit import log_event_sync
from src.app.services.sync_tasks import register_sync_task, unregister_sync_task
from src.app.worker.app import celery_app
from src.app.worker.context import SyncContext
from src.app.worker.errors import SyncScheduleMissingError
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

    try:
        title = target_playlist_name or playlist_url

        result = SyncPipeline.fetch_source(
            playlist_url,
            source,
            schedule_id,
            target_ids,
            playlist_title=title,
        )
        sync_id = result["sync_id"]
        track_items = result["track_items"]

        if not track_items:
            logger.info("No tracks to match for sync %d", sync_id)
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
            )
            register_sync_task(sync_id, child.id)

        if schedule_id is not None:
            unregister_sync_task(schedule_id, self.request.id)
        return {"status": "DISPATCHED", "sync_id": sync_id}
    except SyncScheduleMissingError as e:
        if schedule_id is not None:
            unregister_sync_task(schedule_id, self.request.id)
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
        if self.request.retries >= self.max_retries and schedule_id is not None:
            unregister_sync_task(schedule_id, self.request.id)
        raise self.retry(exc=e, countdown=60, max_retries=3) from e


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
):
    """Match all tracks, then finalize for one target."""
    register_sync_task(sync_id, self.request.id)
    ctx = SyncContext(
        sync_id=sync_id,
        target_id=target_id,
        playlist_title=playlist_title,
        source_url=playlist_url,
        source=source,
    )
    pipeline = SyncPipeline(ctx)

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
            logger.warning("Failed to mark SyncRun as failed: %s", db_exc)

        log_event_sync(
            event_type="sync.failed",
            resource_type="playlist",
            resource_id=resource_id,
            summary=f"Sync failed for {target_id}: {e} — {playlist_url}",
            details={"error": str(e), "target_id": target_id},
        )
        if self.request.retries >= self.max_retries:
            unregister_sync_task(sync_id, self.request.id)
        raise self.retry(exc=e, countdown=60, max_retries=3) from e


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
    return matcher.match(item_id or "")


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
