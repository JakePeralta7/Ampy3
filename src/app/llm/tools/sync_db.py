"""LangGraph agent tools for querying scheduled sync state from the database.

All tools use the async SQLAlchemy session — safe to call from FastAPI/LangGraph context.
"""

from __future__ import annotations

from langchain_core.tools import tool
from sqlalchemy import select

from src.app.db import AsyncSessionLocal
from src.app.models import PlaylistTrack, ScheduledPlaylistSync, SyncRun, SyncRunTrack


@tool
async def list_scheduled_syncs() -> list[dict]:
    """List all scheduled playlist syncs with their match/fail counts.

    Returns id, source_url, target_playlist_name, schedule_interval, is_active,
    matched_count, failed_count, last_synced_at, and error_message for each sync.
    """
    async with AsyncSessionLocal() as session:
        result = await session.execute(
            select(ScheduledPlaylistSync).order_by(ScheduledPlaylistSync.id)
        )
        syncs = result.scalars().all()

    return [
        {
            "id": s.id,
            "source_url": s.source_url,
            "target_playlist_name": s.target_playlist_name,
            "schedule_interval": s.schedule_interval,
            "is_active": s.is_active,
            "matched_count": s.matched_count,
            "failed_count": s.failed_count,
            "last_synced_at": s.last_synced_at.isoformat() if s.last_synced_at else None,
            "error_message": s.error_message,
        }
        for s in syncs
    ]


@tool
async def get_sync_summary(sync_id: int) -> dict:
    """Get summary details for a single scheduled sync.

    Args:
        sync_id: The ID of the scheduled sync.

    Returns id, source_url, target_playlist_name, matched_count, failed_count,
    last_synced_at, next_sync_at, is_active, replace_existing, and error_message.
    """
    async with AsyncSessionLocal() as session:
        result = await session.execute(
            select(ScheduledPlaylistSync).where(ScheduledPlaylistSync.id == sync_id)
        )
        s = result.scalar_one_or_none()

    if not s:
        return {"error": f"Sync {sync_id} not found"}

    return {
        "id": s.id,
        "source_url": s.source_url,
        "target_playlist_name": s.target_playlist_name,
        "schedule_interval": s.schedule_interval,
        "is_active": s.is_active,
        "replace_existing": s.replace_existing,
        "matched_count": s.matched_count,
        "failed_count": s.failed_count,
        "last_synced_at": s.last_synced_at.isoformat() if s.last_synced_at else None,
        "next_sync_at": s.next_sync_at.isoformat() if s.next_sync_at else None,
        "error_message": s.error_message,
    }


@tool
async def get_unmatched_tracks(sync_id: int) -> list[dict]:
    """Return all unmatched tracks for a scheduled sync.

    A track is unmatched when the sync pipeline could not find a corresponding
    entry in the Plex library (match_item_id is NULL).

    Args:
        sync_id: The ID of the scheduled sync to inspect.

    Returns a list of dicts with position, source_title, source_artist, source_album,
    source_duration_ms, and source_id for each unmatched track.
    """
    async with AsyncSessionLocal() as session:
        result = await session.execute(
            select(PlaylistTrack)
            .where(
                PlaylistTrack.sync_id == sync_id,
                PlaylistTrack.match_item_id.is_(None),
            )
            .order_by(PlaylistTrack.position)
        )
        tracks = result.scalars().all()

    return [
        {
            "id": t.id,
            "position": t.position,
            "source_title": t.source_title,
            "source_artist": t.source_artist,
            "source_album": t.source_album,
            "source_duration_ms": t.source_duration_ms,
            "source_id": t.source_id,
        }
        for t in tracks
    ]


@tool
async def list_sync_runs(sync_id: int, limit: int = 10) -> list[dict]:
    """List recent sync run snapshots for a scheduled sync.

    Each run records the matched/failed counts at the time the sync executed.
    Useful for comparing how match rates change over time.

    Args:
        sync_id: The ID of the scheduled sync.
        limit: Maximum number of runs to return (default 10, max 50).
    """
    limit = min(limit, 50)
    async with AsyncSessionLocal() as session:
        result = await session.execute(
            select(SyncRun)
            .where(SyncRun.sync_id == sync_id)
            .order_by(SyncRun.created_at.desc())
            .limit(limit)
        )
        runs = result.scalars().all()

    return [
        {
            "id": r.id,
            "matched_count": r.matched_count,
            "failed_count": r.failed_count,
            "created_at": r.created_at.isoformat() if r.created_at else None,
        }
        for r in runs
    ]


@tool
async def get_sync_run_unmatched(run_id: int) -> list[dict]:
    """Return unmatched tracks from a specific historical sync run.

    Unlike get_unmatched_tracks (which reads the live playlist_tracks table),
    this reads the immutable SyncRunTrack snapshot captured at run time — useful
    for comparing what failed across multiple runs.

    Args:
        run_id: The ID of the SyncRun to inspect.
    """
    async with AsyncSessionLocal() as session:
        result = await session.execute(
            select(SyncRunTrack)
            .where(
                SyncRunTrack.run_id == run_id,
                SyncRunTrack.match_item_id.is_(None),
            )
            .order_by(SyncRunTrack.position)
        )
        tracks = result.scalars().all()

    return [
        {
            "id": t.id,
            "position": t.position,
            "source_title": t.source_title,
            "source_artist": t.source_artist,
            "source_album": t.source_album,
            "source_duration_ms": t.source_duration_ms,
            "source_id": t.source_id,
        }
        for t in tracks
    ]
