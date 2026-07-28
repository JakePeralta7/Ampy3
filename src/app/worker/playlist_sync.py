"""PlaylistSync — manages target playlist creation and updates.

Replaces the old PlaylistManager with clean SyncContext integration.
"""

import logging
from typing import Any

from sqlalchemy import select
from sqlalchemy.dialects.postgresql import insert

from src.app.models import ScheduleTarget
from src.app.worker.context import SyncContext
from src.app.worker.session import run_async, session_scope

logger = logging.getLogger(__name__)


class PlaylistSync:
    """Manages target playlist CRUD on the target platform."""

    def __init__(self, ctx: SyncContext) -> None:
        self.ctx = ctx

    def get_existing_playlist_id(self, sync_id: int) -> str | None:
        """Read the persisted playlist_id from the junction table."""
        with session_scope() as db:
            stmt = select(ScheduleTarget).where(
                ScheduleTarget.sync_id == sync_id,
                ScheduleTarget.target_id == self.ctx.target_id,
            )
            row = db.execute(stmt).scalars().first()
            return row.playlist_id if row else None

    def save_playlist_id(self, sync_id: int, playlist_id: str) -> None:
        """Atomic upsert of the playlist_id."""
        with session_scope() as db:
            insert_stmt = (
                insert(ScheduleTarget)
                .values(
                    sync_id=sync_id,
                    target_id=self.ctx.target_id,
                    playlist_id=playlist_id,
                )
                .on_conflict_do_update(
                    constraint="uq_schedule_target",
                    set_={"playlist_id": playlist_id},
                )
            )
            db.execute(insert_stmt)

        logger.debug(
            "Saved playlist_id=%s for sync_id=%d, target_id=%s",
            playlist_id,
            sync_id,
            self.ctx.target_id,
        )

    async def sync(
        self,
        sync_id: int,
        title: str,
        matched_item_ids: list[str],
        source_url: str,
    ) -> str | None:
        """Create or update the target playlist. Returns the playlist ID."""
        if not matched_item_ids:
            logger.info("No matched items for %s, skipping playlist sync", self.ctx.target_id)
            return None

        existing_playlist_id = self.get_existing_playlist_id(sync_id)
        target = self.ctx.target

        logger.info(
            "sync_playlist: target=%s, existing_id=%s, matched_items=%d",
            self.ctx.target_id,
            existing_playlist_id,
            len(matched_item_ids),
        )

        if existing_playlist_id:
            try:
                existing = await target.get_playlist_details(existing_playlist_id)
                if existing:
                    current_items = await target.get_items_in_playlist(existing_playlist_id)
                    current_ids = sorted(i["item_id"] for i in current_items if i.get("item_id"))
                    desired_ids = sorted(matched_item_ids)
                    if current_ids == desired_ids:
                        logger.info(
                            "Playlist %s already up to date (%d items), skipping",
                            existing_playlist_id,
                            len(desired_ids),
                        )
                        return existing_playlist_id
                    items = [{"item_id": iid} for iid in matched_item_ids]
                    await target.update_playlist(existing_playlist_id, items)
                    logger.info(
                        "Updated existing playlist %s for target %s (%d → %d items)",
                        existing_playlist_id,
                        self.ctx.target_id,
                        len(current_ids),
                        len(desired_ids),
                    )
                    return existing_playlist_id
                logger.warning(
                    "Playlist %s not found on target, creating new",
                    existing_playlist_id,
                )
            except Exception as e:
                logger.warning(
                    "Exception checking playlist %s: %s — creating new",
                    existing_playlist_id,
                    e,
                )

        items = [{"item_id": iid} for iid in matched_item_ids]
        playlist_id = await target.create_playlist(
            title=title,
            items=items,
            custom_metadata={"source_url": source_url, "sync_id": sync_id},
        )

        if playlist_id:
            self.save_playlist_id(sync_id, playlist_id)
            logger.info(
                "Created new playlist %s for target %s",
                playlist_id,
                self.ctx.target_id,
            )

        return playlist_id
