"""Explore content discovery endpoints.

Exposes a source-agnostic browse API backed by ``ExploreProvider``
plugins registered via ``@register_explore_provider``.
"""

from __future__ import annotations

import logging
from typing import Any

from fastapi import APIRouter, Depends, HTTPException, Query

from src.app.auth.dependencies import get_current_user
from src.app.core.explore import ExploreRegistry
from src.app.core.explore.models import ChartsBundle, ExploreHome, ExploreItem, MoodCategory
from src.app.schemas.explore import (
    ChartsBundleOut,
    ExploreHomeOut,
    ExploreItemOut,
    ExploreProviderOut,
    ExploreSectionOut,
    MoodCategoryOut,
)

logger = logging.getLogger(__name__)

router = APIRouter(prefix="/api/v1/explore", tags=["explore"])


def _provider_instance(provider_id: str):
    """Return an instantiated ExploreProvider by ID, or raise 404."""
    try:
        cls = ExploreRegistry.get(provider_id)
    except KeyError as exc:
        raise HTTPException(
            status_code=404, detail=f"Unknown explore provider: {provider_id}"
        ) from exc
    return cls()


def _item_out(item: ExploreItem) -> ExploreItemOut:
    return ExploreItemOut(
        id=item.id,
        title=item.title,
        subtitle=item.subtitle,
        item_type=item.item_type.value,
        thumbnail_url=item.thumbnail_url,
        url=item.url,
        source_id=item.source_id,
    )


# ── Provider metadata ────────────────────────────────────────────────


@router.get("/providers", response_model=list[ExploreProviderOut])
async def list_providers(
    _user: dict[str, Any] = Depends(get_current_user),  # noqa: B008
):
    """List all registered Explore providers."""
    return [ExploreProviderOut(**p) for p in ExploreRegistry.list_providers()]


# ── Home (sections) ──────────────────────────────────────────────────


@router.get("/home", response_model=ExploreHomeOut)
async def get_home(
    provider: str = Query("youtube_music", description="Provider ID"),
    _user: dict[str, Any] = Depends(get_current_user),  # noqa: B008
):
    """Return the main Explore page (sections of mixed content)."""
    prov = _provider_instance(provider)
    try:
        home: ExploreHome = await prov.get_home()
    except Exception as exc:
        logger.error("Explore home failed for '%s': %s", provider, exc, exc_info=True)
        raise HTTPException(status_code=502, detail=str(exc)) from exc

    return ExploreHomeOut(
        sections=[
            ExploreSectionOut(
                title=s.title,
                items=[_item_out(i) for i in s.items],
                see_all_link=s.see_all_link,
            )
            for s in home.sections
        ]
    )


# ── Charts ───────────────────────────────────────────────────────────


@router.get("/charts", response_model=ChartsBundleOut)
async def get_charts(
    provider: str = Query("youtube_music", description="Provider ID"),
    _user: dict[str, Any] = Depends(get_current_user),  # noqa: B008
):
    """Return top songs, artists, and videos."""
    prov = _provider_instance(provider)
    try:
        charts: ChartsBundle = await prov.get_charts()
    except Exception as exc:
        logger.error("Explore charts failed for '%s': %s", provider, exc, exc_info=True)
        raise HTTPException(status_code=502, detail=str(exc)) from exc

    return ChartsBundleOut(
        top_songs=[_item_out(i) for i in charts.top_songs],
        top_artists=[_item_out(i) for i in charts.top_artists],
        top_videos=[_item_out(i) for i in charts.top_videos],
    )


# ── Moods ────────────────────────────────────────────────────────────


@router.get("/moods", response_model=list[MoodCategoryOut])
async def get_moods(
    provider: str = Query("youtube_music", description="Provider ID"),
    _user: dict[str, Any] = Depends(get_current_user),  # noqa: B008
):
    """Return available mood / genre categories."""
    prov = _provider_instance(provider)
    try:
        moods: list[MoodCategory] = await prov.get_moods()
    except Exception as exc:
        logger.error("Explore moods failed for '%s': %s", provider, exc, exc_info=True)
        raise HTTPException(status_code=502, detail=str(exc)) from exc

    return [
        MoodCategoryOut(
            id=m.id,
            name=m.name,
            icon=m.icon,
            playlist_count=m.playlist_count,
        )
        for m in moods
    ]


# ── Mood drill-down ──────────────────────────────────────────────────


@router.get("/moods/{mood_id}/playlists", response_model=list[ExploreItemOut])
async def get_mood_playlists(
    mood_id: str,
    provider: str = Query("youtube_music", description="Provider ID"),
    _user: dict[str, Any] = Depends(get_current_user),  # noqa: B008
):
    """Return playlists for a given mood or genre category."""
    prov = _provider_instance(provider)
    try:
        playlists: list[ExploreItem] = await prov.get_mood_playlists(mood_id)
    except Exception as exc:
        logger.error(
            "Explore mood playlists failed for '%s'/%s: %s", provider, mood_id, exc, exc_info=True
        )
        raise HTTPException(status_code=502, detail=str(exc)) from exc

    return [_item_out(i) for i in playlists]
