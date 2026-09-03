"""Sync endpoints — triggering, tracking, and reviewing sync operations."""

import logging
from typing import Any

from fastapi import APIRouter, Depends, HTTPException, Query
from sqlalchemy import select
from sqlalchemy.orm import selectinload

from src.app.auth.dependencies import get_current_user
from src.app.constants import (
    DEFAULT_SOURCE,
    DEFAULT_TARGET,
    SOURCE_DEEZER,
    SOURCE_DEEZER_DISPLAY,
    SOURCE_YOUTUBE_MUSIC,
    SOURCE_YOUTUBE_MUSIC_DISPLAY,
    TARGET_JELLYFIN,
    TARGET_PLEX,
)
from src.app.db import AsyncSessionLocal
from src.app.models import (
    PlaylistTrack,
    PlaylistTrackTarget,
    ScheduledPlaylistSync,
    ScheduleTarget,
    SyncRun,
    SyncRunTrack,
    SyncRunTrackTarget,
)
from src.app.schemas.playlists import TrackDetail, TrackSource, TrackTarget
from src.app.schemas.syncs import (
    MatchTrackInput,
    MatchTrackResponse,
    SyncDiffItem,
    SyncDiffResponse,
    SyncRunOut,
    SyncTracksResponse,
    SyncTriggerRequest,
    SyncTriggerResponse,
    TargetOpenUrlResponse,
    UnmatchedTrackOut,
)
from src.app.services import get_sync_target
from src.app.services.audit import log_event
from src.app.worker.tasks import match_track_task, sync_playlists_task

logger = logging.getLogger(__name__)

router = APIRouter(prefix="/api/v1/syncs", tags=["syncs"])

_SOURCE_DISPLAY_NAMES = {
    SOURCE_YOUTUBE_MUSIC: SOURCE_YOUTUBE_MUSIC_DISPLAY,
    SOURCE_DEEZER: SOURCE_DEEZER_DISPLAY,
}


# ─── Shared Helpers ──────────────────────────────────────────────


def _build_track_response(
    sync_record: ScheduledPlaylistSync,
    playlist_id: str,
) -> SyncTracksResponse:
    """Build a SyncTracksResponse from a sync record's tracks (DB-only path)."""
    all_rows: list[PlaylistTrack] = list(sync_record.tracks)
    matched_rows = [r for r in all_rows if r.targets]
    unmatched_rows = [r for r in all_rows if not r.targets]
    matched_count = len(matched_rows)
    failed_count = len(unmatched_rows)

    track_details: list[TrackDetail] = []
    formatted_all: list[dict[str, Any]] = []
    for r in all_rows:
        targets = [
            TrackTarget(
                target_id=t.target_id,
                item_id=t.item_id,
                title=t.title,
                artist_name=t.artist_name,
                album_name=t.album_name,
                duration=t.duration,
            )
            for t in r.targets
        ]
        is_matched = len(targets) > 0
        if is_matched:
            first_target = targets[0]
            formatted_all.append(
                {
                    "item_id": first_target.item_id,
                    "title": first_target.title or r.source_title or "Unknown",
                    "artist_name": first_target.artist_name or r.source_artist or "Unknown",
                    "album_name": first_target.album_name or r.source_album or "Unknown",
                    "duration": (
                        first_target.duration
                        if first_target.duration is not None
                        else (r.source_duration_ms // 1000 if r.source_duration_ms else 0)
                    ),
                    "status": "matched",
                    "match_rate": "\u2713 Matched",
                }
            )
        else:
            formatted_all.append(
                {
                    "title": r.source_title or "Unknown",
                    "artist_name": r.source_artist or "Unknown",
                    "album_name": r.source_album or "Unknown",
                    "duration": (r.source_duration_ms // 1000) if r.source_duration_ms else 0,
                    "status": "unmatched",
                    "match_rate": "\u2717 Unmatched",
                }
            )
        track_details.append(
            TrackDetail(
                source=TrackSource(
                    source_id=_SOURCE_DISPLAY_NAMES.get(sync_record.source, sync_record.source),
                    item_id=r.item_id,
                    title=r.source_title,
                    artist_name=r.source_artist,
                    album_name=r.source_album,
                    duration_ms=r.source_duration_ms,
                ),
                targets=targets,
            )
        )

    formatted_matched = [t for t in formatted_all if t["status"] == "matched"]
    formatted_unmatched = [t for t in formatted_all if t["status"] == "unmatched"]

    total_tracks = matched_count + failed_count
    match_rate = f"{matched_count}/{total_tracks}" if total_tracks > 0 else "0/0"
    match_percentage = int(matched_count / total_tracks * 100) if total_tracks > 0 else 0

    return SyncTracksResponse(
        playlist_id=playlist_id,
        source=sync_record.source,
        tracks=formatted_all,
        matched_tracks=formatted_matched,
        unmatched_tracks=formatted_unmatched,
        track_details=track_details,
        total_count=total_tracks,
        matched_count=matched_count,
        failed_count=failed_count,
        total_source_tracks=total_tracks,
        match_rate=match_rate,
        match_percentage=match_percentage,
    )


# ─── Trigger ─────────────────────────────────────────────────────


@router.post("/", response_model=SyncTriggerResponse)
async def trigger_sync(
    body: SyncTriggerRequest,
    _user: dict[str, Any] = Depends(get_current_user),  # noqa: B008
):
    """Initiate a background sync job for a playlist."""
    try:
        is_yt_music = body.source == DEFAULT_SOURCE and "music.youtube.com" not in body.playlist_url
        if is_yt_music:
            raise HTTPException(status_code=422, detail="Invalid YouTube Music URL format.")

        task = sync_playlists_task.delay(
            playlist_url=body.playlist_url,
            source=body.source,
            target_ids=[body.target_id],
            schedule_id=body.schedule_id,
            target_playlist_name=body.target_playlist_name,
        )
        logger.info(f"Triggered sync task {task.id} for {body.source} playlist")

        await log_event(
            event_type="sync.manually_triggered",
            resource_type="playlist",
            resource_id=str(body.schedule_id) if body.schedule_id is not None else None,
            summary=f"Sync triggered for {body.source} playlist \u2014 {body.playlist_url}",
            details={
                "playlist_url": body.playlist_url,
                "source": body.source,
                "target_id": body.target_id,
                "schedule_id": body.schedule_id,
            },
        )

        return SyncTriggerResponse(
            message="Sync job started successfully.",
            task_id=task.id,
            status_url=f"/api/v1/syncs/status/{task.id}",
        )
    except HTTPException:
        raise
    except Exception as e:
        logger.error(f"Error triggering sync: {e}")
        raise HTTPException(status_code=500, detail=f"Failed to start sync job: {str(e)}") from e


@router.get("/status/{task_id}")
async def get_sync_status(
    task_id: str,
    _user: dict[str, Any] = Depends(get_current_user),  # noqa: B008
):
    """Poll the Celery backend for sync job status and result."""
    from src.app.worker.tasks import get_sync_status_task

    return get_sync_status_task(task_id)


# ─── Tracks ──────────────────────────────────────────────────────


@router.get("/{sync_id}/tracks", response_model=SyncTracksResponse)
async def get_sync_tracks(
    sync_id: int,
    _user: dict[str, Any] = Depends(get_current_user),  # noqa: B008
):
    """Get all tracks for a sync record by sync ID."""
    try:
        async with AsyncSessionLocal() as session:
            stmt = (
                select(ScheduledPlaylistSync)
                .where(ScheduledPlaylistSync.id == sync_id)
                .options(
                    selectinload(ScheduledPlaylistSync.schedule_targets),
                    selectinload(ScheduledPlaylistSync.tracks).selectinload(PlaylistTrack.targets),
                )
            )
            result = await session.execute(stmt)
            sync_record = result.scalars().first()

            if not sync_record:
                raise HTTPException(status_code=404, detail=f"Sync {sync_id} not found")

            return _build_track_response(
                sync_record,
                playlist_id=sync_record.target_playlist_id or str(sync_id),
            )
    except HTTPException:
        raise
    except Exception as e:
        logger.error(f"Error getting sync tracks: {e}")
        raise HTTPException(status_code=500, detail=f"Failed to get sync tracks: {str(e)}") from e


@router.get("/{sync_id}/open-url", response_model=TargetOpenUrlResponse)
async def get_sync_open_url(
    sync_id: int,
    target_id: str = Query(default=DEFAULT_TARGET),
    _user: dict[str, Any] = Depends(get_current_user),  # noqa: B008
):
    """Return the target web-app URL to open the synced playlist.

    The URL is built at request time: the Plex route needs the server's
    machine identifier, which is fetched live (and cached on the target
    instance). Returns ``url: null`` when the target is not configured,
    the playlist has not been created yet, or the target is unreachable.
    """
    try:
        async with AsyncSessionLocal() as session:
            stmt = (
                select(ScheduledPlaylistSync)
                .where(ScheduledPlaylistSync.id == sync_id)
                .options(selectinload(ScheduledPlaylistSync.schedule_targets))
            )
            result = await session.execute(stmt)
            sync_record = result.scalars().first()

            if not sync_record:
                raise HTTPException(status_code=404, detail=f"Sync {sync_id} not found")

            playlist_id = next(
                (
                    t.playlist_id
                    for t in sync_record.schedule_targets
                    if t.target_id == target_id and t.playlist_id
                ),
                None,
            )
            if not playlist_id:
                return TargetOpenUrlResponse(url=None)

            target = await get_sync_target(target_id)
            url = await target.client_url(playlist_id)
            return TargetOpenUrlResponse(url=url)
    except HTTPException:
        raise
    except Exception as e:
        logger.warning("Failed to build open url for sync %s target %s: %s", sync_id, target_id, e)
        return TargetOpenUrlResponse(url=None)


# ─── Unmatched ───────────────────────────────────────────────────


@router.get("/unmatched-tracks", response_model=list[UnmatchedTrackOut])
async def get_unmatched_tracks(
    limit: int = Query(default=50, ge=1, le=200),
    _user: dict[str, Any] = Depends(get_current_user),  # noqa: B008
):
    """Get unmatched tracks from recent syncs for use in match rule testing."""
    async with AsyncSessionLocal() as session:
        stmt = (
            select(PlaylistTrack, ScheduledPlaylistSync.target_playlist_name)
            .join(
                ScheduledPlaylistSync,
                PlaylistTrack.sync_id == ScheduledPlaylistSync.id,
            )
            .where(~PlaylistTrack.targets.any())
            .order_by(
                ScheduledPlaylistSync.last_synced_at.desc().nullslast(),
                PlaylistTrack.position,
            )
            .limit(limit)
        )
        result = await session.execute(stmt)
        rows = result.all()

        return [
            UnmatchedTrackOut(
                sync_id=track.sync_id,
                sync_name=sync_name,
                source_title=track.source_title,
                source_artist=track.source_artist,
                source_album=track.source_album,
                source_duration_ms=track.source_duration_ms,
            )
            for track, sync_name in rows
        ]


# ─── History & Diff ──────────────────────────────────────────────


@router.get("/{sync_id}/history", response_model=list[SyncRunOut])
async def get_sync_history(
    sync_id: int,
    _user: dict[str, Any] = Depends(get_current_user),  # noqa: B008
):
    """Get sync run history for a scheduled sync."""
    async with AsyncSessionLocal() as session:
        sync_stmt = select(ScheduledPlaylistSync).where(ScheduledPlaylistSync.id == sync_id)
        sync_result = await session.execute(sync_stmt)
        if not sync_result.scalar_one_or_none():
            raise HTTPException(status_code=404, detail=f"Sync {sync_id} not found")

        stmt = (
            select(SyncRun)
            .where(SyncRun.sync_id == sync_id)
            .options(selectinload(SyncRun.tracks))
            .order_by(SyncRun.created_at.desc())
        )
        result = await session.execute(stmt)
        runs = result.scalars().all()

        return [
            SyncRunOut(
                id=run.id,
                sync_id=run.sync_id,
                target_id=run.target_id,
                matched_count=run.matched_count,
                failed_count=run.failed_count,
                created_at=run.created_at.isoformat() if run.created_at else None,
            )
            for run in runs
        ]


@router.get("/{sync_id}/diff", response_model=SyncDiffResponse)
async def get_sync_diff(
    sync_id: int,
    from_run: int = Query(..., description="Previous run ID to diff from"),
    to_run: int = Query(..., description="Current run ID to diff to"),
    _user: dict[str, Any] = Depends(get_current_user),  # noqa: B008
):
    """Compute the diff between two sync runs."""
    async with AsyncSessionLocal() as session:
        sync_stmt = select(ScheduledPlaylistSync).where(ScheduledPlaylistSync.id == sync_id)
        sync_result = await session.execute(sync_stmt)
        if not sync_result.scalar_one_or_none():
            raise HTTPException(status_code=404, detail=f"Sync {sync_id} not found")

        stmt = (
            select(SyncRun)
            .where(SyncRun.id.in_([from_run, to_run]))
            .options(selectinload(SyncRun.tracks).selectinload(SyncRunTrack.targets))
        )
        result = await session.execute(stmt)
        runs = {r.id: r for r in result.scalars().all()}

        if from_run not in runs or to_run not in runs:
            raise HTTPException(
                status_code=404,
                detail="One or both run IDs not found for this sync",
            )

        old_run = runs[from_run]
        new_run = runs[to_run]

        def track_key(t: SyncRunTrack) -> str | None:
            return t.item_id

        old_keys = {track_key(t): t for t in old_run.tracks}
        new_keys = {track_key(t): t for t in new_run.tracks}

        added: list[SyncDiffItem] = []
        removed: list[SyncDiffItem] = []
        unchanged: list[SyncDiffItem] = []

        for key, track in new_keys.items():
            if key in old_keys:
                old_track = old_keys[key]
                was_matched = len(old_track.targets) > 0
                is_matched = len(track.targets) > 0
                targets = [
                    TrackTarget(
                        target_id=t.target_id,
                        item_id=t.item_id,
                        title=t.title,
                        artist_name=t.artist_name,
                        album_name=t.album_name,
                        duration=t.duration,
                    )
                    for t in track.targets
                ]
                item = SyncDiffItem(
                    source_title=track.source_title,
                    source_artist=track.source_artist,
                    source_album=track.source_album,
                    targets=targets,
                )
                if is_matched and not was_matched:
                    added.append(item)
                elif was_matched and not is_matched:
                    removed.append(item)
                else:
                    unchanged.append(item)
            else:
                targets = [
                    TrackTarget(
                        target_id=t.target_id,
                        item_id=t.item_id,
                        title=t.title,
                        artist_name=t.artist_name,
                        album_name=t.album_name,
                        duration=t.duration,
                    )
                    for t in track.targets
                ]
                added.append(
                    SyncDiffItem(
                        source_title=track.source_title,
                        source_artist=track.source_artist,
                        source_album=track.source_album,
                        targets=targets,
                    )
                )

        for key, track in old_keys.items():
            if key not in new_keys:
                targets = [
                    TrackTarget(
                        target_id=t.target_id,
                        item_id=t.item_id,
                        title=t.title,
                        artist_name=t.artist_name,
                        album_name=t.album_name,
                        duration=t.duration,
                    )
                    for t in track.targets
                ]
                removed.append(
                    SyncDiffItem(
                        source_title=track.source_title,
                        source_artist=track.source_artist,
                        source_album=track.source_album,
                        targets=targets,
                    )
                )

        return SyncDiffResponse(
            added=added,
            removed=removed,
            unchanged=unchanged,
            from_run_id=from_run,
            to_run_id=to_run,
        )


# ─── Match ─────────────────────────────────────────────────────


@router.post("/{sync_id}/match-track", response_model=MatchTrackResponse)
async def match_track(
    sync_id: int,
    body: MatchTrackInput,
    target_id: str = Query(default=DEFAULT_TARGET, description="Target platform ID"),
    item_id: str | None = Query(default=None, description="Source track item ID"),
    _user: dict[str, Any] = Depends(get_current_user),  # noqa: B008
):
    """Dispatch a match task for a track via sync ID, running in a Celery worker."""
    try:
        async with AsyncSessionLocal() as session:
            stmt = select(ScheduledPlaylistSync).where(ScheduledPlaylistSync.id == sync_id)
            result = await session.execute(stmt)
            if not result.scalars().first():
                raise HTTPException(status_code=404, detail=f"Sync {sync_id} not found")

        task = match_track_task.delay(
            sync_id=sync_id,
            item_id=item_id,
            target_id=target_id,
        )

        return MatchTrackResponse(
            matched=False,
            message=f"Match queued for '{body.title}'",
            task_id=task.id,
        )
    except HTTPException:
        raise
    except Exception as e:
        logger.error(f"Error dispatching match for sync {sync_id}: {e}")
        raise HTTPException(status_code=500, detail=f"Failed to dispatch match: {str(e)}") from e
