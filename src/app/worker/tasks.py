"""Celery task definitions for playlist sync operations."""

import asyncio
import logging

from src.app.core.services.matcher import get_active_rules_sync
from src.app.core.services.orchestrator import SyncOrchestrator
from src.app.core.sources.registry import SourceRegistry
from src.app.services import get_sync_target
from src.app.services.audit import log_event_sync
from src.app.worker.app import celery_app
from src.app.worker.sync_helpers import _run_async, _save_sync_results

logger = logging.getLogger(__name__)


@celery_app.task(bind=True)
def sync_playlists_task(self, playlist_url: str, source: str = "youtube_music", replace_existing: bool = False, schedule_id: int | None = None):
    try:
        logger.debug(f"Starting sync for playlist from {source}: {playlist_url}")
        log_event_sync(
            event_type="sync.started",
            resource_type="playlist",
            resource_id=str(schedule_id) if schedule_id else None,
            summary=f"Sync started for {source} playlist — {playlist_url}",
        )
        # Load rules synchronously FIRST to avoid asyncio.run() conflicts
        rules = get_active_rules_sync()
        # Pass a lambda that creates the coroutine, so _run_async can retry with a fresh coroutine
        stats = _run_async(lambda: _async_sync_task(playlist_url, source, replace_existing, schedule_id, rules))
        logger.debug(f"Sync completed: {stats['matched']} matched, {stats['failed']} failed")
        log_event_sync(
            event_type="sync.completed",
            resource_type="playlist",
            resource_id=str(schedule_id) if schedule_id else None,
            summary=f"Sync completed: {stats.get('matched', 0)} matched, {stats.get('failed', 0)} failed — {playlist_url}",
            details=stats,
        )
        return {"status": "SUCCESS", "stats": stats}
    except Exception as e:
        logger.error(f"An error occurred during the sync process: {e}", exc_info=True)
        log_event_sync(
            event_type="sync.failed",
            resource_type="playlist",
            resource_id=str(schedule_id) if schedule_id else None,
            summary=f"Sync failed: {str(e)} — {playlist_url}",
            details={"error": str(e), "playlist_url": playlist_url, "source": source},
        )
        raise self.retry(exc=e, countdown=60, max_retries=3) from e


async def _async_sync_task(playlist_url: str, source: str, replace_existing: bool, schedule_id: int | None = None, rules=None) -> dict:
    # Resolve source adapter via registry
    source_cls = SourceRegistry.get(source)
    source_adapter = source_cls()
    playlist_metadata = await source_adapter.get_playlist(playlist_url)

    logger.debug(f"Fetched playlist '{playlist_metadata.title}' with {len(playlist_metadata.tracks)} tracks")

    target = await get_sync_target()
    orchestrator = SyncOrchestrator(target=target)

    stats = await orchestrator.sync_playlist(
        playlist=playlist_metadata,
        replace_existing=replace_existing,
        rules=rules
    )

    track_rows = stats.pop("track_rows", [])

    await asyncio.to_thread(
        _save_sync_results,
        schedule_id,
        playlist_url,
        source,
        playlist_metadata.title,
        stats,
        track_rows,
    )

    return stats


@celery_app.task
def get_sync_status_task(task_id: str):
    from celery.result import AsyncResult
    result = AsyncResult(task_id, app=celery_app)
    return {
        "task_id": task_id,
        "status": result.state,
        "ready": result.ready(),
        "result": result.result if result.ready() else None,
    }
