"""Pipeline phases — abstract base class and concrete implementations.

Each phase encapsulates one stage of the sync pipeline. Phases are composable:
SyncPipeline chains them together, and new phases can be added by subclassing
SyncPhase without modifying the pipeline.
"""

from __future__ import annotations

import logging
from abc import ABC, abstractmethod
from dataclasses import dataclass, field
from datetime import UTC, datetime
from typing import Any

from sqlalchemy import delete, select
from sqlalchemy.orm import selectinload

from src.app.constants import INTERVAL_DELTAS
from src.app.core.models import TrackMetadata
from src.app.core.services.matcher import MatchEngine, get_active_rules_sync
from src.app.core.sources.registry import SourceRegistry
from src.app.models import (
    PlaylistTrack,
    PlaylistTrackTarget,
    ScheduledPlaylistSync,
    SyncRun,
    SyncRunTrack,
    SyncRunTrackTarget,
)
from src.app.worker.context import MatchResult, SyncContext
from src.app.worker.session import run_async, session_scope

logger = logging.getLogger(__name__)


# ─── Phase ABC ─────────────────────────────────────────────────


@dataclass
class PhaseResult:
    """Result returned by a pipeline phase."""

    success: bool = True
    data: dict[str, Any] = field(default_factory=dict)
    error: str | None = None


class SyncPhase(ABC):
    """Abstract pipeline phase.

    Each phase receives a SyncContext and input data dict, performs its work,
    and returns a PhaseResult with data for downstream phases.
    """

    @abstractmethod
    def execute(self, ctx: SyncContext, input_data: dict[str, Any]) -> PhaseResult: ...


# ─── Phase 1: Fetch Source ────────────────────────────────────


class FetchPhase(SyncPhase):
    """Phase 1: Fetch source playlist and persist tracks to DB.

    Runs once per sync invocation, shared across all targets.
    The ``input_data`` must contain: ``source_url``, ``source``,
    ``schedule_id`` (optional), ``target_ids``.
    """

    def execute(self, ctx: SyncContext, input_data: dict[str, Any]) -> PhaseResult:
        source_url: str = input_data["source_url"]
        source_id: str = input_data["source"]
        schedule_id: int | None = input_data.get("schedule_id")
        target_ids: list[str] = input_data.get("target_ids", [ctx.target_id])

        source_cls = SourceRegistry.get(source_id)
        source_adapter = source_cls()
        playlist = run_async(source_adapter.get_playlist(source_url))

        playlist_title = ctx.playlist_title or playlist.title
        track_rows = [
            {
                "position": pos,
                "source_title": t.title,
                "source_artist": t.artist_name,
                "source_album": t.album_name,
                "source_duration_ms": t.duration_ms,
                "item_id": t.source_id,
                "source_mbid": t.mbid,
                "source_artist_mbid": t.artist_mbid,
                "source_album_mbid": t.album_mbid,
            }
            for pos, t in enumerate(playlist.tracks)
        ]
        track_items = [r["item_id"] for r in track_rows if r["item_id"]]

        with session_scope() as db:
            sync_id = self._save_source_tracks(
                db,
                schedule_id,
                source_url,
                source_id,
                playlist_title,
                track_rows,
                target_ids,
            )

        return PhaseResult(
            data={
                "sync_id": sync_id,
                "track_rows": track_rows,
                "track_items": track_items,
                "playlist_title": playlist_title,
            }
        )

    def _save_source_tracks(  # noqa: PLR0913
        self,
        db,  # noqa: ANN001
        schedule_id: int | None,
        playlist_url: str,
        source: str,
        playlist_title: str,
        track_rows: list[dict[str, Any]],
        target_ids: list[str],
    ) -> int:
        """Save source tracks to DB and return the sync record ID."""
        if schedule_id:
            stmt = select(ScheduledPlaylistSync).where(ScheduledPlaylistSync.id == schedule_id)
        else:
            stmt = select(ScheduledPlaylistSync).where(
                ScheduledPlaylistSync.source_url == playlist_url,
            )

        sync_record = db.execute(stmt).scalars().first()

        if not sync_record:
            sync_record = ScheduledPlaylistSync(
                source=source,
                source_url=playlist_url,
                target_playlist_name=playlist_title,
                schedule_interval="once",
                is_active=False,
                next_sync_at=datetime.now(UTC),
            )
            db.add(sync_record)
            db.flush()

        existing_tracks: dict[int, int] = {}
        if track_rows:
            existing_stmt = select(PlaylistTrack).where(PlaylistTrack.sync_id == sync_record.id)
            for row in db.execute(existing_stmt).scalars().all():
                existing_tracks[row.position] = row.id

        inserted_track_ids: dict[int, int] = {}
        for row_data in track_rows:
            position = row_data.get("position", 0)
            if position in existing_tracks:
                inserted_track_ids[position] = existing_tracks[position]
            else:
                new_track = PlaylistTrack(
                    sync_id=sync_record.id,
                    position=position,
                    source_title=row_data.get("source_title"),
                    source_artist=row_data.get("source_artist"),
                    source_album=row_data.get("source_album"),
                    source_duration_ms=row_data.get("source_duration_ms"),
                    item_id=row_data.get("item_id"),
                    source_mbid=row_data.get("source_mbid"),
                    source_artist_mbid=row_data.get("source_artist_mbid"),
                    source_album_mbid=row_data.get("source_album_mbid"),
                )
                db.add(new_track)
                db.flush()
                inserted_track_ids[position] = new_track.id

        if inserted_track_ids:
            track_id_list = list(inserted_track_ids.values())
            db.execute(
                delete(PlaylistTrackTarget).where(
                    PlaylistTrackTarget.playlist_track_id.in_(track_id_list),
                    PlaylistTrackTarget.target_id.in_(target_ids),
                )
            )

        return sync_record.id  # type: ignore[return-value]


# ─── Phase 2: Match Tracks ────────────────────────────────────


class MatchPhase(SyncPhase):
    """Phase 2: Match all source tracks against the target library.

    The ``input_data`` must contain: ``track_items`` (list of source item IDs).
    """

    def execute(self, ctx: SyncContext, input_data: dict[str, Any]) -> PhaseResult:
        track_items: list[str] = input_data["track_items"]
        matched = 0
        failed = 0

        with ctx.session() as db:
            for item_id in track_items:
                result = self._match_track(db, ctx, item_id)
                if result.matched:
                    matched += 1
                else:
                    failed += 1

        return PhaseResult(data={"matched": matched, "failed": failed})

    def _match_track(self, db, ctx: SyncContext, item_id: str) -> MatchResult:  # noqa: ANN001
        """Match a single track and persist PlaylistTrackTarget on success."""
        stmt = select(PlaylistTrack).where(
            PlaylistTrack.sync_id == ctx.sync_id,
            PlaylistTrack.item_id == item_id,
        )
        db_row = db.execute(stmt).scalars().first()
        if not db_row:
            return MatchResult(matched=False, message=f"Track not found (item={item_id})")

        track = TrackMetadata(
            title=db_row.source_title,
            artist_name=db_row.source_artist,
            album_name=db_row.source_album,
            duration_ms=db_row.source_duration_ms,
            source_id=db_row.item_id,
            mbid=db_row.source_mbid,
            artist_mbid=db_row.source_artist_mbid,
            album_mbid=db_row.source_album_mbid,
        )

        match = self._match_with_rules(ctx, track)

        if not match:
            return MatchResult(matched=False, message=f"No match for '{db_row.source_title}'")

        match_item_id = match.get("item_id")
        duration = match.get("duration") or (
            match.get("duration_ms", 0) // 1000 if match.get("duration_ms") else None
        )

        from sqlalchemy.dialects.postgresql import insert as pg_insert

        insert_stmt = (
            pg_insert(PlaylistTrackTarget)
            .values(
                playlist_track_id=db_row.id,
                target_id=ctx.target_id,
                item_id=match_item_id,
                title=match.get("title"),
                artist_name=match.get("artist_name"),
                album_name=match.get("album_name"),
                duration=duration,
                rule_id=match.get("_rule_id"),
            )
            .on_conflict_do_update(
                constraint="uq_playlist_track_target",
                set_={
                    "item_id": match_item_id,
                    "title": match.get("title"),
                    "artist_name": match.get("artist_name"),
                    "album_name": match.get("album_name"),
                    "duration": duration,
                    "rule_id": match.get("_rule_id"),
                },
            )
        )
        db.execute(insert_stmt)
        db.flush()

        return MatchResult(
            matched=True,
            message=f"Matched '{db_row.source_title}' to '{match.get('title', '')}'",
            item_id=match_item_id,
            title=match.get("title"),
            artist_name=match.get("artist_name"),
            album_name=match.get("album_name"),
            duration=duration,
            rule_id=match.get("_rule_id"),
        )

    def _match_with_rules(self, ctx: SyncContext, track: TrackMetadata) -> dict[str, Any] | None:
        """Try MatchEngine with active rules."""
        try:
            rules = get_active_rules_sync()
            if rules:
                engine = MatchEngine(ctx.target)
                matches = run_async(engine.run(track, rules=rules))
                if matches:
                    return matches[0]
        except Exception:
            logger.warning("MatchEngine failed for track '%s'", track.title)
        return None


# ─── Phase 3: Finalize ────────────────────────────────────────


class FinalizePhase(SyncPhase):
    """Phase 3: Finalize — count results, sync target playlist,
    snapshot history (SyncRunTrackTarget), update stats.

    The ``input_data`` must contain: ``matched``, ``failed``.
    """

    def execute(self, ctx: SyncContext, input_data: dict[str, Any]) -> PhaseResult:
        matched_count: int = input_data["matched"]
        failed_count: int = input_data["failed"]

        with ctx.session() as db:
            self._finalize_counts(db, ctx, matched_count, failed_count)
            self._snapshot_history(db, ctx)
            self._update_stats(db, ctx, matched_count, failed_count)
            matched_item_ids = self._collect_matched_ids(db, ctx)

        self._sync_target_playlist(ctx, matched_item_ids)

        existing_playlist_id = self._get_playlist_id(ctx)

        return PhaseResult(
            data={
                "matched": matched_count,
                "failed": failed_count,
                "target_playlist_id": existing_playlist_id,
            }
        )

    def _finalize_counts(self, db, ctx: SyncContext, matched: int, failed: int) -> None:  # noqa: ANN001
        """Update SyncRun with match counts and mark it completed."""
        stmt = (
            select(SyncRun)
            .where(SyncRun.sync_id == ctx.sync_id, SyncRun.target_id == ctx.target_id)
            .order_by(SyncRun.created_at.desc())
            .limit(1)
        )
        run = db.execute(stmt).scalars().first()
        if run:
            run.matched_count = matched
            run.failed_count = failed
            run.status = "completed"

    def _snapshot_history(self, db, ctx: SyncContext) -> None:  # noqa: ANN001
        """Populate SyncRunTrackTarget rows for the diff.

        This is the fix for the 'No changes since previous run' bug — without
        these rows, the diff endpoint cannot determine match status.
        """
        stmt = (
            select(SyncRun)
            .where(SyncRun.sync_id == ctx.sync_id, SyncRun.target_id == ctx.target_id)
            .order_by(SyncRun.created_at.desc())
            .limit(1)
        )
        run = db.execute(stmt).scalars().first()
        if not run:
            return

        run_tracks_stmt = select(SyncRunTrack).where(SyncRunTrack.run_id == run.id)
        run_tracks = db.execute(run_tracks_stmt).scalars().all()
        run_tracks_by_item = {rt.item_id: rt for rt in run_tracks if rt.item_id}

        playlist_tracks_stmt = (
            select(PlaylistTrack)
            .where(PlaylistTrack.sync_id == ctx.sync_id)
            .options(selectinload(PlaylistTrack.targets))
        )
        playlist_tracks = db.execute(playlist_tracks_stmt).scalars().unique().all()

        new_targets = []
        for pt in playlist_tracks:
            for t in pt.targets:
                if t.target_id == ctx.target_id and t.item_id:
                    rt = run_tracks_by_item.get(pt.item_id)
                    if rt:
                        new_targets.append(
                            SyncRunTrackTarget(
                                sync_run_track_id=rt.id,
                                target_id=ctx.target_id,
                                item_id=t.item_id,
                                title=t.title,
                                artist_name=t.artist_name,
                                album_name=t.album_name,
                                duration=t.duration,
                                rule_id=t.rule_id,
                            )
                        )

        if new_targets:
            db.add_all(new_targets)
            db.flush()

    def _update_stats(
        self,
        db,
        ctx: SyncContext,
        matched: int,
        failed: int,  # noqa: ANN001
    ) -> None:
        """Update ScheduledPlaylistSync stats and schedule next run."""
        stmt = select(ScheduledPlaylistSync).where(ScheduledPlaylistSync.id == ctx.sync_id)
        sync_record = db.execute(stmt).scalars().first()
        if not sync_record:
            return

        sync_record.matched_count = matched
        sync_record.failed_count = failed
        sync_record.last_synced_at = datetime.now(UTC)
        sync_record.error_message = None

        if sync_record.schedule_interval:
            delta = INTERVAL_DELTAS.get(sync_record.schedule_interval)
            if delta:
                sync_record.next_sync_at = sync_record.last_synced_at + delta

        db.flush()

    def _collect_matched_ids(self, db, ctx: SyncContext) -> list[str]:  # noqa: ANN001
        """Collect matched item_ids from PlaylistTrackTarget for this target."""
        stmt = select(PlaylistTrack).where(PlaylistTrack.sync_id == ctx.sync_id)
        tracks = db.execute(stmt).scalars().all()

        matched_ids = []
        for track in tracks:
            for t in track.targets:
                if t.target_id == ctx.target_id and t.item_id:
                    matched_ids.append(t.item_id)
                    break
        return matched_ids

    def _sync_target_playlist(self, ctx: SyncContext, matched_item_ids: list[str]) -> None:
        """Sync the playlist on the target platform."""
        if not matched_item_ids:
            logger.info("No matched items for %s, skipping playlist sync", ctx.target_id)
            return

        from src.app.worker.playlist_sync import PlaylistSync

        playlist_sync = PlaylistSync(ctx)
        run_async(
            playlist_sync.sync(ctx.sync_id, ctx.playlist_title, matched_item_ids, ctx.source_url)
        )

    def _get_playlist_id(self, ctx: SyncContext) -> str | None:
        """Get the existing playlist_id from the junction table."""
        from src.app.worker.playlist_sync import PlaylistSync

        playlist_sync = PlaylistSync(ctx)
        return playlist_sync.get_existing_playlist_id(ctx.sync_id)
