"""Sync tracks endpoints — retrieving track details and open URLs."""

import logging
from typing import Any

from fastapi import APIRouter, Depends, HTTPException, Query
from sqlalchemy import select
from sqlalchemy.orm import selectinload

from src.app.api.syncs.helpers import _build_track_response
from src.app.auth.dependencies import get_current_user
from src.app.constants import DEFAULT_TARGET
from src.app.models import PlaylistTrack, ScheduledPlaylistSync
from src.app.schemas.syncs import TargetOpenUrlResponse, UnmatchedTrackOut
from src.app.services import get_sync_target

logger = logging.getLogger(__name__)

router = APIRouter()


@router.get("/{sync_id}/tracks", response_model=Any)
async def get_sync_tracks(
    sync_id: int,
    user: dict[str, Any] = Depends(get_current_user),  # noqa: B008
):
    """Get all tracks for a sync record by sync ID."""
    try:
        from src.app.api.syncs import AsyncSessionLocal

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
            if sync_record.user_id != user["plex_user_id"]:
                raise HTTPException(status_code=404, detail=f"Sync {sync_id} not found")

            return _build_track_response(
                sync_record,
                playlist_id=sync_record.target_playlist_id or str(sync_id),
            )
    except HTTPException:
        raise
    except Exception as e:
        logger.error(f"Error getting sync tracks: {e}")
        raise HTTPException(status_code=500, detail="Failed to get sync tracks") from e


@router.get("/{sync_id}/open-url", response_model=TargetOpenUrlResponse)
async def get_sync_open_url(
    sync_id: int,
    target_id: str = Query(default=DEFAULT_TARGET),
    user: dict[str, Any] = Depends(get_current_user),  # noqa: B008
):
    """Return the target web-app URL to open the synced playlist.

    The URL is built at request time: the Plex route needs the server's
    machine identifier, which is fetched live (and cached on the target
    instance). Returns ``url: null`` when the target is not configured,
    the playlist has not been created yet, or the target is unreachable.
    """
    try:
        from src.app.api.syncs import AsyncSessionLocal

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
            if sync_record.user_id != user["plex_user_id"]:
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


@router.get("/unmatched-tracks", response_model=list[UnmatchedTrackOut])
async def get_unmatched_tracks(
    limit: int = Query(default=50, ge=1, le=200),
    _user: dict[str, Any] = Depends(get_current_user),  # noqa: B008
):
    """Get unmatched tracks from recent syncs for use in match rule testing."""
    from src.app.api.syncs import AsyncSessionLocal

    async with AsyncSessionLocal() as session:
        stmt = (
            select(PlaylistTrack, ScheduledPlaylistSync.target_playlist_name)
            .join(
                ScheduledPlaylistSync,
                PlaylistTrack.sync_id == ScheduledPlaylistSync.id,
            )
            .where(
                ~PlaylistTrack.targets.any(),
                ScheduledPlaylistSync.user_id == _user["plex_user_id"],  # ← user filter
            )
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
