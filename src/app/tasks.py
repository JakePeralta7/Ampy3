"""Backward-compatible re-exports from the worker package.

Use `from src.app.worker.xxx import yyy` directly in new code.
"""
from src.app.worker import (
    celery_app,
    check_and_trigger_scheduled_syncs,
    get_sync_status_task,
    scheduled_sync_task,
    sync_playlists_task,
)

__all__ = [
    "celery_app",
    "sync_playlists_task",
    "get_sync_status_task",
    "scheduled_sync_task",
    "check_and_trigger_scheduled_syncs",
]
