"""Data models for the Explore content discovery system.

These models provide a source-agnostic representation of browsable
music content — albums, playlists, artists, mood categories, charts —
that any ``ExploreProvider`` plugin returns.
"""

from __future__ import annotations

from dataclasses import dataclass, field
from enum import StrEnum


class ExploreItemType(StrEnum):
    ALBUM = "album"
    PLAYLIST = "playlist"
    ARTIST = "artist"
    SONG = "song"
    VIDEO = "video"


@dataclass
class ExploreItem:
    """A single browsable card shown in the Explore UI."""

    id: str
    title: str
    subtitle: str
    item_type: ExploreItemType
    thumbnail_url: str | None = None
    url: str | None = None
    source_id: str = ""


@dataclass
class ExploreSection:
    """A horizontal row of items on the Explore page."""

    title: str
    items: list[ExploreItem]
    see_all_link: str | None = None


@dataclass
class ExploreHome:
    """Top-level Explore page content (multiple sections)."""

    sections: list[ExploreSection] = field(default_factory=list)


@dataclass
class ChartsBundle:
    """Chart data: top songs, top artists, top videos (if applicable)."""

    top_songs: list[ExploreItem] = field(default_factory=list)
    top_artists: list[ExploreItem] = field(default_factory=list)
    top_videos: list[ExploreItem] = field(default_factory=list)


@dataclass
class MoodCategory:
    """A mood or genre category that contains playlists."""

    id: str
    name: str
    icon: str | None = None
    playlist_count: int | None = None
