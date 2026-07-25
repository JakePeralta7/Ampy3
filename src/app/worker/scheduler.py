"""Scheduled sync management tasks for Celery."""

import logging
from datetime import UTC, datetime

from sqlalchemy import select

from src.app.core.services.matcher import get_active_rules_sync
from src.app.db import SessionLocal
from src.app.models import ScheduledPlaylistSync
from src.app.services.audit import log_event_sync
from src.app.worker.app import celery_app
from src.app.worker.sync_helpers import _execute_sync, _mark_sync_failed
from src.app.worker.tasks import _async_sync_task

logger = logging.getLogger(__name__)


@celery_app.task(bind=True)
def check_and_trigger_scheduled_syncs(self):
    try:
        now = datetime.now(UTC)
        logger.debug("Checking for scheduled syncs due at %s", now)

        db = SessionLocal()
        try:
            stmt = select(ScheduledPlaylistSync).where(
                (ScheduledPlaylistSync.is_active) & (ScheduledPlaylistSync.next_sync_at <= now)
            )
            result = db.execute(stmt)
            due_syncs = result.scalars().all()
            for sync in due_syncs:
                logger.debug("Triggering sync: %s (ID: %d)", sync.target_playlist_name, sync.id)
                scheduled_sync_task.delay(sync.id)
            return {"status": "SUCCESS", "syncs_triggered": len(due_syncs)}
        finally:
            db.close()
    except Exception as e:
        logger.error("Error in check_and_trigger_scheduled_syncs: %s", e, exc_info=True)
        raise


@celery_app.task(bind=True)
def scheduled_sync_task(self, schedule_id: int):
    logger.debug("Executing scheduled sync with ID: %d", schedule_id)

    db = SessionLocal()
    try:
        result = db.execute(
            select(ScheduledPlaylistSync).where(ScheduledPlaylistSync.id == schedule_id)
        )
        sync = result.scalar_one_or_none()
        if not sync:
            logger.error("Scheduled sync with ID %d not found", schedule_id)
            log_event_sync(
                event_type="sync.failed",
                resource_type="schedule",
                resource_id=str(schedule_id),
                summary=f"Scheduled sync #{schedule_id} failed — sync not found",
            )
            return {"status": "FAILED", "error": "Sync not found"}
        source_url, source, target_id, replace_existing, title = (
            sync.source_url,
            sync.source,
            getattr(sync, "target_id", "plex"),
            sync.replace_existing,
            sync.target_playlist_name,
        )
    finally:
        db.close()

    log_event_sync(
        event_type="sync.started",
        resource_type="schedule",
        resource_id=str(schedule_id),
        summary=f"Scheduled sync started for '{title}'",
    )

    rules = get_active_rules_sync()

    try:
        return _execute_sync(
            resource_type="schedule",
            resource_id=str(schedule_id),
            summary_prefix=f"Scheduled sync for '{title}'",
            coro_factory=lambda: _async_sync_task(
                source_url,
                source,
                target_id,
                replace_existing,
                schedule_id,
                rules,
                title,
            ),
        )
    except Exception as sync_error:
        _mark_sync_failed(schedule_id, str(sync_error))
        raise self.retry(exc=sync_error, countdown=300, max_retries=3) from sync_error
