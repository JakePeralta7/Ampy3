"""Celery task definitions for playlist sync operations."""

import dataclasses
import logging
import random
import time
import uuid
from datetime import UTC, datetime
from typing import Any

from celery import Celery
from sqlalchemy import select

from src.app.constants import DEFAULT_SOURCE, DEFAULT_TARGET
from src.app.models import Config, SyncRun
from src.app.services.audit import log_event_sync
from src.app.services.config_fingerprint import _config_fingerprint
from src.app.services.sync_tasks import (
    register_sync_task,
    set_fetch_phase,
    unregister_sync_task,
)
from src.app.worker.app import celery_app
from src.app.worker.context import SyncContext
from src.app.worker.errors import (
    SyncScheduleMissingError,
    SyncTargetConnectionError,
    SyncValidationError,
)
from src.app.worker.log import task_scope, update_log_context
from src.app.worker.matcher import TrackMatcher
from src.app.worker.pipeline import SyncPipeline

logger = logging.getLogger(__name__)


def _verify_target_connection(ctx: SyncContext) -> None:
    """Pre-flight: verify the target is reachable before matching any tracks.

    Runs before the match phase so an unreachable target fails fast and is
    reported as a connection error instead of marking every track as failed.
    """
    from src.app.worker.session import run_async

    try:
        run_async(ctx.target.test_connection())
    except Exception as e:
        raise SyncTargetConnectionError(f"Target '{ctx.target_id}' connection failed: {e}") from e


def _record_failed_run(ctx: SyncContext, error: str) -> None:
    """Reuse or create the target's SyncRun and mark it failed with an error."""
    from src.app.models import SyncRun

    try:
        with ctx.session() as db:
            run = (
                db.execute(
                    select(SyncRun).where(
                        SyncRun.sync_id == ctx.sync_id,
                        SyncRun.target_id == ctx.target_id,
                        SyncRun.execution_id == ctx.execution_id,
                        SyncRun.status.in_(("running", "pending")),
                    )
                )
                .scalars()
                .first()
            )
            if run is None:
                run = SyncRun(
                    sync_id=ctx.sync_id,
                    target_id=ctx.target_id,
                    status="failed",
                    matched_count=0,
                    failed_count=0,
                    execution_id=ctx.execution_id,
                )
                db.add(run)
            run.status = "failed"
            run.error_message = error[:2000]
            db.flush()
    except Exception:
        logger.warning("Failed to record failed SyncRun", exc_info=True)


def _retry_countdown(completed_retries: int) -> int:
    """Exponential backoff with jitter for task retries.

    Capped at Celery soft_time_limit - 60s buffer to avoid exceeding time limits.
    """
    from src.app.worker.app import celery_app

    soft_limit = celery_app.conf.task_soft_time_limit or 3480
    max_backoff = max(60, soft_limit - 60)
    base = min(max_backoff, 60 * (2**completed_retries))
    return base + random.randint(0, 10)


@celery_app.task(bind=True, max_retries=3)
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
        except SyncValidationError as e:
            # Validation errors are permanent — do not retry
            log_event_sync(
                event_type="sync.failed",
                resource_type="playlist",
                resource_id=resource_id,
                summary=f"Sync validation failed: {e} — {playlist_url}",
                details={"error": str(e), "playlist_url": playlist_url},
            )
            logger.error("Sync validation error (non-retryable): %s — %s", e, playlist_url)
            if schedule_id is not None:
                unregister_sync_task(schedule_id, self.request.id)
            set_fetch_phase(
                schedule_id,
                "failed",
                started_at=started_at,
                completed_at=datetime.now(UTC).isoformat(),
                execution_id=execution_id,
            )
            return {"status": "VALIDATION_ERROR", "sync_id": schedule_id}
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
                if schedule_id is not None:
                    unregister_sync_task(schedule_id, self.request.id)
                raise
            logger.warning(
                "Sync failed (attempt %d/%d), retrying in ~%ds: %s — %s",
                attempt,
                self.max_retries,
                _retry_countdown(self.request.retries),
                e,
                playlist_url,
                exc_info=True,
            )
            raise self.retry(exc=e, countdown=_retry_countdown(self.request.retries)) from e


@celery_app.task(bind=True, max_retries=3)
def sync_target_task(
    self,
    sync_id: int,
    target_id: str = DEFAULT_TARGET,
    playlist_title: str = "",
    track_items: list[str] | None = None,
    source: str = DEFAULT_SOURCE,
    playlist_url: str = "",
    resource_id: str | None = None,
    execution_id: str | None = None,
):
    """Match all tracks, then finalize for one target."""
    from src.app.worker.session import run_async

    register_sync_task(sync_id, self.request.id)

    # Detect config changes the same way the pipeline does, but per-process.
    # The web API writes the Valkey fingerprint on every settings change, so a
    # worker comparing against that key would never notice a config change via
    # its own reads (the caching in TargetService hides it). Tracking the last
    # processed fingerprint here means the next task after a config change
    # rebuilds the target instance deliberately.
    try:
        from src.app.services.target import TargetService

        fp = _config_fingerprint()
        if fp != TargetService._processed_fp:
            TargetService.reset()
            TargetService._processed_fp = fp
            logger.info("Target config changed — reset cached target instances")
    except Exception as e:
        logger.warning("Config fingerprint check failed (resetting targets conservatively): %s", e)
        from src.app.services.target import TargetService

        TargetService.reset()
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
            if track_items:
                _verify_target_connection(ctx)

            stats = pipeline.run_target(track_items or [])

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
        except SyncTargetConnectionError as e:
            unregister_sync_task(sync_id, self.request.id)
            _record_failed_run(ctx, str(e))
            log_event_sync(
                event_type="sync.failed",
                resource_type="playlist",
                resource_id=resource_id,
                summary=f"Sync failed for {target_id}: target connection failed: {e}",
                details={"error": str(e), "target_id": target_id},
            )
            logger.error(
                "Target sync failed: sync_id=%d target=%s: %s",
                sync_id,
                target_id,
                e,
            )
            return {"status": "CONNECTION_FAILED", "sync_id": sync_id}
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
                        run.error_message = str(e)[:2000]
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
                    "Target sync failed (attempt %d/%d), retrying in ~%ds: "
                    "sync_id=%d target=%s: %s",
                    attempt,
                    self.max_retries,
                    _retry_countdown(self.request.retries),
                    sync_id,
                    target_id,
                    e,
                    exc_info=True,
                )
            if self.request.retries >= self.max_retries:
                unregister_sync_task(sync_id, self.request.id)
                raise
            raise self.retry(exc=e, countdown=_retry_countdown(self.request.retries)) from e


@celery_app.task(bind=True, max_retries=3)
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
        return dataclasses.asdict(result)


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
