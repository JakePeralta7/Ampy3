"""Playlist and track request/response schemas."""

from pydantic import BaseModel, Field


class PlaylistSyncRequest(BaseModel):
    """Request body for triggering a playlist sync."""
    playlist_url: str = Field(..., description="URL of the source playlist")
    source: str = Field(default="youtube_music", description="Source platform")
    replace_existing: bool = Field(default=False, description="Delete existing playlist and recreate")
    schedule_id: int | None = Field(default=None, description="Link result to an existing scheduled sync record")


class PlaylistSyncResponse(BaseModel):
    """Response after triggering a playlist sync."""
    message: str
    task_id: str
    status_url: str


class PlaylistSearchResponse(BaseModel):
    """Response from playlist search."""
    message: str
    playlists: list[dict]


class TrackSource(BaseModel):
    """Source track metadata."""
    title: str | None = None
    artist_name: str | None = None
    album_name: str | None = None
    duration_ms: int | None = None
    source_id: str | None = None


class TrackMatch(BaseModel):
    """Matched Plex track metadata."""
    plex_id: str | None = None
    title: str | None = None
    artist_name: str | None = None
    album_name: str | None = None
    duration: int | None = None


class TrackDetail(BaseModel):
    """Detailed track info with source and match."""
    source: TrackSource | None = None
    match: TrackMatch | None = None


class PlaylistTrackEntry(BaseModel):
    """A single playlist track with status."""
    plex_id: str | None = None
    title: str
    artist_name: str
    album_name: str
    duration: int | None = None
    status: str
    match_rate: str


class PlaylistTracksResponse(BaseModel):
    """Full track listing for a playlist."""
    playlist_id: str
    source: str
    tracks: list[dict]
    matched_tracks: list[dict]
    unmatched_tracks: list[dict]
    track_details: list[TrackDetail]
    total_count: int
    matched_count: int
    failed_count: int
    total_source_tracks: int
    match_rate: str
    match_percentage: int


class RematchTrackInput(BaseModel):
    """Input for rematching a track to Plex."""
    title: str
    artist_name: str = ""
    album_name: str | None = None


class RematchTrackResponse(BaseModel):
    """Response after rematching a track."""
    matched: bool
    message: str
    track: dict | None = None
