"""Shared track matching logic used by TrackMatcher and MatchPhase."""

import logging
from typing import Any

from src.app.core.models import TrackMetadata
from src.app.core.services.matcher import MatchEngine, get_active_rules_sync
from src.app.worker.context import MatchResult, SyncContext
from src.app.worker.session import run_async

logger = logging.getLogger(__name__)


def _match_single_track(
    ctx: SyncContext,
    db,
    repo,
    item_id: str,
    engine: MatchEngine | None,
    rules: list | None,
) -> MatchResult:
    """Match a single track and persist PlaylistTrackTarget on success.

    Shared by TrackMatcher.match() and MatchPhase._match_track().
    """
    db_row = repo.get_source_track(db, ctx.sync_id, item_id)
    if not db_row:
        return MatchResult(matched=False, message=f"Track not found (item={item_id})")

    track = repo.build_track_metadata(db_row)

    match = _match_with_rules(ctx, track, engine, rules)

    if not match:
        logger.info(
            "No match for '%s' (sync %d, target %s)",
            db_row.source_title,
            ctx.sync_id,
            ctx.target_id,
        )
        return MatchResult(matched=False, message=f"No match for '{db_row.source_title}'")

    repo.upsert_match(db, db_row.id, ctx.target_id, match)

    match_item_id = match.get("item_id")
    duration = match.get("duration") or (
        match.get("duration_ms", 0) // 1000 if match.get("duration_ms") else None
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


def _match_with_rules(
    ctx: SyncContext,
    track: TrackMetadata,
    engine: MatchEngine | None,
    rules: list | None,
) -> dict[str, Any] | None:
    """Try MatchEngine with active rules."""
    if engine is None:
        return None
    try:
        matches = run_async(engine.run(track, rules=rules))
        if matches:
            return matches[0]
    except Exception as e:
        logger.warning(
            "MatchEngine failed for track '%s': %s",
            track.title,
            e,
            exc_info=True,
        )
    return None
