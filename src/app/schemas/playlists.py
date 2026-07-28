"""Playlist request/response schemas."""

from typing import Any

from pydantic import BaseModel


class PlaylistSearchResponse(BaseModel):
    """Response from playlist search."""

    message: str
    playlists: list[dict[str, Any]]


class TrackSource(BaseModel):
    """Source track metadata."""

    source_id: str = "YouTube Music"
    item_id: str | None = None
    title: str | None = None
    artist_name: str | None = None
    album_name: str | None = None
    duration_ms: int | None = None


class TrackTarget(BaseModel):
    """Matched track in a target media library."""

    target_id: str
    item_id: str
    title: str | None = None
    artist_name: str | None = None
    album_name: str | None = None
    duration: int | None = None


class TrackDetail(BaseModel):
    """Detailed track info with source and targets."""

    source: TrackSource | None = None
    targets: list[TrackTarget] = []
