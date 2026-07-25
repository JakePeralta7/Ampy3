"""Sync target discovery endpoints."""

from fastapi import APIRouter, Depends

from src.app.auth.dependencies import get_current_user
from src.app.services import list_sync_targets

router = APIRouter(prefix="/api/v1/targets", tags=["targets"])


@router.get("/")
async def get_targets(
    _user: dict = Depends(get_current_user),  # noqa: B008
):
    """List all available sync targets."""
    return await list_sync_targets()
