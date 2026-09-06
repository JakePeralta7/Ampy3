"""Source discovery and connection test endpoints."""

import asyncio
import logging
from typing import Any

from fastapi import APIRouter, Depends

from src.app.auth.dependencies import get_current_user
from src.app.constants import SOURCE_DEEZER, SOURCE_YOUTUBE_MUSIC
from src.app.core.sources.registry import SourceRegistry
from src.app.schemas.sources import SourceTestRequest, SourceTestResponse
from src.app.services.ytauth import get_ytmusic_auth, validate_ytmusic_auth

logger = logging.getLogger(__name__)

router = APIRouter(prefix="/api/v1/sources", tags=["sources"])

# Sources that authenticate anonymously with no configuration required.
_ANONYMOUS_SOURCES = {SOURCE_DEEZER}


@router.get("/")
async def get_sources(
    _user: dict[str, Any] = Depends(get_current_user),  # noqa: B008
):
    """List all available sources with their authentication requirements."""
    sources = []
    for source in SourceRegistry.list_sources():
        source_id = str(source["id"])
        auth_set = None
        if source_id == SOURCE_YOUTUBE_MUSIC:
            auth_set = bool(await asyncio.to_thread(get_ytmusic_auth))
        sources.append(
            {
                "id": source_id,
                "name": source["name"],
                "auth_required": source_id not in _ANONYMOUS_SOURCES,
                "auth_set": auth_set,
            }
        )
    return sources


@router.post("/test", response_model=SourceTestResponse)
async def test_source(
    body: SourceTestRequest,
    _user: dict[str, Any] = Depends(get_current_user),  # noqa: B008
):
    """Test a source with the provided auth payload.

    The payload is transient — used only for the test and never persisted.
    Anonymous sources trivially pass.
    """
    if body.source_id == SOURCE_YOUTUBE_MUSIC:
        try:
            await asyncio.to_thread(validate_ytmusic_auth, body.auth or "")
            return SourceTestResponse(ok=True)
        except Exception as exc:
            logger.warning("Source test failed for %s: %s", body.source_id, exc)
            return SourceTestResponse(ok=False, error=str(exc))

    if body.source_id in _ANONYMOUS_SOURCES:
        return SourceTestResponse(ok=True)

    return SourceTestResponse(ok=False, error=f"Unknown source: {body.source_id}")
