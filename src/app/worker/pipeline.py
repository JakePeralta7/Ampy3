"""SyncPipeline — composes SyncPhase instances into a full sync flow.

Two modes of operation:
1. ``fetch_source()`` — Phase 1 only (called once per sync invocation)
2. ``run_target()`` — Phases 2+3 (called once per target)
"""

from __future__ import annotations

import logging
from typing import Any

from sqlalchemy import insert, select

from src.app.models import SyncRun, SyncRunTrack
from src.app.worker.context import SyncContext
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
            raise RuntimeError(f"FetchPhase failed: {result.error}")
        return result.data

    def run_target(
        self,
        track_rows: list[dict[str, Any]],
        track_items: list[str],
    ) -> dict[str, Any]:
        """Run all target phases sequentially (ensure_sync_run → match → finalize)."""
        self._ensure_sync_run(track_rows)

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
                raise RuntimeError(f"Phase {phase.__class__.__name__} failed: {result.error}")
            input_data.update(result.data)

        return input_data

    def _ensure_sync_run(self, track_rows: list[dict[str, Any]]) -> None:
        """Create a new SyncRun with SyncRunTrack history for this target."""
        with self.ctx.session() as db:
            run = SyncRun(
                sync_id=self.ctx.sync_id,
                target_id=self.ctx.target_id,
                matched_count=0,
                failed_count=0,
            )
            db.add(run)
            db.flush()

            if track_rows:
                run_track_rows = [
                    {
                        "run_id": run.id,
                        "position": row_data.get("position", 0),
                        "source_title": row_data.get("source_title"),
                        "source_artist": row_data.get("source_artist"),
                        "source_album": row_data.get("source_album"),
                        "source_duration_ms": row_data.get("source_duration_ms"),
                        "item_id": row_data.get("item_id"),
                    }
                    for row_data in track_rows
                ]
                db.execute(insert(SyncRunTrack), run_track_rows)
