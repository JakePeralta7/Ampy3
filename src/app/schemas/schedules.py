"""Scheduled sync request/response schemas."""

from pydantic import BaseModel, Field

from src.app.constants import DEFAULT_TARGET


class CreateScheduledSyncInput(BaseModel):
    """Input schema for creating a scheduled sync."""

    source: str = Field(..., description="Source platform (e.g. youtube_music)")
    target_ids: list[str] = Field(
        default=[DEFAULT_TARGET],
        description="Target platforms (e.g. ['Plex', 'Jellyfin'])",
    )
    source_url: str = Field(..., description="URL of the source playlist")
    target_playlist_name: str = Field(..., description="Name for the playlist")
    schedule_interval: str = Field(..., description="Sync interval (e.g. daily, weekly, every_6h)")


class UpdateScheduledSyncInput(BaseModel):
    """Input schema for updating a scheduled sync."""

    target_ids: list[str] | None = None
    target_playlist_name: str | None = None
    schedule_interval: str | None = None
    is_active: bool | None = None


class ScheduledSyncOut(BaseModel):
    """Output schema for a scheduled sync."""

    id: int
    source: str
    target_ids: list[str]
    source_url: str
    target_playlist_name: str
    schedule_interval: str
    is_active: bool
    last_synced_at: str | None = None
    next_sync_at: str | None = None
    created_at: str | None = None
    updated_at: str | None = None
    error_message: str | None = None
    status: str | None = None


class SyncNowResponse(BaseModel):
    """Response after manually triggering a sync."""

    task_id: str
    message: str


class SchedulerReloadResponse(BaseModel):
    """Response after reloading the scheduler."""

    message: str


# ─── Bulk actions ────────────────────────────────────────────────


class BulkSyncNowInput(BaseModel):
    """Input for bulk sync-now action."""

    ids: list[int] = Field(..., min_length=1, description="Schedule IDs to sync")


class BulkToggleActiveInput(BaseModel):
    """Input for bulk toggle-active action."""

    ids: list[int] = Field(..., min_length=1, description="Schedule IDs to update")
    is_active: bool = Field(..., description="New active state")


class BulkDeleteInput(BaseModel):
    """Input for bulk delete action."""

    ids: list[int] = Field(..., min_length=1, description="Schedule IDs to delete")


class BulkResponse(BaseModel):
    """Response after a bulk action."""

    processed: int
    task_ids: list[str] | None = None
