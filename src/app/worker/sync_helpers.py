"""Helper functions for Celery sync tasks."""

import asyncio
import logging
from datetime import UTC, datetime, timedelta

from sqlalchemy import delete, insert, select

from src.app.db import SessionLocal
from src.app.models import (
    PlaylistTrack,
    ScheduledPlaylistSync,
    ScheduleIntervalEnum,
    SyncRun,
    SyncRunTrack,
)

logger = logging.getLogger(__name__)


def _run_async(coro_func):
    """Run an async coroutine function in a new event loop.

    Args:
        coro_func: A callable that returns a coroutine, or a coroutine object.
                   If it's a callable, it will be called to create a fresh coroutine
                   if the first attempt fails.
    """
    try:
        # If it's a callable, call it to get the coroutine
        coro = coro_func() if callable(coro_func) else coro_func
        return asyncio.run(coro)
    except RuntimeError as e:
        # If asyncio.run() fails, try creating a new loop
        # For callables, we can create a fresh coroutine; for coroutines, we cannot retry
        if not callable(coro_func):
            raise e

        loop = asyncio.new_event_loop()
        asyncio.set_event_loop(loop)
        try:
            coro = coro_func()  # Create a fresh coroutine
            return loop.run_until_complete(coro)
        finally:
            loop.close()


def _mark_sync_failed(schedule_id: int, error_message: str):
    """Update sync dates for a failed scheduled sync (called from scheduler.py only)."""
    db = SessionLocal()
    try:
        result = db.execute(
            select(ScheduledPlaylistSync).where(ScheduledPlaylistSync.id == schedule_id)
        )
        sync = result.scalar_one_or_none()
        if sync:
            sync.last_synced_at = datetime.now(UTC)
            sync.error_message = error_message
            db.commit()
    finally:
        db.close()


def _save_sync_results(
    schedule_id: int | None,
    playlist_url: str,
    source: str,
    playlist_title: str,
    stats: dict,
    track_rows: list[dict],
    error_message: str | None = None,
) -> None:
    db = SessionLocal()
    try:
        if schedule_id:
            stmt = select(ScheduledPlaylistSync).where(ScheduledPlaylistSync.id == schedule_id)
        else:
            stmt = select(ScheduledPlaylistSync).where(
                ScheduledPlaylistSync.source_url == playlist_url
            )

        result = db.execute(stmt)
        sync_record = result.scalars().first()

        if sync_record:
            sync_record.matched_count = stats.get("matched", 0)
            sync_record.failed_count = stats.get("failed", 0)
            sync_record.target_playlist_id = stats.get("target_playlist_id")
        else:
            sync_record = ScheduledPlaylistSync(
                source=source,
                source_url=playlist_url,
                target_playlist_name=playlist_title,
                target_playlist_id=stats.get("target_playlist_id"),
                schedule_interval="once",
                is_active=False,
                matched_count=stats.get("matched", 0),
                failed_count=stats.get("failed", 0),
                next_sync_at=datetime.now(UTC),
            )
            db.add(sync_record)
            db.flush()

        # Persist sync run history before replacing current tracks
        run = SyncRun(
            sync_id=sync_record.id,
            matched_count=stats.get("matched", 0),
            failed_count=stats.get("failed", 0),
        )
        db.add(run)
        db.flush()

        if track_rows:
            run_track_rows = []
            for row_data in track_rows:
                run_track_rows.append({
                    "run_id": run.id,
                    "position": row_data.get("position", 0),
                    "source_title": row_data.get("source_title"),
                    "source_artist": row_data.get("source_artist"),
                    "source_album": row_data.get("source_album"),
                    "source_duration_ms": row_data.get("source_duration_ms"),
                    "source_id": row_data.get("source_id"),
                    "match_item_id": row_data.get("match_item_id"),
                    "match_title": row_data.get("match_title"),
                    "match_artist": row_data.get("match_artist"),
                    "match_album": row_data.get("match_album"),
                    "match_duration": row_data.get("match_duration"),
                    "match_rule_id": row_data.get("match_rule_id"),
                })
            db.execute(insert(SyncRunTrack), run_track_rows)

        # Replace playlist tracks with bulk insert
        db.execute(delete(PlaylistTrack).where(PlaylistTrack.sync_id == sync_record.id))
        if track_rows:
            for row_data in track_rows:
                row_data["sync_id"] = sync_record.id
            db.execute(insert(PlaylistTrack), track_rows)

        # Update sync dates for scheduled syncs
        if schedule_id and sync_record:
            sync_record.last_synced_at = datetime.now(UTC)
            sync_record.error_message = error_message
            if error_message is None:
                interval_map = {
                    ScheduleIntervalEnum.EVERY_6H: timedelta(hours=6),
                    ScheduleIntervalEnum.EVERY_12H: timedelta(hours=12),
                    ScheduleIntervalEnum.EVERY_24H: timedelta(hours=24),
                    ScheduleIntervalEnum.DAILY: timedelta(days=1),
                    ScheduleIntervalEnum.WEEKLY: timedelta(weeks=1),
                }
                delta = interval_map.get(sync_record.schedule_interval, timedelta(days=1))
                sync_record.next_sync_at = sync_record.last_synced_at + delta

        db.commit()
        logger.debug(f"Saved {len(track_rows)} playlist tracks for '{playlist_title}'")
    except Exception as e:
        logger.error(f"Failed to save playlist tracks: {e}")
        raise
    finally:
        db.close()
