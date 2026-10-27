"""Database-backed Plex configuration accessors for the SSO flow.

These helpers read/write the ``config`` rows that store the Plex client
identifier and owner credentials. Keeping them here lets the auth router stay
focused on HTTP concerns.
"""

import logging
import uuid
from datetime import UTC, datetime

from sqlalchemy import select

from src.app.db import AsyncSessionLocal
from src.app.models import Config
from src.app.services.crypto import decrypt_token, encrypt_token

logger = logging.getLogger(__name__)

_client_id_cache: str | None = None


async def _get_config_value(key: str) -> str | None:
    """Return a raw config value, or ``None`` when the key is absent."""
    async with AsyncSessionLocal() as session:
        row = (await session.execute(select(Config).where(Config.key == key))).scalar_one_or_none()
        return row.value if row else None


async def _get_client_id() -> str:
    """Return a stable Plex client identifier (persisted in the config table)."""
    global _client_id_cache  # noqa: PLW0603
    if _client_id_cache:
        return _client_id_cache

    stored = await _get_config_value("plex_client_id")
    if stored:
        _client_id_cache = stored
        return stored

    new_id = str(uuid.uuid4())
    async with AsyncSessionLocal() as session:
        session.add(Config(key="plex_client_id", value=new_id))
        await session.commit()
    _client_id_cache = new_id
    return new_id


async def _get_owner_id() -> str | None:
    """Return the stored owner plex_user_id, or ``None`` if unregistered."""
    return await _get_config_value("owner_plex_user_id")


async def get_owner_plex_token() -> str | None:
    """Return the owner's Plex token, or ``None`` if not stored."""
    value = await _get_config_value("owner_plex_token")
    return decrypt_token(value) if value else None


async def get_plex_server_url() -> str | None:
    """Return the configured Plex Media Server URL, or ``None``."""
    return await _get_config_value("plex_server_url")


async def register_owner(plex_user_id: str, auth_token: str) -> None:
    """Persist the first authenticated user as the owner."""
    async with AsyncSessionLocal() as session:
        session.add(Config(key="owner_plex_user_id", value=plex_user_id))
        session.add(Config(key="owner_plex_token", value=encrypt_token(auth_token)))
        await session.commit()


async def save_plex_target_config(server_url: str, access_token: str) -> None:
    """Store the verified Plex server URL/token and invalidate cached targets."""
    async with AsyncSessionLocal() as session:
        now = datetime.now(UTC)
        for key, value in (
            ("plex_host", server_url),
            ("plex_token", encrypt_token(access_token)),
        ):
            row = (
                await session.execute(select(Config).where(Config.key == key))
            ).scalar_one_or_none()
            if row:
                row.value = value
                row.updated_at = now
            else:
                session.add(Config(key=key, value=value, updated_at=now))

        await session.commit()

    from src.app.services.target import TargetService

    TargetService.reset()
