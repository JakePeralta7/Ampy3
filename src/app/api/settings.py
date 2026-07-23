"""Settings endpoints for runtime configuration."""

import logging
from datetime import UTC, datetime

from fastapi import APIRouter, Depends, HTTPException

from src.app.auth.dependencies import get_current_user
from src.app.db import AsyncSessionLocal
from src.app.models import Config
from src.app.schemas.settings import SettingsOut, SettingsUpdate
from src.app.settings import settings

logger = logging.getLogger(__name__)

router = APIRouter(prefix="/api/v1/settings", tags=["settings"])

USER_CONFIG_KEYS = [
    "plex_host",
    "plex_token",
    "ollama_host",
    "ollama_model",
    "ollama_timeout",
    "yt_dlp_cookies",
    "yt_dlp_timeout",
]


def _mask_token(token: str) -> str:
    if len(token) <= 4:
        return "****"
    return f"****{token[-4:]}"


def _build_settings_out(overrides: dict[str, str]) -> SettingsOut:
    return SettingsOut(
        plex_host=overrides.get("plex_host", ""),
        plex_token=_mask_token(overrides.get("plex_token", "")),
        ollama_host=overrides.get("ollama_host", settings.ollama_host),
        ollama_model=overrides.get("ollama_model", settings.ollama_model),
        ollama_timeout=int(overrides.get("ollama_timeout", str(settings.ollama_timeout))),
        yt_dlp_cookies=overrides.get("yt_dlp_cookies", settings.yt_dlp_cookies),
        yt_dlp_timeout=int(overrides.get("yt_dlp_timeout", str(settings.yt_dlp_timeout))),
    )


@router.get("/", response_model=SettingsOut)
async def get_settings(
    _user: dict = Depends(get_current_user),  # noqa: B008
):
    """Return current settings (env defaults merged with DB overrides)."""
    from sqlalchemy import select

    async with AsyncSessionLocal() as session:
        stmt = select(Config).where(Config.key.in_(USER_CONFIG_KEYS))
        result = await session.execute(stmt)
        rows = result.scalars().all()
        overrides = {row.key: row.value for row in rows}
    return _build_settings_out(overrides)


@router.put("/", response_model=SettingsOut)
async def put_settings(
    body: SettingsUpdate,
    _user: dict = Depends(get_current_user),  # noqa: B008
):
    """Update settings and persist to database."""
    from sqlalchemy import select

    incoming = body.model_dump(exclude_none=True, exclude_unset=True)
    if not incoming:
        raise HTTPException(status_code=400, detail="No settings provided")

    async with AsyncSessionLocal() as session:
        for key, value in incoming.items():
            if key not in USER_CONFIG_KEYS:
                raise HTTPException(status_code=400, detail=f"Unknown setting: {key}")

            stmt = select(Config).where(Config.key == key)
            result = await session.execute(stmt)
            row = result.scalar_one_or_none()

            str_value = str(value)
            if row:
                row.value = str_value
                row.updated_at = datetime.now(UTC)
            else:
                session.add(Config(key=key, value=str_value, updated_at=datetime.now(UTC)))

        await session.commit()

        stmt = select(Config).where(Config.key.in_(USER_CONFIG_KEYS))
        result = await session.execute(stmt)
        rows = result.scalars().all()
        overrides = {row.key: row.value for row in rows}

    settings.load_overrides(overrides)

    if "plex_host" in incoming or "plex_token" in incoming:
        from src.app.services.plex import PlexService
        PlexService.reset()
    if "ollama_host" in incoming or "ollama_model" in incoming or "ollama_timeout" in incoming:
        from src.app.services.ollama import OllamaService
        OllamaService.reset()

    return _build_settings_out(overrides)
