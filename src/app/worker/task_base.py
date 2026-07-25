"""Base class for Celery tasks with structured logging and error handling."""

from __future__ import annotations

import logging
from abc import abstractmethod
from typing import Any

from celery import Task

from src.app.services.audit import log_event_sync

logger = logging.getLogger(__name__)


class SyncTaskBase(Task):
    """Base Celery task for sync operations.

    Provides structured audit logging around the task lifecycle.
    Subclasses implement :meth:`execute` with the actual work.

    Usage::

        @celery_app.task(bind=True, base=SyncTaskBase)
        def sync_playlists_task(self, playlist_url, source, ...):
            return self.run_sync(playlist_url, source, ...)

    Or subclass directly::

        class MySyncTask(SyncTaskBase):
            abstract = False
            def execute(self, **kwargs):
                ...
    """

    abstract = True

    event_type_prefix: str = "sync"
    """Prefix for audit event types, e.g. ``"sync"`` produces
    ``sync.started``, ``sync.completed``, ``sync.failed``."""

    def run_sync(
        self,
        *,
        resource_id: str | None = None,
        summary_start: str = "Task started",
        summary_done: str = "Task completed",
        **kwargs: Any,
    ) -> dict:
        """Execute the task with audit logging and error handling.

        Subclasses should call this from their ``run()`` method or
        use :class:`execute` directly.
        """
        try:
            logger.debug(summary_start)
            log_event_sync(
                event_type=f"{self.event_type_prefix}.started",
                resource_type="playlist",
                resource_id=resource_id,
                summary=summary_start,
            )
            result = self.execute(resource_id=resource_id, **kwargs)
            log_event_sync(
                event_type=f"{self.event_type_prefix}.completed",
                resource_type="playlist",
                resource_id=resource_id,
                summary=summary_done,
                details=result if isinstance(result, dict) else None,
            )
            return {"status": "SUCCESS", "result": result}
        except Exception as exc:
            logger.error("Task failed: %s", exc, exc_info=True)
            log_event_sync(
                event_type=f"{self.event_type_prefix}.failed",
                resource_type="playlist",
                resource_id=resource_id,
                summary=f"Task failed: {exc}",
                details={"error": str(exc)},
            )
            raise self.retry(exc=exc, countdown=60, max_retries=3) from exc

    @abstractmethod
    def execute(self, **kwargs: Any) -> dict:
        """Implement the actual task logic here."""
        ...
