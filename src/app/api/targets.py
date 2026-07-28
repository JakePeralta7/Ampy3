"""Sync target discovery and connection test endpoints."""

import logging
from typing import Any

from fastapi import APIRouter, Depends, HTTPException

from src.app.auth.dependencies import get_current_user
from src.app.constants import TARGET_JELLYFIN, TARGET_PLEX
from src.app.db import AsyncSessionLocal
from src.app.models import Config
from src.app.schemas.targets import TargetTestRequest, TargetTestResponse
from src.app.services import list_sync_targets

logger = logging.getLogger(__name__)

router = APIRouter(prefix="/api/v1/targets", tags=["targets"])

_TARGET_CONFIG_KEYS: dict[str, list[str]] = {
    TARGET_PLEX: ["plex_host", "plex_token"],
    TARGET_JELLYFIN: ["jellyfin_server_url", "jellyfin_api_key", "jellyfin_user_id"],
}


@router.get("/")
async def get_targets(
    _user: dict[str, Any] = Depends(get_current_user),  # noqa: B008
):
    """List all available sync targets."""
    return await list_sync_targets()


@router.get("/configured", response_model=list[str])
async def get_configured_targets(
    _user: dict[str, Any] = Depends(get_current_user),  # noqa: B008
):
    """Return list of configured targets (only includes Plex/Jellyfin if configured)."""
    from sqlalchemy import select

    async with AsyncSessionLocal() as session:
        stmt = select(Config).where(
            Config.key.in_(["plex_host", "plex_token", "jellyfin_server_url", "jellyfin_api_key"])
        )
        result = await session.execute(stmt)
        rows = result.scalars().all()
        overrides = {row.key: row.value for row in rows}

    targets = []

    if overrides.get("plex_host") and overrides.get("plex_token"):
        targets.append(TARGET_PLEX)

    if overrides.get("jellyfin_server_url") and overrides.get("jellyfin_api_key"):
        targets.append(TARGET_JELLYFIN)

    return targets


# ── Connection test ────────────────────────────────────────────────────


async def _create_target_from_config(target_id: str, config: dict[str, str]):
    """Create a target instance from the given config dict, falling back to DB for empty values."""
    from sqlalchemy import select

    from src.app.db import SessionLocal
    from src.app.models import Config

    expected_keys = _TARGET_CONFIG_KEYS.get(target_id, [])

    # Fetch existing values from DB for fallback
    db = SessionLocal()
    try:
        result = db.execute(select(Config).where(Config.key.in_(expected_keys)))
        rows = {row.key: row.value for row in result.scalars().all()}
    finally:
        db.close()

    # Merge: provided values take precedence, empty strings fall back to DB
    merged = {k: (config.get(k, "") or rows.get(k, "")) for k in expected_keys}

    if target_id == TARGET_PLEX:
        from src.app.core.targets.plex import PlexTarget

        return PlexTarget(token=merged["plex_token"], base_url=merged["plex_host"])
    elif target_id == TARGET_JELLYFIN:
        from src.app.core.targets.jellyfin import JellyfinTarget

        return JellyfinTarget(
            api_key=merged["jellyfin_api_key"],
            base_url=merged["jellyfin_server_url"],
            user_id=merged["jellyfin_user_id"],
        )
    raise HTTPException(status_code=400, detail=f"Unknown target: {target_id}")


@router.post("/test", response_model=TargetTestResponse)
async def test_target(
    body: TargetTestRequest,
    _user: dict[str, Any] = Depends(get_current_user),  # noqa: B008
):
    """Test connectivity to a target with the provided credentials.

    Credentials are transient — they are used only for the test and never persisted.
    """
    expected_keys = _TARGET_CONFIG_KEYS.get(body.target_id)
    if expected_keys is None:
        raise HTTPException(status_code=400, detail=f"Unknown target: {body.target_id}")

    config = {k: body.config.get(k, "") for k in expected_keys}

    try:
        target = await _create_target_from_config(body.target_id, config)
        await target.test_connection()
        await target.close()
        return TargetTestResponse(ok=True)
    except Exception as exc:
        logger.warning("Target test failed for %s: %s", body.target_id, exc)
        return TargetTestResponse(ok=False, error=str(exc))
