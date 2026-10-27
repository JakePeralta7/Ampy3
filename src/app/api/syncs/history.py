"""Sync history, pipeline, and diff endpoints."""

import asyncio
import logging
from typing import Any

from fastapi import APIRouter, Depends, HTTPException, Query
from sqlalchemy import func, select
from sqlalchemy.orm import selectinload

from src.app.api.syncs.helpers import (
    _get_user_sync_or_404,
    _is_stale_fetch_phase,
    _newest_run_per_target,
    _parse_fetch_started,
    _select_execution,
    _sync_diff_item,
    get_source_display_name,
)
from src.app.auth.dependencies import get_current_user
from src.app.models import PlaylistTrack, SyncRun, SyncRunTrack
from src.app.schemas.syncs import (
    PipelineStatusResponse,
    PipelineTargetStatus,
    PipelineTaskStatus,
    SyncDiffItem,
    SyncDiffResponse,
    SyncRunOut,
)
from src.app.services.sync_tasks import get_fetch_phase_async

logger = logging.getLogger(__name__)

router = APIRouter()


@router.get("/{sync_id}/history", response_model=list[SyncRunOut])
async def get_sync_history(
    sync_id: int,
    user: dict[str, Any] = Depends(get_current_user),  # noqa: B008
):
    """Get sync run history for a scheduled sync."""
    from src.app.api.syncs import AsyncSessionLocal

    async with AsyncSessionLocal() as session:
        await _get_user_sync_or_404(session, sync_id, user["plex_user_id"])

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
                status=run.status,
                matched_count=run.matched_count,
                failed_count=run.failed_count,
                error=run.error_message,
                created_at=run.created_at.isoformat() if run.created_at else None,
            )
            for run in runs
        ]


@router.get("/{sync_id}/pipeline", response_model=PipelineStatusResponse)
async def get_sync_pipeline(
    sync_id: int,
    run_id: int | None = Query(
        default=None, description="Sync run ID whose execution pipeline to show"
    ),
    user: dict[str, Any] = Depends(get_current_user),  # noqa: B008
):
    """Return the pipeline (fetch → per-target match/sync) for a sync execution.

    Without ``run_id``, the latest (or in-progress) execution is returned: the
    runs whose ``execution_id`` matches the recorded FetchPhase's. With
    ``run_id``, all sibling runs sharing the selected run's ``execution_id``
    are returned; runs predating ``execution_id`` are shown alone.
    """
    from src.app.api.syncs import AsyncSessionLocal

    async with AsyncSessionLocal() as session:
        sync_record = await _get_user_sync_or_404(session, sync_id, user["plex_user_id"])

        runs_stmt = (
            select(SyncRun).where(SyncRun.sync_id == sync_id).order_by(SyncRun.created_at.asc())
        )
        runs_result = await session.execute(runs_stmt)
        runs = list(runs_result.scalars().all())

        fetch_phase = await get_fetch_phase_async(sync_id)
        phase_exec_id = fetch_phase.get("execution_id") if fetch_phase else None
        target_runs: list[SyncRun] = []
        selected_execution_id: str | None = None
        if run_id is not None:
            for run in runs:
                if run.id == run_id:
                    selected_execution_id = run.execution_id
                    break
            target_runs = _select_execution(runs, run_id)
            if not target_runs:
                raise HTTPException(
                    status_code=404, detail=f"Run {run_id} not found for sync {sync_id}"
                )
        elif phase_exec_id:
            target_runs = [r for r in runs if r.execution_id == phase_exec_id]

        count_stmt = (
            select(func.count()).select_from(PlaylistTrack).where(PlaylistTrack.sync_id == sync_id)
        )
        track_count = (await session.execute(count_stmt)).scalar_one()
        source_label = get_source_display_name(sync_record.source)

        is_live_execution = run_id is None or (
            selected_execution_id is not None and selected_execution_id == phase_exec_id
        )
        phase_stale = _is_stale_fetch_phase(fetch_phase)
        if fetch_phase and is_live_execution and not phase_stale:
            orchestrator_status = fetch_phase.get("status", "pending")
            orchestrator = PipelineTaskStatus(
                status=orchestrator_status,
                label=f"Fetch {source_label}",
                detail=f"{track_count} track{'s' if track_count != 1 else ''}",
                started_at=fetch_phase.get("started_at"),
                completed_at=fetch_phase.get("completed_at"),
            )
        else:
            orchestrator = PipelineTaskStatus(
                status="completed" if target_runs else "pending",
                label=f"Fetch {source_label}",
                detail=f"{track_count} track{'s' if track_count != 1 else ''}",
                completed_at=(
                    target_runs[0].created_at.isoformat()
                    if target_runs and target_runs[0].created_at
                    else None
                ),
            )

        return PipelineStatusResponse(
            sync_id=sync_id,
            source=sync_record.source,
            playlist_title=sync_record.target_playlist_name,
            track_count=track_count,
            orchestrator=orchestrator,
            targets=[
                PipelineTargetStatus(
                    run_id=r.id,
                    target_id=r.target_id,
                    status=r.status,
                    matched_count=r.matched_count,
                    failed_count=r.failed_count,
                    error=r.error_message,
                    created_at=r.created_at.isoformat() if r.created_at else None,
                )
                for r in target_runs
            ],
        )


@router.get("/{sync_id}/diff", response_model=SyncDiffResponse)
async def get_sync_diff(
    sync_id: int,
    from_run: int = Query(..., description="Previous run ID to diff from"),
    to_run: int = Query(..., description="Current run ID to diff to"),
    user: dict[str, Any] = Depends(get_current_user),  # noqa: B008
):
    """Compute the diff between two sync runs."""
    from src.app.api.syncs import AsyncSessionLocal

    async with AsyncSessionLocal() as session:
        await _get_user_sync_or_404(session, sync_id, user["plex_user_id"])

        stmt = (
            select(SyncRun)
            .where(
                SyncRun.sync_id == sync_id,
                SyncRun.id.in_([from_run, to_run]),
            )
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
            item = _sync_diff_item(track)
            if key not in old_keys:
                added.append(item)
                continue

            was_matched = len(old_keys[key].targets) > 0
            is_matched = len(track.targets) > 0
            if is_matched and not was_matched:
                added.append(item)
            elif was_matched and not is_matched:
                removed.append(item)
            else:
                unchanged.append(item)

        removed.extend(
            _sync_diff_item(track) for key, track in old_keys.items() if key not in new_keys
        )

        return SyncDiffResponse(
            added=added,
            removed=removed,
            unchanged=unchanged,
            from_run_id=from_run,
            to_run_id=to_run,
        )
