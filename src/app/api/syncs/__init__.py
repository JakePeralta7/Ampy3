"""Sync API endpoints — triggering, tracking, and reviewing sync operations."""

from fastapi import APIRouter

from src.app.api.syncs.helpers import _select_execution
from src.app.api.syncs.history import get_sync_diff
from src.app.api.syncs.history import router as history_router
from src.app.api.syncs.match import router as match_router
from src.app.api.syncs.status import get_sync_status
from src.app.api.syncs.status import router as status_router
from src.app.api.syncs.tracks import get_unmatched_tracks
from src.app.api.syncs.tracks import router as tracks_router
from src.app.api.syncs.trigger import _is_execution_id_conflict, trigger_sync
from src.app.api.syncs.trigger import router as trigger_router
from src.app.db import AsyncSessionLocal
from src.app.services import list_sync_targets
from src.app.services.audit import log_event
from src.app.services.sync_tasks import get_sync_id_for_task_async, register_sync_task_async
from src.app.services.websocket_manager import broadcast_sync_event
from src.app.worker.tasks import get_sync_status_task, sync_playlists_task

router = APIRouter(prefix="/api/v1/syncs", tags=["syncs"])

router.include_router(trigger_router)
router.include_router(tracks_router)
router.include_router(history_router)
router.include_router(match_router)
router.include_router(status_router)

# Re-export for backward compatibility with tests
__all__ = [
    "router",
    "trigger_sync",
    "_is_execution_id_conflict",
    "_select_execution",
    "get_unmatched_tracks",
    "get_sync_diff",
    "get_sync_status",
    "get_sync_id_for_task_async",
    "get_sync_status_task",
    "AsyncSessionLocal",
    "list_sync_targets",
    "log_event",
    "register_sync_task_async",
    "broadcast_sync_event",
    "sync_playlists_task",
]
