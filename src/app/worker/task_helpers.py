"""Side-effect helpers shared by the Celery sync tasks.

These keep :mod:`src.app.worker.tasks` focused on Celery orchestration: target
health checks, SyncRun failure bookkeeping, retry backoff, and the per-process
target-cache refresh all live here.
"""

from __future__ import annotations

import logging
import random
import time
from typing import Any

from sqlalchemy import select

from src.app.core.exceptions import DatabaseError
from src.app.models import SyncRun
from src.app.worker.context import SyncContext

logger = logging.getLogger(__name__)

# Config fingerprint check TTL (seconds) — avoids hammering Valkey on every task
_CONFIG_FP_TTL_SECONDS = 30
_config_fp_last_checked: dict[str, tuple[str, float]] = {}  # process_id -> (fingerprint, timestamp)


def verify_target_connection(ctx: SyncContext) -> None:
    """Pre-flight: verify the target is reachable before matching any tracks.

    Runs before the match phase so an unreachable target fails fast and is
    reported as a connection error instead of marking every track as failed.
    """
    from src.app.worker.session import run_async

    try:
        run_async(ctx.target.test_connection())
    except Exception as e:
        from src.app.worker.errors import SyncTargetConnectionError

        raise SyncTargetConnectionError(f"Target '{ctx.target_id}' connection failed: {e}") from e


async def verify_target_connection_for_target_async(target_id: str) -> None:
    """Verify a target connection by target_id (for pre-fetch validation).

    Must be *awaited* on the worker event loop. Calling the sync ``run_async``
    helper from inside a coroutine deadlocks: the loop thread blocks in
    ``future.result()`` and can never schedule the coroutine it waits for.
    """
    from src.app.services import get_sync_target
    from src.app.worker.errors import SyncTargetConnectionError

    try:
        target = await get_sync_target(target_id)
        await target.test_connection()
    except SyncTargetConnectionError:
        raise
    except Exception as e:
        raise SyncTargetConnectionError(f"Target '{target_id}' connection failed: {e}") from e


async def verify_target_connections_async(target_ids: list[str], *, concurrency: int = 5) -> None:
    """Verify several targets concurrently, bounding in-flight checks."""
    import asyncio

    semaphore = asyncio.Semaphore(concurrency)

    async def _verify_one(target_id: str) -> None:
        async with semaphore:
            await verify_target_connection_for_target_async(target_id)

    await asyncio.gather(*(_verify_one(tid) for tid in target_ids))


def record_failed_run(ctx: SyncContext, error: str) -> None:
    """Reuse or create the target's SyncRun and mark it failed with an error."""
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
    except DatabaseError:
        logger.warning("Failed to record failed SyncRun (database error)", exc_info=True)
    except Exception as e:
        logger.warning("Failed to record failed SyncRun (unexpected error): %s", e, exc_info=True)


def mark_latest_run_failed(sync_id: int, target_id: str, error: str) -> None:
    """Mark the most recent SyncRun for *target_id* as failed."""
    from src.app.worker.session import session_scope

    try:
        with session_scope() as db:
            stmt = (
                select(SyncRun)
                .where(SyncRun.sync_id == sync_id, SyncRun.target_id == target_id)
                .order_by(SyncRun.created_at.desc())
                .limit(1)
            )
            run = db.execute(stmt).scalars().first()
            if run:
                run.status = "failed"
                run.error_message = error[:2000]
    except Exception as db_exc:
        logger.warning("Failed to mark SyncRun as failed: %s", db_exc, exc_info=True)


def retry_countdown(completed_retries: int) -> int:
    """Exponential backoff with jitter for task retries.

    Capped at Celery soft_time_limit - 60s buffer to avoid exceeding time limits.
    """
    from src.app.worker.app import celery_app

    soft_limit = celery_app.conf.task_soft_time_limit or 3480
    max_backoff = max(60, soft_limit - 60)
    base = min(max_backoff, 60 * (2**completed_retries))
    return base + random.randint(0, 10)


def refresh_target_cache_if_config_changed() -> None:
    """Reset cached target instances when the config fingerprint changed.

    The web API writes the Valkey fingerprint on every settings change, so a
    worker comparing against that key would never notice a config change via
    its own reads (the caching in TargetService hides it). Tracking the last
    processed fingerprint per process means the next task after a config
    change rebuilds the target instance deliberately.

    Uses a per-process TTL to avoid checking Valkey on every task.
    """
    import os

    from src.app.services.config_fingerprint import _config_fingerprint
    from src.app.services.target import TargetService

    process_id = str(os.getpid())
    now = time.monotonic()

    # Check TTL
    if process_id in _config_fp_last_checked:
        last_fp, last_check = _config_fp_last_checked[process_id]
        if now - last_check < _CONFIG_FP_TTL_SECONDS:
            # Within TTL, skip Valkey call but still check if fingerprint changed in-memory
            try:
                current_fp = _config_fingerprint()
                if current_fp != last_fp:
                    TargetService.reset()
                    _config_fp_last_checked[process_id] = (current_fp, now)
                    logger.info("Target config changed — reset cached target instances")
            except Exception:
                pass  # Skip on error, will retry next task
            return

    try:
        fingerprint = _config_fingerprint()
        _config_fp_last_checked[process_id] = (fingerprint, now)
        if fingerprint != TargetService._processed_fp:
            TargetService.reset()
            TargetService._processed_fp = fingerprint
            logger.info("Target config changed — reset cached target instances")
    except Exception as e:
        logger.warning("Config fingerprint check failed (resetting targets conservatively): %s", e)
        TargetService.reset()
