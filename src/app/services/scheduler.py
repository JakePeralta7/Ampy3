"""APScheduler service for managing scheduled playlist syncs."""

from __future__ import annotations

import logging
from datetime import datetime

from apscheduler.schedulers.asyncio import AsyncIOScheduler
from apscheduler.triggers.interval import IntervalTrigger
from sqlalchemy import select
from sqlalchemy.orm import selectinload

from src.app.constants import INTERVAL_DELTAS
from src.app.db import AsyncSessionLocal
from src.app.models import ScheduledPlaylistSync
from src.app.services.base import ServiceBase
from src.app.worker.tasks import sync_playlists_task

logger = logging.getLogger(__name__)


class SchedulerService(ServiceBase):
    """Service for managing APScheduler instance and scheduled tasks.

    The singleton instance IS the ``AsyncIOScheduler``.  Use
    ``SchedulerService.get_instance()`` to get it, and ``start()`` /
    ``stop()`` to manage its lifecycle.
    """

    _instance: AsyncIOScheduler | None = None

    @classmethod
    def create(cls) -> AsyncIOScheduler:
        return AsyncIOScheduler()

    @classmethod
    async def create_async(cls) -> AsyncIOScheduler:
        return cls.create()

    @classmethod
    async def start(cls) -> None:
        """Start the scheduler and load scheduled syncs from database."""
        scheduler = cls.get_instance()

        if scheduler.running:
            logger.warning("Scheduler is already running")
            return

        try:
            scheduler.start()
            logger.info("APScheduler started")
            await cls.reload_schedules()
        except Exception as e:
            logger.error("Failed to start scheduler: %s", e)
            raise

    @classmethod
    async def stop(cls) -> None:
        """Stop the scheduler gracefully."""
        scheduler = cls.get_instance()

        if not scheduler.running:
            logger.warning("Scheduler is not running")
            return

        try:
            scheduler.shutdown()
            logger.info("APScheduler stopped")
        except Exception as e:
            logger.error("Failed to stop scheduler: %s", e)
            raise

    @classmethod
    async def reload_schedules(cls) -> None:
        """Load all active scheduled syncs from database and register them."""
        scheduler = cls.get_instance()
        scheduler.remove_all_jobs()
        logger.info("Cleared all existing scheduled jobs")

        try:
            async with AsyncSessionLocal() as session:
                stmt = (
                    select(ScheduledPlaylistSync)
                    .where(ScheduledPlaylistSync.is_active)
                    .options(selectinload(ScheduledPlaylistSync.schedule_targets))
                )
                result = await session.execute(stmt)
                syncs = result.scalars().all()

                logger.info("Found %d active scheduled syncs", len(syncs))

                for sync in syncs:
                    await cls._register_sync(scheduler, sync)
        except Exception as e:
            logger.error("Failed to reload schedules: %s", e)
            raise

    @classmethod
    async def _register_sync(cls, scheduler: AsyncIOScheduler, sync: ScheduledPlaylistSync) -> None:
        """Register a single sync with the scheduler."""
        job_id = f"sync_{sync.id}"
        target_ids = sync.target_ids

        try:
            trigger = cls._get_trigger(sync.schedule_interval, sync.next_sync_at)

            scheduler.add_job(
                cls._dispatch_targets,
                trigger=trigger,
                id=job_id,
                name=f"Sync: {sync.target_playlist_name}",
                kwargs={
                    "sync_id": sync.id,
                    "source_url": sync.source_url,
                    "source": sync.source,
                    "target_ids": target_ids,
                    "target_playlist_name": sync.target_playlist_name,
                },
                replace_existing=True,
                max_instances=1,
            )

            logger.info(
                "Registered job %s: %s (%s, targets=%s)",
                job_id,
                sync.target_playlist_name,
                sync.schedule_interval,
                target_ids,
            )
        except Exception as e:
            logger.error("Failed to register sync %d: %s", sync.id, e)
            raise

    @staticmethod
    def _dispatch_targets(
        sync_id: int,
        source_url: str,
        source: str,
        target_ids: list[str],
        target_playlist_name: str,
    ) -> None:
        """Dispatch a single sync_playlists_task with all targets."""
        sync_playlists_task.delay(
            playlist_url=source_url,
            source=source,
            target_ids=target_ids,
            schedule_id=sync_id,
            target_playlist_name=target_playlist_name,
        )

    @classmethod
    async def trigger_sync_now(cls, sync: ScheduledPlaylistSync) -> None:
        """Immediately dispatch a sync for the given schedule with all targets."""
        sync_playlists_task.delay(
            playlist_url=sync.source_url,
            source=sync.source,
            target_ids=sync.target_ids,
            schedule_id=sync.id,
            target_playlist_name=sync.target_playlist_name,
        )

    @staticmethod
    def _get_trigger(schedule_interval: str, next_sync_at: datetime) -> IntervalTrigger:
        """Get appropriate APScheduler trigger based on interval type."""
        delta = INTERVAL_DELTAS.get(schedule_interval)
        if delta is not None:
            total_hours = int(delta.total_seconds() // 3600)
            if total_hours >= 24 and total_hours % 24 == 0:
                return IntervalTrigger(days=int(total_hours // 24), start_date=next_sync_at)
            return IntervalTrigger(hours=total_hours, start_date=next_sync_at)
        raise ValueError(f"Unsupported schedule interval: {schedule_interval}")
