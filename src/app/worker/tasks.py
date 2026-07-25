"""Celery task definitions for playlist sync operations."""

import logging

from src.app.core.services.matcher import get_active_rules_sync
from src.app.core.services.orchestrator import SyncOrchestrator
from src.app.core.sources.registry import SourceRegistry
from src.app.services import get_sync_target
from src.app.services.audit import log_event_sync
from src.app.worker.app import celery_app
from src.app.worker.sync_helpers import _execute_sync, _run_async, _save_sync_results

logger = logging.getLogger(__name__)


@celery_app.task(bind=True)
def sync_playlists_task(
    self,
    playlist_url: str,
    source: str = "youtube_music",
    replace_existing: bool = False,
    schedule_id: int | None = None,
    target_playlist_name: str | None = None,
):
    resource_id = str(schedule_id) if schedule_id else None
    log_event_sync(
        event_type="sync.started",
        resource_type="playlist",
        resource_id=resource_id,
        summary=f"Sync started for {source} playlist — {playlist_url}",
    )

    rules = get_active_rules_sync()

    try:
        result = _execute_sync(
            resource_type="playlist",
            resource_id=resource_id,
            summary_prefix=f"Sync for {source} playlist — {playlist_url}",
            coro_factory=lambda: _async_sync_task(
                playlist_url,
                source,
                replace_existing,
                schedule_id,
                rules,
                target_playlist_name,
            ),
        )
        return result
    except Exception as e:
        log_event_sync(
            event_type="sync.failed",
            resource_type="playlist",
            resource_id=resource_id,
            summary=f"Sync failed: {e} — {playlist_url}",
            details={"error": str(e), "playlist_url": playlist_url, "source": source},
        )
        raise self.retry(exc=e, countdown=60, max_retries=3) from e


async def _async_sync_task(
    playlist_url: str,
    source: str,
    replace_existing: bool,
    schedule_id: int | None = None,
    rules=None,
    target_playlist_name: str | None = None,
) -> dict:
    source_cls = SourceRegistry.get(source)
    source_adapter = source_cls()
    playlist_metadata = await source_adapter.get_playlist(playlist_url)

    logger.debug(
        "Fetched playlist '%s' with %d tracks",
        playlist_metadata.title,
        len(playlist_metadata.tracks),
    )

    target = await get_sync_target()
    orchestrator = SyncOrchestrator(target=target)

    stats = await orchestrator.sync_playlist(
        playlist=playlist_metadata,
        replace_existing=replace_existing,
        rules=rules,
        target_playlist_name=target_playlist_name,
    )

    track_rows = stats.pop("track_rows", [])

    import asyncio

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
