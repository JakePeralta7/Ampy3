"""Target service — singleton lifecycle for sync targets."""

from __future__ import annotations

import asyncio
import logging
import threading
from typing import Any

from src.app.services.base import ServiceBase
from src.app.services.config_fingerprint import _config_fingerprint
from src.app.worker.session import _worker_loop

logger = logging.getLogger(__name__)


class TargetService(ServiceBase):
    """Service for managing sync target instances (async initialization).

    Constructed target instances are cached per ``target_id`` for the process
    lifetime, so repeated lookups reuse a single HTTP client instead of leaking
    a new one on every call. ``reset()`` closes and drops the cache (called
    when target settings change and from ``reset_services()``).
    """

    _instances: dict[str, Any] = {}
    _lock = threading.Lock()

    @classmethod
    def create(cls) -> Any:
        raise NotImplementedError("Use get_target_async() for TargetService")

    @classmethod
    async def create_async(cls) -> Any:
        raise NotImplementedError("Use get_target_async() for TargetService")

    @classmethod
    async def get_target_async(cls, target_id: str) -> Any:
        """Get or create a sync target instance by ID.

        Uses the target registry's factory to construct the target from DB config.
        Returns a :class:`BaseTarget` implementation (e.g. ``PlexTarget``).
        """
        if target_id in cls._instances:
            return cls._instances[target_id]

        with cls._lock:
            if target_id in cls._instances:
                return cls._instances[target_id]

            import src.app.core.targets  # noqa: F401 — trigger registrations
            from src.app.core.targets.registry import TargetRegistry

            TargetRegistry.get(target_id)  # validate target_id exists
            factory = TargetRegistry.get_factory(target_id)
            instance = await factory()
            cls._instances[target_id] = instance
            logger.info("Created and cached %s target instance", target_id)
            return instance

    @classmethod
    def reset(cls) -> None:
        """Close cached target instances and clear the cache.

        Safe to call from both sync and async contexts: when an event loop is
        running the cleanup is scheduled in the background; otherwise it runs
        on the worker's persistent event loop.
        """
        instances = list(cls._instances.values())
        cls._instances.clear()

        async def _close_all() -> None:
            for instance in instances:
                close = getattr(instance, "close", None)
                if close is None:
                    continue
                try:
                    await close()
                except Exception:
                    logger.exception(
                        "Failed to close cached target instance: %s",
                        getattr(instance, "target_id", "?"),
                    )

        try:
            loop = asyncio.get_running_loop()
        except RuntimeError:
            # Sync context (e.g., Celery task) — use worker's persistent loop
            loop = _worker_loop()
            future = asyncio.run_coroutine_threadsafe(_close_all(), loop)
            future.result(timeout=30)
        else:
            task = asyncio.create_task(_close_all())
            task.add_done_callback(lambda t: t.exception() if not t.cancelled() else None)

        # Update config fingerprint in Valkey so other workers know to reset
        from src.app.services.valkey import ValkeyService
        from src.app.worker.session import run_async

        fp = _config_fingerprint()
        try:
            loop = asyncio.get_running_loop()
        except RuntimeError:
            run_async(ValkeyService.check_and_update_fingerprint(fp))
        else:
            loop.create_task(ValkeyService.check_and_update_fingerprint(fp))

        logger.info("Reset %d target instance(s)", len(instances))
