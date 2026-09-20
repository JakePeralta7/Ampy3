"""System metadata endpoints."""

from typing import Any

from fastapi import APIRouter, Depends

from src.app import __version__
from src.app.auth.dependencies import get_current_user

router = APIRouter(prefix="/api/v1/system", tags=["system"])


@router.get("/version")
async def get_version(_user: dict[str, Any] = Depends(get_current_user)):  # noqa: B008
    """Return the running application version."""
    return {"version": __version__, "repository_url": "https://github.com/JakePeralta7/Ampy3"}
