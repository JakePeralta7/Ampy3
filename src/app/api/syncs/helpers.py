"""Shared helpers for sync endpoints."""

import logging
from datetime import UTC, datetime
from typing import Any

from fastapi import HTTPException
from sqlalchemy import select

from src.app.constants import (
    SOURCE_DEEZER,
    SOURCE_DEEZER_DISPLAY,
    SOURCE_YOUTUBE_MUSIC,
    SOURCE_YOUTUBE_MUSIC_DISPLAY,
)
from src.app.models import PlaylistTrack, ScheduledPlaylistSync
from src.app.schemas.playlists import TrackDetail, TrackSource, TrackTarget
from src.app.schemas.syncs import SyncDiffItem, SyncTracksResponse

logger = logging.getLogger(__name__)

_SOURCE_DISPLAY_NAMES = {
    SOURCE_YOUTUBE_MUSIC: SOURCE_YOUTUBE_MUSIC_DISPLAY,
    SOURCE_DEEZER: SOURCE_DEEZER_DISPLAY,
}


async def _get_user_sync_or_404(session, sync_id: int, user_id: str) -> ScheduledPlaylistSync:
    """Load a sync scoped to its owner, hiding foreign rows behind a 404."""
    result = await session.execute(
        select(ScheduledPlaylistSync).where(
            ScheduledPlaylistSync.id == sync_id,
            ScheduledPlaylistSync.user_id == user_id,
        )
    )
    sync_record = result.scalar_one_or_none()
    if not sync_record:
        raise HTTPException(status_code=404, detail=f"Sync {sync_id} not found")
    return sync_record


def _track_targets(track) -> list[TrackTarget]:
    """Build the API target list for a stored run track."""
    return [
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


def _sync_diff_item(track) -> SyncDiffItem:
    """Build one side of a run diff from a stored run track."""
    return SyncDiffItem(
        source_title=track.source_title,
        source_artist=track.source_artist,
        source_album=track.source_album,
        targets=_track_targets(track),
    )


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


def _newest_run_per_target(runs: list) -> list:
    """Keep only the newest run per target, preserving execution order.

    A retried ``sync_target_task`` creates a fresh SyncRun for every attempt
    (all sharing the target's ``execution_id``); the newest row is the final
    attempt's outcome, so it alone should be shown in the pipeline.
    """
    newest: dict[str, Any] = {}
    for run in runs:
        current = newest.get(run.target_id)
        if current is None or run.id > current.id:
            newest[run.target_id] = run
    return [r for r in runs if newest.get(r.target_id) is r]


def _select_execution(runs: list, run_id: int) -> list:
    """All runs belonging to the same execution as ``run_id``.

    Executions are grouped exactly by their ``execution_id`` (generated once
    per sync invocation by the orchestrator). Runs without one predate that
    identity and are shown alone — no timestamp heuristics. Retried targets
    collapse to their final attempt.
    """
    for run in runs:
        if run.id == run_id:
            if not run.execution_id:
                return [run]
            matched = [r for r in runs if r.execution_id == run.execution_id]
            return _newest_run_per_target(matched)
    return []


def _parse_fetch_started(started_iso: str | None) -> datetime | None:
    """Parse a phase ``started_at`` into an aware UTC datetime, or ``None``."""
    if not started_iso:
        return None
    try:
        ts = datetime.fromisoformat(started_iso)
    except ValueError:
        return None
    return ts if ts.tzinfo else ts.replace(tzinfo=UTC)


_STALE_FETCH_PHASE_SECONDS = 1800


def _is_stale_fetch_phase(fetch_phase: dict | None) -> bool:
    """Check if fetch phase is stale (running > 30 minutes)."""
    if not fetch_phase:
        return False
    phase_running = fetch_phase.get("status") == "running"
    phase_started = _parse_fetch_started(fetch_phase.get("started_at")) if fetch_phase else None
    return bool(
        phase_running
        and phase_started is not None
        and (datetime.now(UTC) - phase_started).total_seconds() > _STALE_FETCH_PHASE_SECONDS
    )


def get_source_display_name(source: str) -> str:
    """Get display name for a source."""
    return _SOURCE_DISPLAY_NAMES.get(source, source)
