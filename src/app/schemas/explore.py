"""Explore API request/response schemas."""

from pydantic import BaseModel


class ExploreItemOut(BaseModel):
    id: str
    title: str
    subtitle: str
    item_type: str
    thumbnail_url: str | None = None
    url: str | None = None
    source_id: str = ""


class ExploreSectionOut(BaseModel):
    title: str
    items: list[ExploreItemOut]
    see_all_link: str | None = None


class ExploreHomeOut(BaseModel):
    sections: list[ExploreSectionOut]


class ChartsBundleOut(BaseModel):
    top_songs: list[ExploreItemOut] = []
    top_artists: list[ExploreItemOut] = []
    top_videos: list[ExploreItemOut] = []


class MoodCategoryOut(BaseModel):
    id: str
    name: str
    icon: str | None = None
    playlist_count: int | None = None


class ExploreProviderOut(BaseModel):
    provider_id: str
    display_name: str
