"""Settings endpoints for runtime configuration."""

import logging
from datetime import UTC, datetime
from typing import Any

from fastapi import APIRouter, Depends, HTTPException
from pydantic import BaseModel

from src.app.auth.dependencies import get_current_user
from src.app.constants import SENSITIVE_CONFIG_KEYS
from src.app.db import AsyncSessionLocal
from src.app.models import Config
from src.app.schemas.settings import SettingsOut, SettingsUpdate
from src.app.services.audit import log_event
from src.app.services.crypto import (
    DecryptionError,
    decrypt_boot_token,
    decrypt_token,
    encrypt_boot_token,
    encrypt_token,
    encrypt_token_with_key,
    reset_crypto_caches,
)
from src.app.settings import settings

logger = logging.getLogger(__name__)

router = APIRouter(prefix="/api/v1/settings", tags=["settings"])

# All user-editable config keys (stored in DB config table)
USER_CONFIG_KEYS = [
    # Credentials
    "plex_host",
    "plex_token",
    "jellyfin_server_url",
    "jellyfin_api_key",
    "jellyfin_user_id",
    "ytmusic_auth",
    # Infrastructure
    "yt_dlp_timeout",
    "celery_broker_url",
    "celery_worker_concurrency",
    "celery_log_level",
    "log_format",
    "source_playlist_cache_ttl_seconds",
    "explore_cache_ttl_seconds",
    "session_ttl_hours",
    # Network
    "behind_proxy",
    "trusted_proxies",
    # Security & Server
    "require_auth",
    "app_url",
    "plex_client_id",
    "secret_key",
]

# Keys whose values must never be sent to the frontend.
_SENSITIVE_KEYS = {"plex_token", "jellyfin_api_key", "ytmusic_auth", "secret_key"}


def _decrypt_plaintext(value: str) -> str:
    """Decrypt a stored sensitive config value to its plaintext.

    Returns an empty string when the value cannot be decrypted (foreign key
    material, migration leftovers) so the caller falls back to re-encrypting.
    """
    try:
        return decrypt_token(value)
    except DecryptionError:
        return ""


def _build_settings_out(overrides: dict[str, str]) -> SettingsOut:
    import json

    from src.app.settings import settings

    def _parse_trusted_proxies(value: str) -> list[str]:
        """Parse comma-separated CIDR list or JSON array from config table."""
        if not value or not value.strip():
            return []
        raw = value.strip()
        if raw.startswith("["):
            try:
                parsed = json.loads(raw)
            except ValueError:
                logger.warning("trusted_proxies is not valid JSON — falling back to a plain list")
            else:
                return [str(item).strip() for item in parsed if str(item).strip()]
        return [part.strip() for part in raw.split(",") if part.strip()]

    behind_proxy_str = overrides.get("behind_proxy", str(settings.behind_proxy).lower())
    behind_proxy = behind_proxy_str.lower() in ("true", "1", "yes")

    trusted_proxies_str = overrides.get("trusted_proxies", "")
    trusted_proxies = _parse_trusted_proxies(trusted_proxies_str)

    sp_cache_default = str(settings.source_playlist_cache_ttl_seconds)
    ex_cache_default = str(settings.explore_cache_ttl_seconds)
    req_auth_default = str(settings.require_auth)
    req_auth_val = overrides.get("require_auth", req_auth_default).lower()

    return SettingsOut(
        plex_host=overrides.get("plex_host", settings.plex_host),
        plex_token_set=bool(overrides.get("plex_token", settings.plex_token)),
        jellyfin_server_url=overrides.get("jellyfin_server_url", settings.jellyfin_server_url),
        jellyfin_api_key_set=bool(overrides.get("jellyfin_api_key", settings.jellyfin_api_key)),
        jellyfin_user_id=overrides.get("jellyfin_user_id", settings.jellyfin_user_id),
        ytmusic_auth_set=bool(overrides.get("ytmusic_auth", settings.ytmusic_auth)),
        yt_dlp_timeout=int(overrides.get("yt_dlp_timeout", str(settings.yt_dlp_timeout))),
        celery_broker_url=overrides.get("celery_broker_url", settings.celery_broker_url),
        celery_worker_concurrency=int(
            overrides.get("celery_worker_concurrency", str(settings.celery_worker_concurrency))
        ),
        celery_log_level=overrides.get("celery_log_level", settings.celery_log_level),
        log_format=overrides.get("log_format", settings.log_format),
        source_playlist_cache_ttl_seconds=int(
            overrides.get("source_playlist_cache_ttl_seconds", sp_cache_default)
        ),
        explore_cache_ttl_seconds=int(overrides.get("explore_cache_ttl_seconds", ex_cache_default)),
        session_ttl_hours=int(overrides.get("session_ttl_hours", str(settings.session_ttl_hours))),
        behind_proxy=behind_proxy,
        trusted_proxies=trusted_proxies,
        require_auth=req_auth_val in ("true", "1", "yes"),
        app_url=overrides.get("app_url", settings.app_url),
        plex_client_id=overrides.get("plex_client_id", settings.plex_client_id),
        secret_key_set=bool(overrides.get("secret_key", settings.secret_key)),
    )


# ── Setup Endpoint (First Boot) ──────────────────────────────────────────


class SetupRequest(BaseModel):
    """Setup wizard initial configuration."""

    secret_key: str  # Required, ≥32 chars
    require_auth: bool


class SetupResponse(BaseModel):
    """Setup completion response."""

    success: bool
    message: str


@router.post("/setup", response_model=SetupResponse)
async def setup_initial_config(body: SetupRequest):
    """Configure initial system settings (first boot only).

    This endpoint is public (no auth required) and only works if secret_key
    is not yet configured. After setup, normal auth endpoints are enforced.
    """
    from sqlalchemy import select

    # Validate secret_key length
    if len(body.secret_key) < 32:
        raise HTTPException(
            status_code=400,
            detail="Secret key must be at least 32 characters",
        )

    async with AsyncSessionLocal() as session:
        # Check if already configured
        stmt = select(Config).where(Config.key == "secret_key")
        result = await session.execute(stmt)
        existing = result.scalar_one_or_none()

        if existing and existing.value:
            raise HTTPException(status_code=409, detail="Setup already completed")

        # Store initial config. The secret is wrapped with the boot key so it
        # can be recovered on the next start, before the working key is known.
        config_keys = {
            "secret_key": encrypt_boot_token(body.secret_key) or body.secret_key,
            "require_auth": str(body.require_auth).lower(),
        }

        for key, value in config_keys.items():
            stmt = select(Config).where(Config.key == key)
            result = await session.execute(stmt)
            row = result.scalar_one_or_none()

            if row:
                row.value = value
                row.updated_at = datetime.now(UTC)
            else:
                session.add(Config(key=key, value=value, updated_at=datetime.now(UTC)))

        await session.commit()

    # Update in-memory settings object so subsequent requests see the new values
    settings.secret_key = body.secret_key
    settings.require_auth = body.require_auth
    reset_crypto_caches()

    return SetupResponse(success=True, message="Setup completed. Please log in.")


# ── Settings Endpoints ──────────────────────────────────────────────────


class SecretKeyRotateRequest(BaseModel):
    """Request to rotate the secret key."""

    new_secret_key: str | None = None  # If not provided, auto-generate


class SecretKeyRotateResponse(BaseModel):
    """Response after rotating the secret key."""

    success: bool
    message: str
    new_secret_key: str | None = None  # Only returned when auto-generated


@router.post("/rotate-secret-key", response_model=SecretKeyRotateResponse)
async def rotate_secret_key(
    body: SecretKeyRotateRequest,
    _user: dict[str, Any] = Depends(get_current_user),  # noqa: B008
):
    """Rotate the secret key and re-encrypt all sensitive config values.

    If new_secret_key is not provided, a secure random key is generated.
    The new key must be at least 32 characters.
    """
    from sqlalchemy import select

    # Generate or validate new secret key
    if body.new_secret_key is not None:
        new_secret_key = body.new_secret_key
        if len(new_secret_key) < 32:
            raise HTTPException(
                status_code=400,
                detail="Secret key must be at least 32 characters",
            )
        auto_generated = False
    else:
        # Generate a 64-character hex string (32 random bytes)
        import secrets

        new_secret_key = secrets.token_hex(32)
        auto_generated = True

    async with AsyncSessionLocal() as session:
        # Get all sensitive config keys that need re-encryption
        stmt = select(Config).where(Config.key.in_(SENSITIVE_CONFIG_KEYS))
        result = await session.execute(stmt)
        rows = result.scalars().all()

        # Decrypt all current values with the OLD (working) key. The
        # ``secret_key`` row is boot-wrapped, so it uses the boot key.
        decrypted_values: dict[str, str] = {}
        for row in rows:
            if row.value:
                try:
                    if row.key == "secret_key":
                        decrypted_values[row.key] = decrypt_boot_token(row.value)
                    else:
                        decrypted_values[row.key] = decrypt_token(row.value)
                except DecryptionError:
                    # If decryption fails (e.g., different key), keep as-is.
                    # This shouldn't happen in normal operation.
                    logger.warning(f"Failed to decrypt {row.key} during secret key rotation")
                    decrypted_values[row.key] = ""

        # Encrypt every value with the NEW key. The ``secret_key`` row is
        # special: it is wrapped with the boot (deployment) key so the next
        # startup can recover it before the working key is known.
        for key, plaintext in decrypted_values.items():
            if not plaintext or key == "secret_key":
                continue
            encrypted = encrypt_token_with_key(plaintext, new_secret_key) or plaintext
            row = next((r for r in rows if r.key == key), None)
            if row:
                row.value = encrypted
                row.updated_at = datetime.now(UTC)
            else:
                session.add(Config(key=key, value=encrypted, updated_at=datetime.now(UTC)))

        # Update the secret_key row itself
        stmt = select(Config).where(Config.key == "secret_key")
        result = await session.execute(stmt)
        secret_row = result.scalar_one_or_none()

        new_secret_key_encrypted = encrypt_boot_token(new_secret_key) or new_secret_key

        if secret_row:
            secret_row.value = new_secret_key_encrypted
            secret_row.updated_at = datetime.now(UTC)
        else:
            session.add(
                Config(
                    key="secret_key",
                    value=new_secret_key_encrypted,
                    updated_at=datetime.now(UTC),
                )
            )

        await session.commit()

    # Switch the working key only after the new ciphertexts are committed.
    settings.secret_key = new_secret_key
    reset_crypto_caches()

    await log_event(
        event_type="settings.secret_key_rotated",
        summary="Secret key rotated and sensitive config re-encrypted",
        resource_type="settings",
        details={"auto_generated": auto_generated},
    )

    return SecretKeyRotateResponse(
        success=True,
        message="Secret key rotated successfully. All sensitive config re-encrypted.",
        new_secret_key=new_secret_key if auto_generated else None,
    )


@router.get("/", response_model=SettingsOut)
async def get_settings(
    _user: dict[str, Any] = Depends(get_current_user),  # noqa: B008
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
    _user: dict[str, Any] = Depends(get_current_user),  # noqa: B008
):
    """Update settings and persist to database."""
    from sqlalchemy import select

    incoming = body.model_dump(exclude_none=True, exclude_unset=True)
    if not incoming:
        raise HTTPException(status_code=400, detail="No settings provided")

    # Skip sensitive keys when empty — preserves existing value.
    for key in _SENSITIVE_KEYS:
        if key in incoming and incoming[key] == "":
            del incoming[key]

    if not incoming:
        raise HTTPException(status_code=400, detail="No settings provided")

    # The secret key must not be changed in place: every other sensitive value
    # is encrypted with it, so a plain write would make them undecryptable.
    if "secret_key" in incoming:
        raise HTTPException(
            status_code=400,
            detail="Use /api/v1/settings/rotate-secret-key to change the secret key",
        )

    # Encrypt sensitive tokens before storage
    sensitive_keys_to_encrypt = SENSITIVE_CONFIG_KEYS

    async with AsyncSessionLocal() as session:
        for key, value in incoming.items():
            if key not in USER_CONFIG_KEYS:
                raise HTTPException(status_code=400, detail=f"Unknown setting: {key}")

            stmt = select(Config).where(Config.key == key)
            result = await session.execute(stmt)
            row = result.scalar_one_or_none()

            # Convert lists to comma-separated strings for storage
            if isinstance(value, list):
                str_value = ",".join(str(v).strip() for v in value if v)
            else:
                str_value = str(value)

            if key in sensitive_keys_to_encrypt and str_value:
                # Fernet is non-deterministic: re-encrypting an unchanged token
                # would produce a new ciphertext, churning the config
                # fingerprint and resetting sync targets. Keep the stored
                # ciphertext when the plaintext is unchanged.
                if row and row.value and str_value == _decrypt_plaintext(row.value):
                    continue
                str_value = encrypt_token(str_value) or str_value
            else:
                # For non-sensitive keys, skip write if value is unchanged
                # to avoid churning the config fingerprint and resetting targets.
                if row and row.value == str_value:
                    continue

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

    await log_event(
        event_type="settings.updated",
        summary=f"Settings updated: {', '.join(incoming.keys())}",
        resource_type="settings",
        details={"keys_updated": list(incoming.keys())},
    )

    if "plex_host" in incoming or "plex_token" in incoming:
        from src.app.services.target import TargetService

        TargetService.reset()
    if (
        "jellyfin_server_url" in incoming
        or "jellyfin_api_key" in incoming
        or "jellyfin_user_id" in incoming
    ):
        from src.app.services.target import TargetService

        TargetService.reset()
    if "ytmusic_auth" in incoming:
        from src.app.services.ytauth import invalidate_ytmusic_auth_cache

        invalidate_ytmusic_auth_cache()

    return _build_settings_out(overrides)
