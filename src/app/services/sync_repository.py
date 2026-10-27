"""SyncRepository — data access layer for sync operations.

Centralizes all database operations related to ScheduledPlaylistSync, SyncRun,
PlaylistTrack, PlaylistTrackTarget, and SyncRunTrackTarget.
"""

import logging
from datetime import UTC, datetime
from typing import Any

from sqlalchemy import delete, select, text
from sqlalchemy.dialects.postgresql import insert as pg_insert
from sqlalchemy.orm import selectinload

from src.app.constants import AD_HOC_INTERVAL, INTERVAL_DELTAS
from src.app.core.models import TrackMetadata
from src.app.models import (
    MatchRule,
    PlaylistTrack,
    PlaylistTrackTarget,
    ScheduledPlaylistSync,
    SyncRun,
    SyncRunTrack,
    SyncRunTrackTarget,
)
from src.app.worker.context import MatchResult, SyncContext
from src.app.worker.errors import SyncScheduleMissingError
from src.app.worker.session import session_scope

logger = logging.getLogger(__name__)


class SyncRepository:
    """Data access layer for sync operations.

    Provides a single source of truth for all sync-related DB operations,
    eliminating duplication between pipeline phases and manual match tasks.
    """

    def __init__(self) -> None:
        pass

    # ─── Sync Record Management ──────────────────────────────────

    def get_or_create_sync(
        self,
        *,
        schedule_id: int | None = None,
        sync_id: int | None = None,
        source: str,
        source_url: str,
        playlist_title: str,
        execution_id: str | None = None,
        user_id: str | None = None,
    ) -> ScheduledPlaylistSync:
        """Get existing sync or create new one.

        Args:
            schedule_id: If provided, updates existing schedule with execution_id
            sync_id: If provided, uses pre-created ad-hoc sync record
            source: Source platform ID (youtube_music, deezer)
            source_url: Source playlist URL
            playlist_title: Target playlist name
            execution_id: Idempotency key
            user_id: Owner user ID

        Returns:
            The ScheduledPlaylistSync record
        """
        with session_scope() as db:
            return self._get_or_create_sync(
                db,
                schedule_id=schedule_id,
                sync_id=sync_id,
                source=source,
                source_url=source_url,
                playlist_title=playlist_title,
                execution_id=execution_id,
                user_id=user_id,
            )

    def _get_or_create_sync(
        self,
        db,
        *,
        schedule_id: int | None,
        sync_id: int | None,
        source: str,
        source_url: str,
        playlist_title: str,
        execution_id: str | None,
        user_id: str | None,
    ) -> ScheduledPlaylistSync:
        """Internal implementation with existing DB session."""
        if sync_id is not None:
            # Idempotency: use pre-created sync record (created in API handler)
            sync_record = db.get(ScheduledPlaylistSync, sync_id)
            if not sync_record:
                raise SyncScheduleMissingError(sync_id)
        elif schedule_id is not None:
            sync_record = (
                db.execute(
                    select(ScheduledPlaylistSync).where(ScheduledPlaylistSync.id == schedule_id)
                )
                .scalars()
                .first()
            )
            if not sync_record:
                raise SyncScheduleMissingError(schedule_id)
        else:
            # Manual (ad-hoc) runs without pre-created sync record
            sync_record = ScheduledPlaylistSync(
                source=source,
                source_url=source_url,
                target_playlist_name=playlist_title,
                schedule_interval=AD_HOC_INTERVAL,
                is_active=False,
                next_sync_at=datetime.now(UTC),
                execution_id=execution_id,
                user_id=user_id,
            )
            db.add(sync_record)
            db.flush()

        return sync_record

    # ─── Track Persistence ───────────────────────────────────────

    def upsert_source_tracks(
        self,
        db,
        sync_id: int,
        track_rows: list[dict[str, Any]],
        target_ids: list[str],
    ) -> dict[int, int]:
        """Upsert source tracks and clear old target mappings.

        Args:
            db: Active DB session
            sync_id: Sync record ID
            track_rows: List of track dicts with position, title, artist, etc.
            target_ids: Target platform IDs to clear old mappings for

        Returns:
            Dict mapping position -> track ID
        """
        existing_tracks: dict[int, PlaylistTrack] = {}
        if track_rows:
            existing_stmt = select(PlaylistTrack).where(PlaylistTrack.sync_id == sync_id)
            for row in db.execute(existing_stmt).scalars().all():
                existing_tracks[row.position] = row

        inserted_track_ids: dict[int, int] = {}
        for row_data in track_rows:
            position = row_data.get("position", 0)
            if position in existing_tracks:
                track = existing_tracks[position]
                track.source_title = row_data.get("source_title")
                track.source_artist = row_data.get("source_artist")
                track.source_album = row_data.get("source_album")
                track.source_duration_ms = row_data.get("source_duration_ms")
                track.item_id = row_data.get("item_id")
                track.source_mbid = row_data.get("source_mbid")
                track.source_artist_mbid = row_data.get("source_artist_mbid")
                track.source_album_mbid = row_data.get("source_album_mbid")
                inserted_track_ids[position] = track.id
            else:
                new_track = PlaylistTrack(
                    sync_id=sync_id,
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

        if track_rows:
            max_new_position = max(row_data.get("position", 0) for row_data in track_rows)
            pruned_count = 0
            for pos, track in existing_tracks.items():
                if pos > max_new_position:
                    if track.targets:
                        logger.warning(
                            "Pruning track at position %d (sync %d) that has %d target match(es). "
                            "Consider soft-delete to preserve history.",
                            pos,
                            sync_id,
                            len(track.targets),
                        )
                    db.delete(track)
                    pruned_count += 1
            if pruned_count:
                logger.info(
                    "Pruned %d track(s) from sync %d (no longer in source playlist)",
                    pruned_count,
                    sync_id,
                )

        if inserted_track_ids:
            track_id_list = list(inserted_track_ids.values())
            db.execute(
                delete(PlaylistTrackTarget).where(
                    PlaylistTrackTarget.playlist_track_id.in_(track_id_list),
                    PlaylistTrackTarget.target_id.in_(target_ids),
                )
            )

        return inserted_track_ids

    def get_source_track(self, db, sync_id: int, item_id: str) -> PlaylistTrack | None:
        """Get a source track by sync_id and item_id."""
        stmt = select(PlaylistTrack).where(
            PlaylistTrack.sync_id == sync_id,
            PlaylistTrack.item_id == item_id,
        )
        return db.execute(stmt).scalars().first()

    def get_source_tracks_for_sync(self, db, sync_id: int) -> list[PlaylistTrack]:
        """Get all source tracks for a sync with target relationships loaded."""
        stmt = (
            select(PlaylistTrack)
            .where(PlaylistTrack.sync_id == sync_id)
            .options(selectinload(PlaylistTrack.targets))
        )
        return db.execute(stmt).scalars().unique().all()

    # ─── Match Persistence ───────────────────────────────────────

    def upsert_match(
        self,
        db,
        playlist_track_id: int,
        target_id: str,
        match: dict[str, Any],
    ) -> None:
        """Upsert a PlaylistTrackTarget row for a matched track.

        Args:
            db: Active DB session
            playlist_track_id: ID of the PlaylistTrack
            target_id: Target platform ID
            match: Match dict with item_id, title, artist_name, album_name, duration, _rule_id
        """
        match_item_id = match.get("item_id")
        duration = match.get("duration") or (
            match.get("duration_ms", 0) // 1000 if match.get("duration_ms") else None
        )

        insert_stmt = (
            pg_insert(PlaylistTrackTarget)
            .values(
                playlist_track_id=playlist_track_id,
                target_id=target_id,
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

    def build_track_metadata(self, db_row: PlaylistTrack) -> TrackMetadata:
        """Build TrackMetadata from a PlaylistTrack DB row."""
        return TrackMetadata(
            title=db_row.source_title,
            artist_name=db_row.source_artist,
            album_name=db_row.source_album,
            duration_ms=db_row.source_duration_ms,
            source_id=db_row.item_id,
            mbid=db_row.source_mbid,
            artist_mbid=db_row.source_artist_mbid,
            album_mbid=db_row.source_album_mbid,
        )

    # ─── SyncRun Management ──────────────────────────────────────

    def get_latest_sync_run(self, db, sync_id: int, target_id: str) -> SyncRun | None:
        """Get the latest SyncRun for a sync/target."""
        stmt = (
            select(SyncRun)
            .where(SyncRun.sync_id == sync_id, SyncRun.target_id == target_id)
            .order_by(SyncRun.created_at.desc())
            .limit(1)
        )
        return db.execute(stmt).scalars().first()

    def finalize_sync_run(
        self, db, sync_id: int, target_id: str, matched: int, failed: int
    ) -> None:
        """Update SyncRun with match counts and mark completed."""
        run = self.get_latest_sync_run(db, sync_id, target_id)
        if run:
            run.matched_count = matched
            run.failed_count = failed
            run.status = "completed"

    # ─── History Snapshot ────────────────────────────────────────

    def snapshot_history(self, db, sync_id: int, target_id: str) -> None:
        """Populate SyncRunTrackTarget rows for the diff endpoint.

        This enables the diff endpoint to determine match status changes
        between runs.
        """
        run = self.get_latest_sync_run(db, sync_id, target_id)
        if not run:
            return

        run_tracks_stmt = select(SyncRunTrack).where(SyncRunTrack.run_id == run.id)
        run_tracks = db.execute(run_tracks_stmt).scalars().all()
        run_tracks_by_item = {rt.item_id: rt for rt in run_tracks if rt.item_id}

        playlist_tracks = self.get_source_tracks_for_sync(db, sync_id)

        new_targets = []
        for pt in playlist_tracks:
            for t in pt.targets:
                if t.target_id == target_id and t.item_id:
                    rt = run_tracks_by_item.get(pt.item_id)
                    if rt:
                        new_targets.append(
                            SyncRunTrackTarget(
                                sync_run_track_id=rt.id,
                                target_id=target_id,
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

    # ─── Stats & Schedule Updates ────────────────────────────────

    def update_schedule_stats(self, db, sync_id: int) -> None:
        """Update ScheduledPlaylistSync stats from latest SyncRun per target.

        Uses an advisory lock to prevent race conditions when multiple
        targets finalize concurrently.
        """
        db.execute(
            text("SELECT pg_advisory_xact_lock(:k)"),
            {"k": hash(sync_id) & 0x7FFFFFFFFFFFFFFF},
        )

        stmt = select(ScheduledPlaylistSync).where(ScheduledPlaylistSync.id == sync_id)
        sync_record = db.execute(stmt).scalars().first()
        if not sync_record:
            return

        runs = db.execute(select(SyncRun).where(SyncRun.sync_id == sync_id)).scalars().all()
        latest_by_target: dict[str, SyncRun] = {}
        for run in runs:
            prev = latest_by_target.get(run.target_id)
            if prev is None or (run.created_at, run.id) > (prev.created_at, prev.id):
                latest_by_target[run.target_id] = run

        sync_record.matched_count = sum(r.matched_count or 0 for r in latest_by_target.values())
        sync_record.failed_count = sum(r.failed_count or 0 for r in latest_by_target.values())
        sync_record.last_synced_at = datetime.now(UTC)
        sync_record.error_message = None

        if sync_record.schedule_interval:
            delta = INTERVAL_DELTAS.get(sync_record.schedule_interval)
            if delta:
                sync_record.next_sync_at = sync_record.last_synced_at + delta

        db.flush()

    # ─── Target Playlist Sync ────────────────────────────────────

    def get_matched_item_ids(self, db, sync_id: int, target_id: str) -> list[str]:
        """Collect matched item_ids from PlaylistTrackTarget for a target."""
        tracks = self.get_source_tracks_for_sync(db, sync_id)

        matched_ids = []
        for track in tracks:
            for t in track.targets:
                if t.target_id == target_id and t.item_id:
                    matched_ids.append(t.item_id)
                    break
        return matched_ids

    def get_existing_playlist_id(self, ctx: SyncContext) -> str | None:
        """Get the existing playlist_id for this target from the junction table."""
        from src.app.worker.playlist_sync import PlaylistSync

        return PlaylistSync(ctx).get_existing_playlist_id(ctx.sync_id)

    def sync_target_playlist(
        self,
        ctx: SyncContext,
        matched_item_ids: list[str],
    ) -> None:
        """Sync the playlist on the target platform."""
        if not matched_item_ids:
            logger.info("No matched items for %s, skipping playlist sync", ctx.target_id)
            return

        from src.app.worker.playlist_sync import PlaylistSync

        playlist_sync = PlaylistSync(ctx)
        from src.app.worker.session import run_async

        run_async(
            playlist_sync.sync(ctx.sync_id, ctx.playlist_title, matched_item_ids, ctx.source_url)
        )


# Module-level singleton for convenience
_sync_repository: SyncRepository | None = None


def get_sync_repository() -> SyncRepository:
    """Get the global SyncRepository instance."""
    global _sync_repository
    if _sync_repository is None:
        _sync_repository = SyncRepository()
    return _sync_repository


def reset_sync_repository() -> None:
    """Reset the SyncRepository instance (for testing)."""
    global _sync_repository
    _sync_repository = None
