"""Playlist endpoints — listing, search, sync, and track management."""

import logging

from fastapi import APIRouter, Depends, HTTPException, Query

from src.app.auth.dependencies import get_current_user
from src.app.core.models import TrackMetadata
from src.app.core.services.matcher import MatchEngine, get_active_rules
from src.app.core.sources.registry import SourceRegistry
from src.app.db import AsyncSessionLocal
from src.app.models import PlaylistTrack, ScheduledPlaylistSync, SyncRun, SyncRunTrack
from src.app.schemas.playlists import (
    PlaylistSearchResponse,
    PlaylistSyncRequest,
    PlaylistSyncResponse,
    PlaylistTracksResponse,
    RematchTrackInput,
    RematchTrackResponse,
    SyncDiffItem,
    SyncDiffResponse,
    SyncRunOut,
    TrackDetail,
    TrackMatch,
    TrackSource,
    UnmatchedTrackOut,
)
from src.app.services import get_plex_client, get_sync_target
from src.app.services.audit import log_event
from src.app.tasks import sync_playlists_task

logger = logging.getLogger(__name__)

router = APIRouter(prefix="/api/v1/playlists", tags=["playlists"])


# ─── Sources ────────────────────────────────────────────────────


@router.get("/sources")
async def list_sources(
    _user: dict = Depends(get_current_user),  # noqa: B008
):
    """List all available playlist source adapters."""
    return SourceRegistry.list_sources()


# ─── Listing & Search ────────────────────────────────────────────


@router.get("/unmatched-tracks", response_model=list[UnmatchedTrackOut])
async def get_unmatched_tracks(
    limit: int = Query(default=50, ge=1, le=200),
    _user: dict = Depends(get_current_user),  # noqa: B008
):
    """Get unmatched tracks from recent syncs for use in match rule testing."""
    from sqlalchemy import select

    async with AsyncSessionLocal() as session:
        stmt = (
            select(PlaylistTrack, ScheduledPlaylistSync.target_playlist_name)
            .join(
                ScheduledPlaylistSync,
                PlaylistTrack.sync_id == ScheduledPlaylistSync.id,
            )
            .where(PlaylistTrack.match_item_id.is_(None))
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


@router.get("/by-sync/{sync_id}/history", response_model=list[SyncRunOut])
async def get_sync_history(
    sync_id: int,
    _user: dict = Depends(get_current_user),  # noqa: B008
):
    """Get sync run history for a scheduled sync."""
    from sqlalchemy import select
    from sqlalchemy.orm import selectinload

    async with AsyncSessionLocal() as session:
        # Verify the sync exists
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
                matched_count=run.matched_count,
                failed_count=run.failed_count,
                created_at=run.created_at.isoformat() if run.created_at else None,
            )
            for run in runs
        ]


@router.get("/by-sync/{sync_id}/diff", response_model=SyncDiffResponse)
async def get_sync_diff(
    sync_id: int,
    from_run: int = Query(..., description="Previous run ID to diff from"),
    to_run: int = Query(..., description="Current run ID to diff to"),
    _user: dict = Depends(get_current_user),  # noqa: B008
):
    """Compute the diff between two sync runs."""
    from sqlalchemy import select
    from sqlalchemy.orm import selectinload

    async with AsyncSessionLocal() as session:
        # Verify sync exists
        sync_stmt = select(ScheduledPlaylistSync).where(ScheduledPlaylistSync.id == sync_id)
        sync_result = await session.execute(sync_stmt)
        if not sync_result.scalar_one_or_none():
            raise HTTPException(status_code=404, detail=f"Sync {sync_id} not found")

        # Load both runs with tracks
        stmt = (
            select(SyncRun)
            .where(SyncRun.id.in_([from_run, to_run]))
            .options(selectinload(SyncRun.tracks))
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

        def track_key(t: SyncRunTrack) -> tuple[str | None, str | None]:
            return (t.source_title, t.source_artist)

        old_keys = {track_key(t): t for t in old_run.tracks}
        new_keys = {track_key(t): t for t in new_run.tracks}

        added: list[SyncDiffItem] = []
        removed: list[SyncDiffItem] = []
        unchanged: list[SyncDiffItem] = []

        for key, track in new_keys.items():
            if key in old_keys:
                old_track = old_keys[key]
                was_matched = old_track.match_item_id is not None
                is_matched = track.match_item_id is not None
                item = SyncDiffItem(
                    source_title=track.source_title,
                    source_artist=track.source_artist,
                    source_album=track.source_album,
                    match_item_id=track.match_item_id,
                    match_title=track.match_title,
                    match_artist=track.match_artist,
                )
                if is_matched and not was_matched:
                    # Newly matched this run
                    added.append(item)
                elif was_matched and not is_matched:
                    # Lost its match this run
                    removed.append(item)
                else:
                    unchanged.append(item)
            else:
                added.append(SyncDiffItem(
                    source_title=track.source_title,
                    source_artist=track.source_artist,
                    source_album=track.source_album,
                    match_item_id=track.match_item_id,
                    match_title=track.match_title,
                    match_artist=track.match_artist,
                ))

        for key, track in old_keys.items():
            if key not in new_keys:
                removed.append(SyncDiffItem(
                    source_title=track.source_title,
                    source_artist=track.source_artist,
                    source_album=track.source_album,
                    match_item_id=track.match_item_id,
                    match_title=track.match_title,
                    match_artist=track.match_artist,
                ))

        return SyncDiffResponse(
            added=added,
            removed=removed,
            unchanged=unchanged,
            from_run_id=from_run,
            to_run_id=to_run,
        )


@router.get("/")
async def list_user_playlists(
    _user: dict = Depends(get_current_user),  # noqa: B008
):
    """List all playlists the user owns in Plex."""
    try:
        plex_client = await get_plex_client()
        playlists = await plex_client.search_playlists("")
        logger.info(f"Listed {len(playlists)} playlists")
        return playlists
    except Exception as e:
        logger.error(f"Error listing playlists: {e}")
        raise HTTPException(status_code=500, detail=f"Failed to list playlists: {str(e)}") from e


@router.post("/search", response_model=PlaylistSearchResponse)
async def search_playlists(
    query: str,
    _user: dict = Depends(get_current_user),  # noqa: B008
):
    """Search Plex playlists by title or keywords."""
    try:
        plex_client = await get_plex_client()
        results = await plex_client.search_playlists(query)
        if not results:
            raise HTTPException(status_code=404, detail=f"No playlists found matching '{query}'")
        return PlaylistSearchResponse(message="Search successful", playlists=results)
    except HTTPException:
        raise
    except Exception as e:
        logger.error(f"Error searching playlists: {e}")
        raise HTTPException(status_code=500, detail=f"Failed to search playlists: {str(e)}") from e


# ─── Sync ────────────────────────────────────────────────────────


@router.post("/sync", response_model=PlaylistSyncResponse)
async def trigger_playlist_sync(
    sync_request: PlaylistSyncRequest,
    _user: dict = Depends(get_current_user),  # noqa: B008
):
    """Initiate a background sync job for a playlist."""
    try:
        is_yt_music = (
            sync_request.source == "youtube_music"
            and "music.youtube.com" not in sync_request.playlist_url
        )
        if is_yt_music:
            raise HTTPException(status_code=422, detail="Invalid YouTube Music URL format.")

        task = sync_playlists_task.delay(
            sync_request.playlist_url,
            sync_request.source,
            sync_request.replace_existing,
            sync_request.schedule_id,
            sync_request.target_playlist_name,
        )
        logger.info(f"Triggered sync task {task.id} for {sync_request.source} playlist")

        await log_event(
            event_type="sync.manually_triggered",
            resource_type="playlist",
            resource_id=sync_request.schedule_id and str(sync_request.schedule_id),
            summary=(
                f"Sync triggered for {sync_request.source}"
                f" playlist — {sync_request.playlist_url}"
            ),
            details={
                "playlist_url": sync_request.playlist_url,
                "source": sync_request.source,
                "replace_existing": sync_request.replace_existing,
                "schedule_id": sync_request.schedule_id,
            },
        )

        return PlaylistSyncResponse(
            message="Sync job started successfully.",
            task_id=task.id,
            status_url=f"/api/v1/playlists/status/{task.id}",
        )
    except HTTPException:
        raise
    except Exception as e:
        logger.error(f"Error triggering sync: {e}")
        raise HTTPException(status_code=500, detail=f"Failed to start sync job: {str(e)}") from e


@router.get("/status/{task_id}")
async def get_sync_status(
    task_id: str,
    _user: dict = Depends(get_current_user),  # noqa: B008
):
    """Poll the Celery backend for sync job status and result."""
    from src.app.tasks import get_sync_status_task

    return get_sync_status_task(task_id)


# ─── Tracks ──────────────────────────────────────────────────────


@router.get("/{playlist_id}/tracks", response_model=PlaylistTracksResponse)
async def get_playlist_tracks(
    playlist_id: str,
    _user: dict = Depends(get_current_user),  # noqa: B008
):
    """Get all tracks for a playlist with match status details."""
    try:
        plex_client = await get_plex_client()
        plex_tracks = await plex_client.get_items_in_playlist(playlist_id)

        async with AsyncSessionLocal() as session:
            from sqlalchemy import select
            from sqlalchemy.orm import selectinload

            stmt = (
                select(ScheduledPlaylistSync)
                .where(ScheduledPlaylistSync.target_playlist_id == playlist_id)
                .options(selectinload(ScheduledPlaylistSync.tracks))
            )
            result = await session.execute(stmt)
            sync_record = result.scalars().first()

            if sync_record and len(sync_record.tracks) > 0:
                all_rows: list[PlaylistTrack] = list(sync_record.tracks)
                matched_rows = [r for r in all_rows if r.match_item_id is not None]
                unmatched_rows = [r for r in all_rows if r.match_item_id is None]
                matched_count = len(matched_rows)
                failed_count = len(unmatched_rows)
            else:
                matched_rows = []
                unmatched_rows = []
                matched_count = 0
                failed_count = len(plex_tracks)

            matched_by_id: dict[str, PlaylistTrack] = {
                r.match_item_id: r for r in matched_rows if r.match_item_id
            }

            track_details: list[TrackDetail] = []

            if plex_tracks:
                formatted_matched = [
                    {**t, "status": "matched", "match_rate": "✓ Matched"}
                    for t in plex_tracks
                ]
                for t in formatted_matched:
                    db_row = matched_by_id.get(t.get("plex_id"))
                    track_details.append(TrackDetail(
                        source=TrackSource(
                            title=db_row.source_title,
                            artist_name=db_row.source_artist,
                            album_name=db_row.source_album,
                            duration_ms=db_row.source_duration_ms,
                            source_id=db_row.source_id,
                        ) if db_row else None,
                        match=TrackMatch(
                            plex_id=t.get("plex_id"),
                            title=t.get("title"),
                            artist_name=t.get("artist_name"),
                            album_name=t.get("album_name"),
                            duration=t.get("duration"),
                        ),
                    ))
            else:
                formatted_matched = []
                for r in matched_rows:
                    formatted_matched.append({
                        "plex_id": r.match_item_id,
                        "title": r.match_title or r.source_title or "Unknown",
                        "artist_name": r.match_artist or r.source_artist or "Unknown",
                        "album_name": r.match_album or r.source_album or "Unknown",
                        "duration": (
                            r.match_duration
                            if r.match_duration is not None
                            else (r.source_duration_ms // 1000
                                  if r.source_duration_ms else 0)
                        ),
                        "status": "matched",
                        "match_rate": "✓ Matched",
                    })
                    track_details.append(TrackDetail(
                        source=TrackSource(
                            title=r.source_title,
                            artist_name=r.source_artist,
                            album_name=r.source_album,
                            duration_ms=r.source_duration_ms,
                            source_id=r.source_id,
                        ),
                        match=TrackMatch(
                            plex_id=r.match_item_id,
                            title=r.match_title,
                            artist_name=r.match_artist,
                            album_name=r.match_album,
                            duration=r.match_duration,
                        ),
                    ))

            formatted_unmatched = [
                {
                    "title": r.source_title or "Unknown",
                    "artist_name": r.source_artist or "Unknown",
                    "album_name": r.source_album or "Unknown",
                    "duration": (r.source_duration_ms // 1000) if r.source_duration_ms else 0,
                    "status": "unmatched",
                    "match_rate": "✗ Unmatched",
                }
                for r in unmatched_rows
            ]

            for r in unmatched_rows:
                track_details.append(TrackDetail(
                    source=TrackSource(
                        title=r.source_title,
                        artist_name=r.source_artist,
                        album_name=r.source_album,
                        duration_ms=r.source_duration_ms,
                        source_id=r.source_id,
                    ),
                    match=None,
                ))

            total_tracks = matched_count + failed_count
            match_rate = f"{matched_count}/{total_tracks}" if total_tracks > 0 else "0/0"
            match_percentage = int(matched_count / total_tracks * 100) if total_tracks > 0 else 0

            source_name = sync_record.source if sync_record else "unknown"

            return PlaylistTracksResponse(
                playlist_id=playlist_id,
                source=source_name,
                tracks=formatted_matched + formatted_unmatched,
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
    except HTTPException:
        raise
    except Exception as e:
        logger.error(f"Error getting playlist tracks: {e}")
        raise HTTPException(
            status_code=500,
            detail=f"Failed to get playlist tracks: {str(e)}",
        ) from e


@router.get("/by-sync/{sync_id}/tracks", response_model=PlaylistTracksResponse)
async def get_sync_tracks(
    sync_id: int,
    _user: dict = Depends(get_current_user),  # noqa: B008
):
    """Get all tracks for a sync record by sync ID."""
    try:
        from sqlalchemy import select
        from sqlalchemy.orm import selectinload

        async with AsyncSessionLocal() as session:
            stmt = (
                select(ScheduledPlaylistSync)
                .where(ScheduledPlaylistSync.id == sync_id)
                .options(selectinload(ScheduledPlaylistSync.tracks))
            )
            result = await session.execute(stmt)
            sync_record = result.scalars().first()

            if not sync_record:
                raise HTTPException(status_code=404, detail=f"Sync {sync_id} not found")

            all_rows: list[PlaylistTrack] = list(sync_record.tracks)
            matched_rows = [r for r in all_rows if r.match_item_id is not None]
            unmatched_rows = [r for r in all_rows if r.match_item_id is None]
            matched_count = len(matched_rows)
            failed_count = len(unmatched_rows)

            track_details: list[TrackDetail] = []

            formatted_matched = []
            for r in matched_rows:
                formatted_matched.append({
                    "plex_id": r.match_item_id,
                    "title": r.match_title or r.source_title or "Unknown",
                    "artist_name": r.match_artist or r.source_artist or "Unknown",
                    "album_name": r.match_album or r.source_album or "Unknown",
                    "duration": (
                        r.match_duration
                        if r.match_duration is not None
                        else (r.source_duration_ms // 1000
                              if r.source_duration_ms else 0)
                    ),
                    "status": "matched",
                    "match_rate": "✓ Matched",
                })
                track_details.append(TrackDetail(
                    source=TrackSource(
                        title=r.source_title,
                        artist_name=r.source_artist,
                        album_name=r.source_album,
                        duration_ms=r.source_duration_ms,
                        source_id=r.source_id,
                    ),
                    match=TrackMatch(
                        plex_id=r.match_item_id,
                        title=r.match_title,
                        artist_name=r.match_artist,
                        album_name=r.match_album,
                        duration=r.match_duration,
                    ),
                ))

            formatted_unmatched = [
                {
                    "title": r.source_title or "Unknown",
                    "artist_name": r.source_artist or "Unknown",
                    "album_name": r.source_album or "Unknown",
                    "duration": (r.source_duration_ms // 1000) if r.source_duration_ms else 0,
                    "status": "unmatched",
                    "match_rate": "✗ Unmatched",
                }
                for r in unmatched_rows
            ]

            for r in unmatched_rows:
                track_details.append(TrackDetail(
                    source=TrackSource(
                        title=r.source_title,
                        artist_name=r.source_artist,
                        album_name=r.source_album,
                        duration_ms=r.source_duration_ms,
                        source_id=r.source_id,
                    ),
                    match=None,
                ))

            total_tracks = matched_count + failed_count
            match_rate = f"{matched_count}/{total_tracks}" if total_tracks > 0 else "0/0"
            match_percentage = int(matched_count / total_tracks * 100) if total_tracks > 0 else 0

            return PlaylistTracksResponse(
                playlist_id=sync_record.target_playlist_id or str(sync_id),
                source=sync_record.source,
                tracks=formatted_matched + formatted_unmatched,
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
    except HTTPException:
        raise
    except Exception as e:
        logger.error(f"Error getting sync tracks: {e}")
        raise HTTPException(status_code=500, detail=f"Failed to get sync tracks: {str(e)}") from e


# ─── Rematch ─────────────────────────────────────────────────────


@router.post("/by-sync/{sync_id}/rematch-track", response_model=RematchTrackResponse)
async def rematch_sync_track(
    sync_id: int,
    body: RematchTrackInput,
    _user: dict = Depends(get_current_user),  # noqa: B008
):
    """Rematch a track via sync ID, updating the DB and Plex playlist."""
    try:
        target = await get_sync_target()

        async with AsyncSessionLocal() as session:
            from sqlalchemy import select
            from sqlalchemy.orm import selectinload

            stmt = (
                select(ScheduledPlaylistSync)
                .where(ScheduledPlaylistSync.id == sync_id)
                .options(selectinload(ScheduledPlaylistSync.tracks))
            )
            result = await session.execute(stmt)
            sync_record = result.scalars().first()

            if not sync_record:
                raise HTTPException(status_code=404, detail=f"Sync {sync_id} not found")

            track = TrackMetadata(
                title=body.title,
                artist_name=body.artist_name,
                album_name=body.album_name or "",
            )

            match = None
            try:
                rules = await get_active_rules()
                if rules:
                    engine = MatchEngine(target)
                    matches = await engine.run(track)
                    if matches:
                        match = matches[0]
            except Exception:
                logger.warning("MatchEngine failed during rematch, falling back to direct search")

            if not match:
                hits = await target.search_library(
                    title=body.title,
                    artist=body.artist_name,
                    album=body.album_name,
                )
                if hits:
                    match = hits[0]

            if not match:
                msg = f"No match found for '{body.title}'"
                return RematchTrackResponse(
                    matched=False, message=msg,
                )

            plex_id = match.get("plex_id")

            if plex_id and sync_record.target_playlist_id:
                await target.add_items_to_playlist(sync_record.target_playlist_id, [plex_id])

            track_stmt = select(PlaylistTrack).where(
                PlaylistTrack.sync_id == sync_id,
                PlaylistTrack.match_item_id.is_(None),
                PlaylistTrack.source_title == body.title,
            )
            if body.artist_name:
                track_stmt = track_stmt.where(PlaylistTrack.source_artist == body.artist_name)
            track_stmt = track_stmt.limit(1)
            result = await session.execute(track_stmt)
            if db_row := result.scalars().first():
                db_row.match_item_id = plex_id
                db_row.match_title = match.get("title")
                db_row.match_artist = match.get("artist_name")
                db_row.match_album = match.get("album_name")
                match_duration = match.get("duration") or (
                    match.get("duration_ms", 0) // 1000 if match.get("duration_ms") else None
                )
                db_row.match_duration = match_duration
                await session.commit()

            await log_event(
                event_type="track.rematched",
                resource_type="track",
                resource_id=plex_id,
                summary=(
                    f"Track '{body.title}' by {body.artist_name or '?'}"
                    f" rematched to '{match.get('title', '')}'"
                    f" in sync {sync_id}"
                ),
            )

            return RematchTrackResponse(
                matched=True,
                message=f"Matched '{body.title}' to '{match.get('title', '')}'",
                track={
                    "plex_id": plex_id,
                    "title": match.get("title"),
                    "artist_name": match.get("artist_name"),
                    "album_name": match.get("album_name"),
                },
            )
    except HTTPException:
        raise
    except Exception as e:
        logger.error(f"Error rematching track for sync {sync_id}: {e}")
        raise HTTPException(status_code=500, detail=f"Failed to rematch track: {str(e)}") from e


@router.post("/{playlist_id}/rematch-track", response_model=RematchTrackResponse)
async def rematch_track(
    playlist_id: str,
    body: RematchTrackInput,
    _user: dict = Depends(get_current_user),  # noqa: B008
):
    """Rematch a track via playlist ID, updating the DB and Plex playlist."""
    try:
        target = await get_sync_target()

        track = TrackMetadata(
            title=body.title,
            artist_name=body.artist_name,
            album_name=body.album_name or "",
        )

        match = None
        try:
            rules = await get_active_rules()
            if rules:
                engine = MatchEngine(target)
                matches = await engine.run(track)
                if matches:
                    match = matches[0]
        except Exception:
            logger.warning("MatchEngine failed during rematch, falling back to direct search")

        if not match:
            hits = await target.search_library(
                title=body.title,
                artist=body.artist_name,
                album=body.album_name,
            )
            if hits:
                match = hits[0]

        if not match:
            return RematchTrackResponse(matched=False, message=f"No match found for '{body.title}'")

        plex_id = match.get("plex_id")
        if plex_id:
            await target.add_items_to_playlist(playlist_id, [plex_id])

        async with AsyncSessionLocal() as session:
            from sqlalchemy import select

            sync_stmt = select(ScheduledPlaylistSync).where(
                ScheduledPlaylistSync.target_playlist_id == playlist_id
            )
            sync_result = await session.execute(sync_stmt)
            sync_record = sync_result.scalars().first()

            if sync_record:
                track_stmt = select(PlaylistTrack).where(
                    PlaylistTrack.sync_id == sync_record.id,
                    PlaylistTrack.match_item_id.is_(None),
                    PlaylistTrack.source_title == body.title,
                )
                if body.artist_name:
                    track_stmt = track_stmt.where(PlaylistTrack.source_artist == body.artist_name)
                track_stmt = track_stmt.limit(1)
                result = await session.execute(track_stmt)
                if db_row := result.scalars().first():
                    db_row.match_item_id = plex_id
                    db_row.match_title = match.get("title")
                    db_row.match_artist = match.get("artist_name")
                    db_row.match_album = match.get("album_name")
                    match_duration = match.get("duration") or (
                        match.get("duration_ms", 0) // 1000 if match.get("duration_ms") else None
                    )
                    db_row.match_duration = match_duration
                    await session.commit()

        await log_event(
            event_type="track.rematched",
            resource_type="track",
            resource_id=plex_id,
            summary=(
                f"Track '{body.title}' by {body.artist_name or '?'}"
                f" rematched to '{match.get('title', '')}'"
                f" in playlist {playlist_id}"
            ),
        )

        return RematchTrackResponse(
            matched=True,
            message=f"Matched '{body.title}' to '{match.get('title', '')}'",
            track={
                "plex_id": plex_id,
                "title": match.get("title"),
                "artist_name": match.get("artist_name"),
                "album_name": match.get("album_name"),
            },
        )
    except HTTPException:
        raise
    except Exception as e:
        logger.error(f"Error rematching track: {e}")
        raise HTTPException(status_code=500, detail=f"Failed to rematch track: {str(e)}") from e
