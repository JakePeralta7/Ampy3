"""APScheduler service for managing scheduled playlist syncs."""
import logging
from datetime import datetime, timedelta

from apscheduler.schedulers.asyncio import AsyncIOScheduler
from apscheduler.triggers.cron import CronTrigger
from apscheduler.triggers.interval import IntervalTrigger
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from src.app.db import AsyncSessionLocal
from src.app.models import ScheduledPlaylistSync
from src.app.tasks import sync_playlists_task

logger = logging.getLogger(__name__)


class SchedulerService:
    """Service for managing APScheduler instance and scheduled tasks."""

    _instance: AsyncIOScheduler | None = None

    @classmethod
    def get_scheduler(cls) -> AsyncIOScheduler:
        """Get or create scheduler instance."""
        if cls._instance is None:
            cls._instance = AsyncIOScheduler()
        return cls._instance

    @classmethod
    async def start(cls) -> None:
        """Start the scheduler and load scheduled syncs from database."""
        scheduler = cls.get_scheduler()

        if scheduler.running:
            logger.warning("Scheduler is already running")
            return

        try:
            scheduler.start()
            logger.info("APScheduler started")

            # Load all active scheduled syncs from database
            await cls.reload_schedules()
        except Exception as e:
            logger.error(f"Failed to start scheduler: {e}")
            raise

    @classmethod
    async def stop(cls) -> None:
        """Stop the scheduler gracefully."""
        scheduler = cls.get_scheduler()

        if not scheduler.running:
            logger.warning("Scheduler is not running")
            return

        try:
            scheduler.shutdown()
            logger.info("APScheduler stopped")
        except Exception as e:
            logger.error(f"Failed to stop scheduler: {e}")
            raise

    @classmethod
    async def reload_schedules(cls) -> None:
        """Load all active scheduled syncs from database and register them."""
        scheduler = cls.get_scheduler()

        # Remove all existing jobs
        scheduler.remove_all_jobs()
        logger.info("Cleared all existing scheduled jobs")

        try:
            async with AsyncSessionLocal() as session:
                stmt = select(ScheduledPlaylistSync).where(
                    ScheduledPlaylistSync.is_active
                )
                result = await session.execute(stmt)
                syncs = result.scalars().all()

                logger.info(f"Found {len(syncs)} active scheduled syncs")

                for sync in syncs:
                    await cls._register_sync(scheduler, sync)
        except Exception as e:
            logger.error(f"Failed to reload schedules: {e}")
            raise

    @classmethod
    async def _register_sync(cls, scheduler: AsyncIOScheduler, sync: ScheduledPlaylistSync) -> None:
        """Register a single sync with the scheduler."""
        job_id = f"sync_{sync.id}"

        try:
            trigger = cls._get_trigger(sync.schedule_interval, sync.next_sync_at)

            scheduler.add_job(
                sync_playlists_task.apply_async,
                trigger=trigger,
                id=job_id,
                name=f"Sync: {sync.plex_playlist_name}",
                kwargs={
                    "playlist_url": sync.source_url,
                    "source": sync.source,
                    "replace_existing": sync.replace_existing or False,
                },
                replace_existing=True,
                max_instances=1,
            )

            logger.info(f"Registered job {job_id}: {sync.plex_playlist_name} ({sync.schedule_interval})")
        except Exception as e:
            logger.error(f"Failed to register sync {sync.id}: {e}")
            raise

    @staticmethod
    def _get_trigger(schedule_interval: str, next_sync_at: datetime):
        """Get appropriate APScheduler trigger based on interval type."""
        interval_map = {
            "every_6h": timedelta(hours=6),
            "every_12h": timedelta(hours=12),
            "every_24h": timedelta(hours=24),
            "daily": timedelta(days=1),
            "weekly": timedelta(weeks=1),
        }
        delta = interval_map.get(schedule_interval)
        if delta is not None:
            total_hours = int(delta.total_seconds() // 3600)
            if total_hours >= 24 and total_hours % 24 == 0:
                return IntervalTrigger(days=int(total_hours // 24), start_date=next_sync_at)
            return IntervalTrigger(hours=total_hours, start_date=next_sync_at)
        raise ValueError(f"Unsupported schedule interval: {schedule_interval}")
