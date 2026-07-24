"""Scheduled sync management tasks for Celery."""

import logging
from datetime import UTC, datetime

from sqlalchemy import select

from src.app.core.services.matcher import get_active_rules_sync
from src.app.db import SessionLocal
from src.app.models import ScheduledPlaylistSync
from src.app.services.audit import log_event_sync
from src.app.worker.app import celery_app
from src.app.worker.sync_helpers import _mark_sync_failed, _run_async
from src.app.worker.tasks import _async_sync_task

logger = logging.getLogger(__name__)


@celery_app.task(bind=True)
def check_and_trigger_scheduled_syncs(self):
    try:
        now = datetime.now(UTC)
        logger.debug(f"Checking for scheduled syncs due at {now}")

        db = SessionLocal()
        try:
            stmt = select(ScheduledPlaylistSync).where(
                (ScheduledPlaylistSync.is_active) &
                (ScheduledPlaylistSync.next_sync_at <= now)
            )
            result = db.execute(stmt)
            due_syncs = result.scalars().all()
            for sync in due_syncs:
                logger.debug(f"Triggering sync: {sync.target_playlist_name} (ID: {sync.id})")
                scheduled_sync_task.delay(sync.id)
            return {"status": "SUCCESS", "syncs_triggered": len(due_syncs)}
        finally:
            db.close()
    except Exception as e:
        logger.error(f"Error in check_and_trigger_scheduled_syncs: {e}", exc_info=True)
        raise


@celery_app.task(bind=True)
def scheduled_sync_task(self, schedule_id: int):
    logger.debug(f"Executing scheduled sync with ID: {schedule_id}")

    db = SessionLocal()
    try:
        result = db.execute(
            select(ScheduledPlaylistSync).where(ScheduledPlaylistSync.id == schedule_id)
        )
        sync = result.scalar_one_or_none()
        if not sync:
            logger.error(f"Scheduled sync with ID {schedule_id} not found")
            log_event_sync(
                event_type="sync.failed",
                resource_type="schedule",
                resource_id=str(schedule_id),
                summary=f"Scheduled sync #{schedule_id} failed — sync not found",
            )
            return {"status": "FAILED", "error": "Sync not found"}
        source_url, source, replace_existing, title = sync.source_url, sync.source, sync.replace_existing, sync.target_playlist_name
    finally:
        db.close()

    log_event_sync(
        event_type="sync.started",
        resource_type="schedule",
        resource_id=str(schedule_id),
        summary=f"Scheduled sync started for '{title}'",
    )

    logger.debug(f"Starting sync for: {title}")

    try:
        # Load rules synchronously FIRST to avoid asyncio.run() conflicts with asyncpg
        rules = get_active_rules_sync()
        # Pass a lambda that creates the coroutine, so _run_async can retry with a fresh coroutine
        stats = _run_async(lambda: _async_sync_task(source_url, source, replace_existing, schedule_id, rules))
        logger.debug(f"Sync successful for {title}: {stats}")
        log_event_sync(
            event_type="sync.completed",
            resource_type="schedule",
            resource_id=str(schedule_id),
            summary=f"Scheduled sync completed for '{title}': {stats.get('matched', 0)} matched, {stats.get('failed', 0)} failed",
            details=stats,
        )
        return {"status": "SUCCESS", "stats": stats}
    except Exception as sync_error:
        logger.error(f"Sync failed for {title}: {sync_error}", exc_info=True)
        _mark_sync_failed(schedule_id, str(sync_error))
        log_event_sync(
            event_type="sync.failed",
            resource_type="schedule",
            resource_id=str(schedule_id),
            summary=f"Scheduled sync failed for '{title}': {sync_error}",
            details={"error": str(sync_error)},
        )
        raise self.retry(exc=sync_error, countdown=300, max_retries=3) from sync_error
