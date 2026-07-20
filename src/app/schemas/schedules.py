"""Scheduled sync request/response schemas."""

from pydantic import BaseModel, Field


class CreateScheduledSyncInput(BaseModel):
    """Input schema for creating a scheduled sync."""
    source: str = Field(..., description="Source platform (e.g. youtube_music)")
    source_url: str = Field(..., description="URL of the source playlist")
    plex_playlist_name: str = Field(..., description="Name for the Plex playlist")
    schedule_interval: str = Field(..., description="Sync interval (e.g. daily, weekly, every_6h)")
    replace_existing: bool = Field(default=False, description="Replace existing playlist on sync")


class UpdateScheduledSyncInput(BaseModel):
    """Input schema for updating a scheduled sync."""
    plex_playlist_name: str | None = None
    schedule_interval: str | None = None
    is_active: bool | None = None
    replace_existing: bool | None = None


class ScheduledSyncOut(BaseModel):
    """Output schema for a scheduled sync."""
    id: int
    source: str
    source_url: str
    plex_playlist_name: str
    plex_playlist_id: str | None = None
    schedule_interval: str
    is_active: bool
    replace_existing: bool
    last_synced_at: str | None = None
    next_sync_at: str | None = None
    created_at: str | None = None
    updated_at: str | None = None
    error_message: str | None = None


class SyncNowResponse(BaseModel):
    """Response after manually triggering a sync."""
    task_id: str
    message: str


class SchedulerReloadResponse(BaseModel):
    """Response after reloading the scheduler."""
    message: str
