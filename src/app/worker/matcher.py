"""TrackMatcher — matches a single source track against a target library.

Uses SyncContext for DB access and target resolution. Persists
PlaylistTrackTarget on success.
"""

import logging
from typing import Any

from sqlalchemy import select
from sqlalchemy.dialects.postgresql import insert

from src.app.core.models import TrackMetadata
from src.app.core.services.matcher import MatchEngine, get_active_rules_sync
from src.app.models import PlaylistTrack, PlaylistTrackTarget
from src.app.services.audit import log_event_sync
from src.app.worker.context import MatchResult, SyncContext

logger = logging.getLogger(__name__)


class TrackMatcher:
    """Matches a single source track against a target library and persists the result."""

    def __init__(self, ctx: SyncContext) -> None:
        self.ctx = ctx

    def match(self, item_id: str) -> MatchResult:
        """Match a single track by source item_id. Saves PlaylistTrackTarget row."""
        with self.ctx.session() as db:
            stmt = select(PlaylistTrack).where(
                PlaylistTrack.sync_id == self.ctx.sync_id,
                PlaylistTrack.item_id == item_id,
            )
            db_row = db.execute(stmt).scalars().first()
            if not db_row:
                return MatchResult(
                    matched=False,
                    message=f"Track not found (sync={self.ctx.sync_id}, item={item_id})",
                )

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

            match = self._match_with_rules(track)

            if not match:
                return MatchResult(
                    matched=False,
                    message=f"No match found for '{db_row.source_title}'",
                )

            match_item_id = match.get("item_id")
            duration = match.get("duration") or (
                match.get("duration_ms", 0) // 1000 if match.get("duration_ms") else None
            )

            insert_stmt = (
                insert(PlaylistTrackTarget)
                .values(
                    playlist_track_id=db_row.id,
                    target_id=self.ctx.target_id,
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

            log_event_sync(
                event_type="track.matched",
                resource_type="track",
                resource_id=match_item_id,
                summary=(
                    f"Track '{db_row.source_title}' by {db_row.source_artist or '?'}"
                    f" matched to '{match.get('title', '')}'"
                    f" in sync {self.ctx.sync_id}"
                ),
            )

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

    def _match_with_rules(self, track: TrackMetadata) -> dict[str, Any] | None:
        """Try MatchEngine with active rules."""
        from src.app.worker.session import run_async

        try:
            rules = get_active_rules_sync()
            if rules:
                engine = MatchEngine(self.ctx.target)
                matches = run_async(engine.run(track, rules=rules))
                if matches:
                    return matches[0]
        except Exception:
            logger.warning("MatchEngine failed for track '%s'", track.title)
        return None
