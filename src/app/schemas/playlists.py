"""Playlist and track request/response schemas."""

from pydantic import BaseModel, Field


class PlaylistSyncRequest(BaseModel):
    """Request body for triggering a playlist sync."""

    playlist_url: str = Field(..., description="URL of the source playlist")
    source: str = Field(default="youtube_music", description="Source platform")
    target_id: str = Field(default="plex", description="Target platform")
    replace_existing: bool = Field(
        default=False, description="Delete existing playlist and recreate"
    )
    target_playlist_name: str | None = Field(
        default=None, description="Name for the target playlist"
    )
    schedule_id: int | None = Field(
        default=None,
        description="Link result to an existing scheduled sync record",
    )


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
    matched_count: int
    failed_count: int
    created_at: str | None = None


class SyncDiffItem(BaseModel):
    """A single track in a sync diff."""

    source_title: str | None = None
    source_artist: str | None = None
    source_album: str | None = None
    match_item_id: str | None = None
    match_title: str | None = None
    match_artist: str | None = None


class SyncDiffResponse(BaseModel):
    """Diff between two sync runs."""

    added: list[SyncDiffItem]
    removed: list[SyncDiffItem]
    unchanged: list[SyncDiffItem]
    from_run_id: int
    to_run_id: int
