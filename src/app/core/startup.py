"""Shared startup logic for API and worker.

Centralizes config loading and startup validation so both entry points
(API lifespan, Celery worker) stay in sync without duplicating the
environment/DB merge and SECRET_KEY gate.
"""

from __future__ import annotations

import logging
from typing import Any

from src.app.settings import settings as default_settings

logger = logging.getLogger(__name__)


async def load_settings_overrides_async(settings_obj: Any | None = None) -> dict[str, str]:
    """Load user-editable settings from the config table (async, for API lifespan).

    Merges DB-stored values over environment defaults. Sensitive keys are
    decrypted before being applied to the settings object. Returns the raw
    (still-encrypted) overrides so callers can tell whether the instance has
    already been set up.
    """
    s = settings_obj or default_settings
    from sqlalchemy import select

    from src.app.db import AsyncSessionLocal
    from src.app.models import Config

    async with AsyncSessionLocal() as session:
        stmt = select(Config)
        result = await session.execute(stmt)
        rows = result.scalars().all()
        overrides = {row.key: row.value for row in rows}

    if overrides:
        s.load_overrides(overrides)

    return overrides


def load_settings_overrides_sync(settings_obj: Any | None = None) -> dict[str, str] | None:
    """Load user-editable settings from the config table (sync, for worker bootstrap).

    Best-effort: returns None when the DB cannot be read (e.g. schema not migrated yet).
    Returns the raw overrides dict on success, or None on any exception.
    """
    s = settings_obj or default_settings
    try:
        from sqlalchemy import select

        from src.app.db import SessionLocal
        from src.app.models import Config

        with SessionLocal() as session:
            rows = session.execute(select(Config)).scalars().all()
        overrides = {row.key: row.value for row in rows}
        if overrides:
            s.load_overrides(overrides)
        return overrides
    except Exception as exc:  # pragma: no cover - startup best effort
        # Don't warn for expected "table doesn't exist" errors on fresh installs
        # (schema not migrated yet). Only log unexpected errors.
        error_msg = str(exc).lower()
        missing_table = "does not exist" in error_msg and (
            "relation" in error_msg or "table" in error_msg
        )
        if missing_table:
            logger.debug("Config table not yet created (schema not migrated): %s", exc)
        else:
            logger.warning("Could not load settings overrides: %s", exc)
        return None


def enforce_startup_gate(
    settings_obj: Any | None = None, *, allow_unconfigured: bool = False
) -> None:
    """Fail closed when the app is not configured with a usable SECRET_KEY.

    ``SECRET_KEY`` keys both the session signing and the at-rest token
    encryption, so an empty (or too short) key would silently encrypt
    credentials with a well-known value.

    The check runs *after* DB-stored settings are applied because the working
    key lives in the ``config`` table. A fresh install has no key yet: set
    ``allow_unconfigured=True`` so it can boot into the setup wizard. A
    configured instance with an unusable key still fails hard.
    """
    s = settings_obj or default_settings
    has_key = bool(s.secret_key)
    has_usable_key = has_key and len(s.secret_key) >= 32

    if has_usable_key:
        return

    if has_key:
        raise RuntimeError(
            "SECRET_KEY must be at least 32 characters. "
            'Generate one with: python -c "import secrets; print(secrets.token_hex(32))"'
        )

    # No key at all: REQUIRE_AUTH can never work, and a production install
    # that has already been configured must not serve without its key.
    if s.require_auth:
        raise RuntimeError(
            "REQUIRE_AUTH=true requires SECRET_KEY (at least 32 characters). "
            'Generate one with: python -c "import secrets; print(secrets.token_hex(32))"'
        )

    if s.app_env == "production" and not allow_unconfigured:
        raise RuntimeError(
            "APP_ENV=production requires SECRET_KEY (at least 32 characters). "
            'Generate one with: python -c "import secrets; print(secrets.token_hex(32))"'
        )


def validate_worker_startup(configured: bool | None, settings_obj: Any | None = None) -> None:
    """Validate worker-specific startup requirements after loading config.

    The worker only starts when the instance is properly configured.
    """
    s = settings_obj or default_settings

    # If the secret_key row existed in DB but couldn't be decrypted (e.g.
    # SECRET_KEY rotated without re-encryption), we cannot proceed safely.
    failed = getattr(s, "failed_decryptions", set()) or set()
    if "secret_key" in failed:
        raise RuntimeError(
            "Failed to decrypt the stored SECRET_KEY from the config table. "
            "This usually means the deployment SECRET_KEY changed. Set the original "
            "SECRET_KEY in the environment, or clear the 'secret_key' row from the "
            "config table and reconfigure via the setup wizard."
        )

    # Worker must only start when the app is configured (secret_key present).
    if configured is not True:
        raise RuntimeError(
            "Ampy3 is not configured yet. Complete setup via the web UI first "
            "(set SECRET_KEY and other settings), then start the worker."
        )

    # Fail closed: production requires a SECRET_KEY so token encryption at
    # rest is never keyed from a fixed, well-known value.
    if s.app_env == "production" and (not s.secret_key or len(s.secret_key) < 32):
        raise RuntimeError(
            "APP_ENV=production requires SECRET_KEY (at least 32 characters). "
            'Generate one with: python -c "import secrets; print(secrets.token_hex(32))"'
        )

    # Fail closed: REQUIRE_AUTH=true without SECRET_KEY is a hard error
    if s.require_auth and (not s.secret_key or len(s.secret_key) < 32):
        raise RuntimeError(
            "REQUIRE_AUTH=true requires SECRET_KEY (at least 32 characters). "
            'Generate one with: python -c "import secrets; print(secrets.token_hex(32))"'
        )

    # If other sensitive values failed to decrypt while the instance is
    # configured, the worker cannot safely process syncs that need those tokens.
    if failed:
        raise RuntimeError(
            "Failed to decrypt one or more sensitive config values: "
            f"{', '.join(sorted(failed))}. "
            "Restore the original SECRET_KEY or re-enter these values in Settings."
        )
