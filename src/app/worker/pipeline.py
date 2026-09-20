"""SyncPipeline — composes SyncPhase instances into a full sync flow.

Two modes of operation:
1. ``fetch_source()`` — Phase 1 only (called once per sync invocation)
2. ``run_target()`` — Phases 2+3 (called once per target)
"""

from __future__ import annotations

import logging
from typing import Any

from sqlalchemy import insert, select

from src.app.models import ScheduledPlaylistSync, SyncRun, SyncRunTrack
from src.app.worker.context import SyncContext
from src.app.worker.errors import (
    FinalizeError,
    MatchError,
    SyncScheduleMissingError,
    SyncSourceError,
    SyncValidationError,
)
from src.app.worker.phases import FetchPhase, FinalizePhase, MatchPhase, PhaseResult, SyncPhase

logger = logging.getLogger(__name__)


class SyncPipeline:
    """Orchestrates the sync flow by composing SyncPhase instances.

    Phases are injectable — different pipeline configurations can be used
    for full sync, re-match, or dry-run scenarios.
    """

    def __init__(
        self,
        ctx: SyncContext,
        phases: list[SyncPhase] | None = None,
    ) -> None:
        self.ctx = ctx
        self.phases = phases or [MatchPhase(), FinalizePhase()]

    @classmethod
    def fetch_source(
        cls,
        source_url: str,
        source: str,
        schedule_id: int | None,
        target_ids: list[str],
        playlist_title: str = "",
    ) -> dict[str, Any]:
        """Run Phase 1 (FetchPhase) and return track data.

        Called once per sync invocation, shared across all targets.
        """
        ctx = SyncContext(
            sync_id=0,
            target_id=target_ids[0],
            playlist_title=playlist_title,
        )
        phase = FetchPhase()
        result = phase.execute(
            ctx,
            {
                "source_url": source_url,
                "source": source,
                "schedule_id": schedule_id,
                "target_ids": target_ids,
            },
        )
        if not result.success:
            raise SyncValidationError(f"FetchPhase failed: {result.error}")
        logger.info(
            "Fetched %d tracks from %s (%s)",
            len(result.data["track_items"]),
            source,
            source_url,
        )
        return result.data

    def run_target(
        self,
        track_items: list[str],
    ) -> dict[str, Any]:
        """Run all target phases sequentially (ensure_sync_run → match → finalize)."""
        self._ensure_sync_run()

        input_data: dict[str, Any] = {"track_items": track_items}
        for phase in self.phases:
            logger.info(
                "Running %s for sync %d target %s",
                phase.__class__.__name__,
                self.ctx.sync_id,
                self.ctx.target_id,
            )
            result = phase.execute(self.ctx, input_data)
            if not result.success:
                phase_name = phase.__class__.__name__
                if phase_name == "MatchPhase":
                    raise MatchError(f"MatchPhase failed: {result.error}")
                if phase_name == "FinalizePhase":
                    raise FinalizeError(f"FinalizePhase failed: {result.error}")
                raise RuntimeError(f"Phase {phase_name} failed: {result.error}")
            input_data.update(result.data)

        return input_data

    def _ensure_sync_run(self) -> bool:
        """Create or reuse a SyncRun with SyncRunTrack history for this target.

        Reuses an existing non-terminal SyncRun with the same (sync_id, target_id, execution_id)
        to provide idempotency on retries and worker redelivery.

        Returns True when a new SyncRun was created (and its SyncRunTrack batch
        should be recorded); False when an existing run was reused (its history
        batch is already persisted, so recording a second copy would duplicate
        earlier rows).
        """
        with self.ctx.session() as db:
            if db.get(ScheduledPlaylistSync, self.ctx.sync_id) is None:
                raise SyncScheduleMissingError(self.ctx.sync_id)

            # Check for existing non-terminal run with same execution_id (idempotency)
            existing = db.execute(
                select(SyncRun).where(
                    SyncRun.sync_id == self.ctx.sync_id,
                    SyncRun.target_id == self.ctx.target_id,
                    SyncRun.execution_id == self.ctx.execution_id,
                    SyncRun.status.in_(("running", "pending")),
                )
            ).scalar_one_or_none()

            if existing:
                run = existing
                run_created = False
                logger.info(
                    "Reusing existing SyncRun id=%d for sync %d target %s (execution_id=%s)",
                    run.id,
                    self.ctx.sync_id,
                    self.ctx.target_id,
                    self.ctx.execution_id,
                )
            else:
                run = SyncRun(
                    sync_id=self.ctx.sync_id,
                    target_id=self.ctx.target_id,
                    status="running",
                    matched_count=0,
                    failed_count=0,
                    execution_id=self.ctx.execution_id,
                )
                db.add(run)
                db.flush()
                run_created = True
                logger.info(
                    "Created SyncRun id=%d for sync %d target %s",
                    run.id,
                    self.ctx.sync_id,
                    self.ctx.target_id,
                )

            from src.app.models import PlaylistTrack

            track_rows = (
                db.execute(
                    select(PlaylistTrack)
                    .where(PlaylistTrack.sync_id == self.ctx.sync_id)
                    .order_by(PlaylistTrack.position)
                )
                .scalars()
                .all()
            )

            if track_rows and run_created:
                run_track_rows = [
                    {
                        "run_id": run.id,
                        "position": row.position,
                        "source_title": row.source_title,
                        "source_artist": row.source_artist,
                        "source_album": row.source_album,
                        "source_duration_ms": row.source_duration_ms,
                        "item_id": row.item_id,
                    }
                    for row in track_rows
                ]
                db.execute(insert(SyncRunTrack), run_track_rows)
                logger.info(
                    "Recorded %d SyncRunTrack rows for run %d",
                    len(run_track_rows),
                    run.id,
                )
            elif track_rows:
                logger.info(
                    "Skipping SyncRunTrack rows for reused run %d (already recorded)",
                    run.id,
                )

            return run_created
