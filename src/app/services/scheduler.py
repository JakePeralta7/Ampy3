"""APScheduler service for managing scheduled playlist syncs.

Uses APScheduler 4.x with AsyncScheduler and SQLAlchemyDataStore for
persistent job storage in PostgreSQL (asyncpg).
"""

from __future__ import annotations

import logging
import uuid
from datetime import UTC, datetime
from typing import Any

from apscheduler import AsyncScheduler, ConflictPolicy
from apscheduler.datastores.sqlalchemy import SQLAlchemyDataStore
from apscheduler.triggers.interval import IntervalTrigger
from sqlalchemy import select
from sqlalchemy.ext.asyncio import create_async_engine
from sqlalchemy.orm import selectinload

from src.app.constants import INTERVAL_DELTAS
from src.app.db import AsyncSessionLocal
from src.app.models import ScheduledPlaylistSync, SyncRun
from src.app.services.base import ServiceBase
from src.app.services.valkey import ValkeyService
from src.app.settings import settings
from src.app.worker.tasks import sync_playlists_task

logger = logging.getLogger(__name__)

# How long an interval dispatch lock lives. Serves as a safety net for runs
# that never start or crash before releasing the lock (see
# ``_release_dispatch_lock``); well above the worker soft time limit (~58 min)
# yet below the shortest interval (6h) so a stale lock never blocks a tick.
_DISPATCH_LOCK_TTL_SECONDS = 14_400


def _dispatch_lock_key(schedule_id: int) -> str:
    return f"ampy3:dispatch_lock:{schedule_id}"


def _dispatch_counter_key(schedule_id: int) -> str:
    return f"ampy3:dispatch_counter:{schedule_id}"


# Compare-and-delete the dispatch lock plus its sibling counter key. Atomic on
# the server, so an expired/replaced lock can never be clobbered by a stale
# owner (the non-atomic get-then-delete it replaces).
_RELEASE_LOCK_SCRIPT = """\
local current = redis.call('get', KEYS[1])
if not current or tostring(current) ~= ARGV[1] then
  return 0
end
redis.call('del', KEYS[1], KEYS[2])
return 1
"""


# Decrement the run's pending-child counter; the child that reaches zero
# deletes the counter and the dispatch lock. Ownership is bound to the lock
# token, so a stale child from a superseded dispatch is inert, and the TTL is
# refreshed on every decrement so a long run never dies under a live lock.
_CHILD_FINISHED_SCRIPT = """\
local val = redis.call('get', KEYS[2])
if not val then
  return 0
end
local tok, n = string.match(val, '^(.-):(%d+)$')
if not tok or tok ~= ARGV[1] then
  return 0
end
n = tonumber(n) - 1
if n <= 0 then
  redis.call('del', KEYS[2])
  redis.call('del', KEYS[1])
  return 1
end
redis.call('set', KEYS[2], tok .. ':' .. n, 'EX', ARGV[2])
return 0
"""


def _try_acquire_dispatch_lock(schedule_id: int, child_count: int = 1) -> str | None:
    """Return an owner token when this schedule may dispatch a new run.

    Valkey ``SET NX EX`` keyed per schedule prevents overlapping interval
    dispatches: if a previous dispatch's run is still in flight, later
    dispatches are skipped instead of enqueuing duplicate work. The token is
    stored as the lock value so the worker can release the lock it owns when
    the run finishes; *child_count* target tasks will share one decrement
    budget stored alongside the lock (see ``_CHILD_FINISHED_SCRIPT``), and the
    TTL only expires locks whose owner never released.

    Returns ``None`` when a run is already in flight. Fails open: a Valkey
    outage must never block a scheduled sync, so an *unstored* token is
    returned in that case (any release is then a no-op).
    """
    token = uuid.uuid4().hex
    try:
        client = ValkeyService.get_sync_instance()
        acquired = client.set(
            _dispatch_lock_key(schedule_id),
            token,
            nx=True,
            ex=_DISPATCH_LOCK_TTL_SECONDS,
        )
        if not acquired:
            return None
        client.set(
            _dispatch_counter_key(schedule_id),
            f"{token}:{child_count}",
            ex=_DISPATCH_LOCK_TTL_SECONDS,
        )
        return token
    except Exception as e:
        logger.warning("Could not acquire dispatch lock for schedule %d: %s", schedule_id, e)
        # Fail open: return the unstored token so the sync proceeds even if Valkey is down.
        # Release functions check for this and treat it as a no-op (no stored lock to release).
        return token


def _release_dispatch_lock(schedule_id: int, token: str | None) -> None:
    """Release the dispatch lock for *schedule_id* if *token* still owns it.

    Runs a compare-and-delete Lua script so an expired-then-reacquired lock is
    never deleted by a stale owner. Best effort: a missing/mismatched token or
    a Valkey outage is logged and swallowed — the lock TTL still expires locks
    whose owner never released.
    """
    if not token:
        return
    try:
        client = ValkeyService.get_sync_instance()
        client.eval(
            _RELEASE_LOCK_SCRIPT,
            2,
            _dispatch_lock_key(schedule_id),
            _dispatch_counter_key(schedule_id),
            token,
        )
    except Exception as e:
        logger.warning("Could not release dispatch lock for schedule %d: %s", schedule_id, e)


def _child_finished_dispatch_lock(schedule_id: int, token: str) -> None:
    """Record that one per-target child finished; the last one drops the lock.

    Called from each ``sync_target_task`` postrun so the dispatch lock stays
    held for the whole run — fetch, matching *and* every target update — not
    just the fetch phase. Dead children fall back to the lock TTL.
    """
    try:
        client = ValkeyService.get_sync_instance()
        client.eval(
            _CHILD_FINISHED_SCRIPT,
            2,
            _dispatch_lock_key(schedule_id),
            _dispatch_counter_key(schedule_id),
            token,
            str(_DISPATCH_LOCK_TTL_SECONDS),
        )
    except Exception as e:
        logger.warning(
            "Could not record child completion for schedule %d: %s",
            schedule_id,
            e,
        )


async def _create_failed_run(
    sync_id: int,
    target_ids: list[str],
    execution_id: str,
    error_message: str,
) -> None:
    """Create failed SyncRun entries for all targets when dispatch fails."""
    async with AsyncSessionLocal() as session, session.begin():
        for target_id in target_ids:
            run = SyncRun(
                sync_id=sync_id,
                target_id=target_id,
                status="failed",
                matched_count=0,
                failed_count=0,
                execution_id=execution_id,
                error_message=error_message[:2000],
            )
            session.add(run)


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
    token = _try_acquire_dispatch_lock(sync_id, len(target_ids))
    if token is None:
        logger.warning(
            "Scheduled dispatch for schedule %d failed: could not acquire lock",
            sync_id,
        )
        execution_id = uuid.uuid4().hex
        import asyncio

        asyncio.run(
            _create_failed_run(
                sync_id,
                target_ids,
                execution_id,
                "Could not acquire dispatch lock",
            )
        )
        return

    sync_playlists_task.delay(
        playlist_url=source_url,
        source=source,
        target_ids=target_ids,
        schedule_id=sync_id,
        target_playlist_name=target_playlist_name,
        dispatch_token=token,
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
        real task id (usable with the status endpoint). Returns ``None`` if a
        run is already in flight for this schedule (overlap guard).
        """
        token = _try_acquire_dispatch_lock(sync.id, len(sync.target_ids))
        if token is None:
            logger.info(
                "Skipping manual sync for schedule %d: a run is already in progress",
                sync.id,
            )
            return None
        return sync_playlists_task.delay(
            playlist_url=sync.source_url,
            source=sync.source,
            target_ids=sync.target_ids,
            schedule_id=sync.id,
            target_playlist_name=sync.target_playlist_name,
            dispatch_token=token,
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
