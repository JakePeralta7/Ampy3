"""Sync request/response schemas."""

from typing import Any

from pydantic import BaseModel, Field

from src.app.constants import DEFAULT_SOURCE, DEFAULT_TARGET
from src.app.schemas.playlists import TrackTarget


class SyncTriggerRequest(BaseModel):
    """Request body for triggering a sync."""

    playlist_url: str = Field(..., description="URL of the source playlist")
    source: str = Field(default=DEFAULT_SOURCE, description="Source platform")
    target_id: str = Field(default=DEFAULT_TARGET, description="Target platform")
    target_playlist_name: str | None = Field(
        default=None, description="Name for the target playlist"
    )
    schedule_id: int | None = Field(
        default=None,
        description="Link result to an existing scheduled sync record",
    )


class SyncTriggerResponse(BaseModel):
    """Response after triggering a sync."""

    message: str
    task_id: str
    status_url: str


class SyncTracksResponse(BaseModel):
    """Full track listing for a sync record."""

    playlist_id: str
    source: str
    tracks: list[dict[str, Any]]
    matched_tracks: list[dict[str, Any]]
    unmatched_tracks: list[dict[str, Any]]
    track_details: list[Any]  # list[TrackDetail] — avoids circular import
    total_count: int
    matched_count: int
    failed_count: int
    total_source_tracks: int
    match_rate: str
    match_percentage: int


class MatchTrackInput(BaseModel):
    """Input for matching a track to a target library."""

    title: str
    artist_name: str = ""
    album_name: str | None = None


class MatchTrackResponse(BaseModel):
    """Response after matching a track."""

    matched: bool
    message: str
    track: dict[str, Any] | None = None
    task_id: str | None = None


class UnmatchedTrackOut(BaseModel):
    """An unmatched track from a recent sync."""

    sync_id: int
    sync_name: str
    source_title: str | None = None
    source_artist: str | None = None
    source_album: str | None = None
    source_duration_ms: int | None = None


class SyncRunOut(BaseModel):
    """A single sync run record."""

    id: int
    sync_id: int
    target_id: str
    matched_count: int
    failed_count: int
    created_at: str | None = None


class SyncDiffItem(BaseModel):
    """A single track in a sync diff."""

    source_title: str | None = None
    source_artist: str | None = None
    source_album: str | None = None
    targets: list[TrackTarget] = []


class SyncDiffResponse(BaseModel):
    """Diff between two sync runs."""

    added: list[SyncDiffItem]
    removed: list[SyncDiffItem]
    unchanged: list[SyncDiffItem]
    from_run_id: int
    to_run_id: int
