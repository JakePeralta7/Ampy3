"""Playlist endpoints — listing and search."""

import logging
from typing import Any

from fastapi import APIRouter, Depends, HTTPException, Query

from src.app.auth.dependencies import get_current_user
from src.app.constants import DEFAULT_TARGET
from src.app.core.sources.registry import SourceRegistry
from src.app.schemas.playlists import PlaylistSearchResponse
from src.app.services import get_sync_target

logger = logging.getLogger(__name__)

router = APIRouter(prefix="/api/v1/playlists", tags=["playlists"])


@router.get("/sources")
async def list_sources(
    _user: dict[str, Any] = Depends(get_current_user),  # noqa: B008
):
    """List all available playlist source adapters."""
    return SourceRegistry.list_sources()


@router.get("/")
async def list_user_playlists(
    target_id: str = Query(default=DEFAULT_TARGET, description="Target platform ID"),
    _user: dict[str, Any] = Depends(get_current_user),  # noqa: B008
):
    """List all playlists the user owns in the selected target."""
    try:
        target = await get_sync_target(target_id)
        playlists = await target.search_playlists("")
        logger.info(f"Listed {len(playlists)} playlists")
        return playlists
    except Exception as e:
        logger.error(f"Error listing playlists: {e}")
        raise HTTPException(status_code=500, detail=f"Failed to list playlists: {str(e)}") from e


@router.get("/search", response_model=PlaylistSearchResponse)
async def search_playlists(
    query: str,
    target_id: str = Query(default=DEFAULT_TARGET, description="Target platform ID"),
    _user: dict[str, Any] = Depends(get_current_user),  # noqa: B008
):
    """Search target playlists by title or keywords."""
    try:
        target = await get_sync_target(target_id)
        results = await target.search_playlists(query)
        if not results:
            raise HTTPException(status_code=404, detail=f"No playlists found matching '{query}'")
        return PlaylistSearchResponse(message="Search successful", playlists=results)
    except HTTPException:
        raise
    except Exception as e:
        logger.error(f"Error searching playlists: {e}")
        raise HTTPException(status_code=500, detail=f"Failed to search playlists: {str(e)}") from e
