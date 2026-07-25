from __future__ import annotations

import asyncio
import logging
from typing import TYPE_CHECKING

from src.app.core.models import PlaylistMetadata, TrackMetadata
from src.app.core.services.matcher import MatchEngine, get_active_rules
from src.app.models import MatchRule

if TYPE_CHECKING:
    from src.app.core.targets.base import BaseTarget

logger = logging.getLogger(__name__)


class SyncOrchestrator:
    def __init__(self, target: BaseTarget):
        self._target = target
        self._match_engine = MatchEngine(target)

    async def sync_playlist(
        self,
        playlist: PlaylistMetadata,
        replace_existing: bool = False,
        rules: list[MatchRule] | None = None,
        target_playlist_name: str | None = None,
    ) -> dict:
        if rules is None:
            rules = await get_active_rules()
        if not rules:
            logger.warning("No active match rules configured — all tracks will fail to match")
        else:
            logger.debug("Loaded %d active match rule(s) for this sync run", len(rules))

        playlist_name = target_playlist_name or playlist.title

        stats = {
            "playlist": playlist_name,
            "source_id": playlist.source_id,
            "target_playlist_id": None,
            "total_tracks": len(playlist.tracks),
            "matched": 0,
            "failed": 0,
            "added": 0,
            "updated": 0,
            "errors": [],
            "matched_tracks": [],
            "failed_tracks": [],
        }

        existing = await self._target.get_playlist_by_name(playlist_name)

        def _playlist_id(data: dict | None) -> str | None:
            if not data:
                return None
            for key in ("rating_key", "playlist_id", "id"):
                value = data.get(key)
                if isinstance(value, str) and value:
                    return value
            return None

        if existing and replace_existing:
            try:
                existing_id = _playlist_id(existing)
                if not existing_id:
                    raise RuntimeError("Existing playlist missing identifier")
                await self._target.delete_playlist(existing_id)
                logger.debug("Deleted existing playlist '%s' for replacement", playlist_name)
                existing = None
            except Exception as e:
                stats["errors"].append(f"Failed to delete existing: {e}")

        # Resolve all tracks in parallel with bounded concurrency
        semaphore = asyncio.Semaphore(10)

        async def _resolve_one(
            position: int,
            track: TrackMetadata,
        ) -> tuple[int, TrackMetadata, dict | None]:
            async with semaphore:
                result = await self._resolve_track(track, rules)
                return position, track, result

        tasks = [_resolve_one(pos, t) for pos, t in enumerate(playlist.tracks)]
        resolved = await asyncio.gather(*tasks)

        # Build results in original order
        matched_results = []
        track_rows = []
        for position, track, result in sorted(resolved, key=lambda x: x[0]):
            row = {
                "position": position,
                "source_title": track.title,
                "source_artist": track.artist_name,
                "source_album": track.album_name,
                "source_duration_ms": track.duration_ms,
                "source_id": track.source_id,
            }
            if result and result.get("found", False):
                hit = result["match"]
                row["match_item_id"] = hit.get("plex_id")
                row["match_title"] = hit.get("title")
                row["match_artist"] = hit.get("artist_name")
                row["match_album"] = hit.get("album_name")
                dur_ms = hit.get("duration_ms", 0)
                dur_s = dur_ms // 1000 if dur_ms else None
                row["match_duration"] = hit.get("duration") or dur_s
                row["match_rule_id"] = result.get("rule_id")
                matched_results.append(result)
                stats["matched"] += 1
                stats["matched_tracks"].append(
                    {
                        "title": track.title,
                        "artist": track.artist_name,
                    }
                )
            else:
                stats["failed"] += 1
                stats["failed_tracks"].append(
                    {
                        "title": track.title or "unknown",
                        "artist": track.artist_name,
                    }
                )
                error_msg = f"No match for track: {track.title or 'unknown'}"
                stats["errors"].append(error_msg)
            track_rows.append(row)

        stats["track_rows"] = track_rows

        if matched_results:
            try:
                if existing and not replace_existing:
                    existing_id = _playlist_id(existing)
                    if not existing_id:
                        raise RuntimeError("Existing playlist missing identifier")
                    success = await self._target.update_playlist(
                        existing_id,
                        [t["match"] for t in matched_results],
                    )
                    if success:
                        stats["target_playlist_id"] = existing_id
                        stats["updated"] = len(matched_results)
                else:
                    playlist_id = await self._target.create_playlist(
                        title=playlist_name,
                        items=[t["match"] for t in matched_results],
                        custom_metadata={"source_playlist_id": playlist.source_id},
                    )
                    if playlist_id:
                        stats["target_playlist_id"] = playlist_id
                        stats["added"] = len(matched_results)
            except Exception as e:
                stats["errors"].append(f"Failed to create/update playlist: {e}")

        return stats

    async def _resolve_track(
        self,
        track: TrackMetadata,
        rules: list[MatchRule] | None = None,
    ) -> dict | None:
        if not track.is_matchable:
            logger.warning(
                "Track missing required metadata for matching: title=%s artist=%s",
                track.title,
                track.artist_name,
            )
            return None

        if not rules:
            return None

        try:
            matches = await self._match_engine.run(track, rules=rules)
            if matches:
                m = matches[0]
                logger.debug(
                    "Matched '%s' by '%s' via rule '%s' (id=%d)",
                    track.title,
                    track.artist_name,
                    m.get("_rule_name", "?"),
                    m.get("_rule_id", -1),
                )
                return {
                    "found": True,
                    "type": "match_engine",
                    "match": m,
                    "rule_id": m.get("_rule_id"),
                }

            logger.debug("No match found for '%s' by '%s'", track.title, track.artist_name)
            return None
        except Exception as e:
            logger.error(
                "MatchEngine failed for '%s' by '%s': %s",
                track.title,
                track.artist_name,
                e,
            )
            return None
