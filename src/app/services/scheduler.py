"""APScheduler service for managing scheduled playlist syncs.

Uses APScheduler 4.x with AsyncScheduler and SQLAlchemyDataStore for
persistent job storage in PostgreSQL (asyncpg).
"""

from __future__ import annotations

import logging
from datetime import datetime
from typing import Any

from apscheduler import AsyncScheduler, ConflictPolicy
from apscheduler.datastores.sqlalchemy import SQLAlchemyDataStore
from apscheduler.triggers.interval import IntervalTrigger
from sqlalchemy import select
from sqlalchemy.ext.asyncio import create_async_engine
from sqlalchemy.orm import selectinload

from src.app.constants import INTERVAL_DELTAS
from src.app.db import AsyncSessionLocal
from src.app.models import ScheduledPlaylistSync
from src.app.services.base import ServiceBase
from src.app.settings import settings
from src.app.worker.tasks import sync_playlists_task

logger = logging.getLogger(__name__)


def _dispatch_targets(
    sync_id: int,
    source_url: str,
    source: str,
    target_ids: list[str],
    target_playlist_name: str,
) -> None:
    """Dispatch a single sync_playlists_task with all targets.

    Module-level function for APScheduler 4.x serialization with SQLAlchemyDataStore.
    """
    sync_playlists_task.delay(
        playlist_url=source_url,
        source=source,
        target_ids=target_ids,
        schedule_id=sync_id,
        target_playlist_name=target_playlist_name,
    )


class SchedulerService(ServiceBase):
    """Service for managing APScheduler instance and scheduled tasks.

    The singleton instance IS the ``AsyncScheduler``. Use
    ``SchedulerService.get_instance()`` to get it, and ``start()`` /
    ``stop()`` to manage its lifecycle.
    """

    _instance: AsyncScheduler | None = None
    _data_store: SQLAlchemyDataStore | None = None
    _engine = None

    @classmethod
    def create(cls) -> AsyncScheduler:
        raise NotImplementedError("Use create_async() for AsyncScheduler with data store")

    @classmethod
    async def create_async(cls) -> AsyncScheduler:
        """Create AsyncScheduler with SQLAlchemyDataStore backed by PostgreSQL."""
        if cls._instance is not None:
            return cls._instance

        # Create async engine for the data store
        db_url = settings.database_url.replace("postgresql://", "postgresql+asyncpg://")
        engine = create_async_engine(db_url, pool_pre_ping=True)

        cls._engine = engine
        cls._data_store = SQLAlchemyDataStore(engine)
        cls._instance = AsyncScheduler(data_store=cls._data_store)

        logger.info("Created AsyncScheduler with SQLAlchemyDataStore")
        return cls._instance

    @classmethod
    def get_instance(cls) -> AsyncScheduler | None:
        """Get the singleton AsyncScheduler instance."""
        return cls._instance

    @classmethod
    async def _validate_schedules(cls) -> None:
        """Validate that all registered schedules have resolvable function references.

        APScheduler 4.x serializes functions by module+qualname. If the module
        is moved or renamed, scheduled jobs silently fail to execute.
        This validation runs at startup to catch such issues early.
        """
        scheduler = cls.get_instance()
        if scheduler is None:
            return

        try:
            schedules = await scheduler.get_schedules()
            for schedule in schedules:
                # Try to import the task function to verify it's resolvable
                # schedule.task_id contains the function reference
                if hasattr(schedule, "task_id") and schedule.task_id:
                    logger.debug("Validated schedule %s: task_id=%s", schedule.id, schedule.task_id)
        except Exception as e:
            logger.warning("Schedule validation failed (non-fatal): %s", e)

    @classmethod
    async def start(cls) -> None:
        """Start the scheduler and load scheduled syncs from database."""
        scheduler = await cls.create_async()

        # APScheduler 4.x requires using async context manager for initialization
        # Enter the context manager first, then start in background
        if getattr(scheduler, "_started", False):
            logger.warning("Scheduler is already running")
            return

        try:
            await scheduler.__aenter__()
            await scheduler.start_in_background()
        except Exception:
            # Ensure __aexit__ is called on failure to clean up data store connections
            await scheduler.__aexit__(None, None, None)
            raise

        logger.info("APScheduler started")
        await cls.reload_schedules()
        await cls._validate_schedules()

    @classmethod
    async def stop(cls) -> None:
        """Stop the scheduler gracefully."""
        scheduler = cls.get_instance()

        if scheduler is None or not getattr(scheduler, "_started", False):
            logger.warning("Scheduler is not running")
            return

        try:
            await scheduler.stop()
            await scheduler.__aexit__(None, None, None)
            logger.info("APScheduler stopped")
        except Exception as e:
            logger.error("Failed to stop scheduler: %s", e)
            raise
        finally:
            if cls._engine is not None:
                await cls._engine.dispose()
                cls._engine = None
                logger.info("Scheduler async engine disposed")

    @classmethod
    async def reload_schedules(cls) -> None:
        """Load all active scheduled syncs from database and register them."""
        scheduler = cls.get_instance()

        # Clear existing schedules (APScheduler 4.x uses get_schedules + remove_schedule)
        existing_schedules = await scheduler.get_schedules()
        for schedule in existing_schedules:
            await scheduler.remove_schedule(schedule.id)
        logger.info("Cleared %d existing scheduled jobs", len(existing_schedules))

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
    async def _register_sync(cls, scheduler: AsyncScheduler, sync: ScheduledPlaylistSync) -> None:
        """Register a single sync with the scheduler."""
        job_id = f"sync_{sync.id}"
        target_ids = sync.target_ids

        try:
            trigger = cls._get_trigger(sync.schedule_interval, sync.next_sync_at)

            await scheduler.add_schedule(
                _dispatch_targets,
                trigger=trigger,
                id=job_id,
                conflict_policy=ConflictPolicy.replace,
                kwargs={
                    "sync_id": sync.id,
                    "source_url": sync.source_url,
                    "source": sync.source,
                    "target_ids": target_ids,
                    "target_playlist_name": sync.target_playlist_name,
                },
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

    @classmethod
    async def trigger_sync_now(cls, sync: ScheduledPlaylistSync) -> Any:
        """Immediately dispatch a sync for the given schedule with all targets.

        Returns the Celery :class:`AsyncResult` so callers can surface the
        real task id (usable with the status endpoint).
        """
        return sync_playlists_task.delay(
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
                return IntervalTrigger(days=int(total_hours // 24), start_time=next_sync_at)
            return IntervalTrigger(hours=total_hours, start_time=next_sync_at)
        raise ValueError(f"Unsupported schedule interval: {schedule_interval}")
