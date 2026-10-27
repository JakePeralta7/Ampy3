"""SettingsService — business logic for runtime configuration management.

Centralizes all settings-related operations including encryption/decryption,
config persistence, and config fingerprint management.
"""

import json
import logging
import secrets
from datetime import UTC, datetime
from typing import Any

from sqlalchemy import select

from src.app.constants import SENSITIVE_CONFIG_KEYS
from src.app.db import AsyncSessionLocal
from src.app.models import Config
from src.app.schemas.settings import SettingsOut
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

# Keys that require a service restart to take effect.
# These are read once at startup and cannot be changed at runtime.
RESTART_REQUIRED_KEYS = {
    "celery_broker_url",
    "celery_worker_concurrency",
    "celery_log_level",
    "log_format",
    "plex_client_id",
    # secret_key is handled separately via rotate_secret_key()
}

# Keys that can be changed at runtime without restart.
RUNTIME_CONFIG_KEYS = [
    k for k in USER_CONFIG_KEYS if k not in RESTART_REQUIRED_KEYS and k != "secret_key"
]

# Keys whose values must never be sent to the frontend. Derived from the
# canonical sensitive-key set so the two lists can never drift apart.
_SENSITIVE_KEYS = SENSITIVE_CONFIG_KEYS.intersection(USER_CONFIG_KEYS)


class SettingsService:
    """Service layer for settings management.

    Encapsulates all business logic for reading, writing, and encrypting
    configuration values. The API layer should only handle HTTP concerns.
    """

    def __init__(self) -> None:
        pass

    # ── Internal Helpers ──────────────────────────────────────────

    def _decrypt_plaintext(self, value: str) -> str:
        """Decrypt a stored sensitive config value to its plaintext.

        Returns an empty string when the value cannot be decrypted (foreign key
        material, migration leftovers) so the caller falls back to re-encrypting.
        """
        try:
            return decrypt_token(value)
        except DecryptionError:
            return ""

    def _parse_trusted_proxies(self, value: str) -> list[str]:
        """Parse comma-separated CIDR list or JSON array from config table."""
        from src.app.core.trusted_proxies import parse_trusted_proxies

        return parse_trusted_proxies(value)

    def _build_settings_out(self, overrides: dict[str, str]) -> SettingsOut:
        """Build SettingsOut response from DB overrides + env defaults."""
        behind_proxy_str = overrides.get("behind_proxy", str(settings.behind_proxy).lower())
        behind_proxy = behind_proxy_str.lower() in ("true", "1", "yes")

        trusted_proxies_str = overrides.get("trusted_proxies", "")
        trusted_proxies = self._parse_trusted_proxies(trusted_proxies_str)

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
            explore_cache_ttl_seconds=int(
                overrides.get("explore_cache_ttl_seconds", ex_cache_default)
            ),
            session_ttl_hours=int(
                overrides.get("session_ttl_hours", str(settings.session_ttl_hours))
            ),
            behind_proxy=behind_proxy,
            trusted_proxies=trusted_proxies,
            require_auth=req_auth_val in ("true", "1", "yes"),
            app_url=overrides.get("app_url", settings.app_url),
            plex_client_id=overrides.get("plex_client_id", settings.plex_client_id),
            secret_key_set=bool(overrides.get("secret_key", settings.secret_key)),
        )

    # ── Public API ────────────────────────────────────────────────

    async def setup_initial_config(self, secret_key: str, require_auth: bool) -> tuple[bool, str]:
        """Configure initial system settings (first boot only).

        Returns (success, message).
        """
        # Validate secret_key length
        if len(secret_key) < 32:
            return False, "Secret key must be at least 32 characters"

        async with AsyncSessionLocal() as session:
            # Check if already configured
            stmt = select(Config).where(Config.key == "secret_key")
            result = await session.execute(stmt)
            existing = result.scalar_one_or_none()

            if existing and existing.value:
                return False, "Setup already completed"

            # Store initial config. The secret is wrapped with the boot key so it
            # can be recovered on the next start, before the working key is known.
            config_keys = {
                "secret_key": encrypt_boot_token(secret_key) or secret_key,
                "require_auth": str(require_auth).lower(),
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
        settings.secret_key = secret_key
        settings.require_auth = require_auth
        reset_crypto_caches()

        return True, "Setup completed. Please log in."

    async def get_settings(self) -> SettingsOut:
        """Return current settings (env defaults merged with DB overrides)."""
        async with AsyncSessionLocal() as session:
            stmt = select(Config).where(Config.key.in_(USER_CONFIG_KEYS))
            result = await session.execute(stmt)
            rows = result.scalars().all()
            overrides = {row.key: row.value for row in rows}
        return self._build_settings_out(overrides)

    async def update_settings(self, updates: dict[str, Any]) -> SettingsOut:
        """Update settings and persist to database.

        Returns the new settings state.
        """
        incoming = {k: v for k, v in updates.items() if v is not None}
        if not incoming:
            raise ValueError("No settings provided")

        # Check for restart-required keys BEFORE any DB transaction
        restart_keys = [k for k in incoming if k in RESTART_REQUIRED_KEYS]
        if restart_keys:
            keys_str = ", ".join(sorted(restart_keys))
            msg = (
                "The following settings require a service restart to take effect: "
                f"{keys_str}. "
                "Please update them via environment variables or the config file "
                "and restart the service."
            )
            raise ValueError(msg)

        # The secret key must not be changed in place: every other sensitive value
        # is encrypted with it, so a plain write would make them undecryptable.
        if "secret_key" in incoming:
            raise ValueError("Use rotate_secret_key() to change the secret key")

        # Skip sensitive keys when empty — preserves existing value.
        for key in _SENSITIVE_KEYS:
            if key in incoming and incoming[key] == "":
                del incoming[key]

        if not incoming:
            raise ValueError("No settings provided")

        # Encrypt sensitive tokens before storage
        async with AsyncSessionLocal() as session:
            for key, value in incoming.items():
                if key not in USER_CONFIG_KEYS:
                    raise ValueError(f"Unknown setting: {key}")

                stmt = select(Config).where(Config.key == key)
                result = await session.execute(stmt)
                row = result.scalar_one_or_none()

                # Convert lists to comma-separated strings for storage
                if isinstance(value, list):
                    str_value = ",".join(str(v).strip() for v in value if v)
                else:
                    str_value = str(value)

                if key in SENSITIVE_CONFIG_KEYS and str_value:
                    # Fernet is non-deterministic: re-encrypting an unchanged token
                    # would produce a new ciphertext, churning the config
                    # fingerprint and resetting sync targets. Keep the stored
                    # ciphertext when the plaintext is unchanged.
                    if row and row.value and str_value == self._decrypt_plaintext(row.value):
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

        return self._build_settings_out(overrides)

    async def rotate_secret_key(
        self, new_secret_key: str | None = None
    ) -> tuple[bool, str, str | None]:
        """Rotate the secret key and re-encrypt all sensitive config values.

        Returns (success, message, new_secret_key_if_auto_generated).
        """
        # Generate or validate new secret key
        if new_secret_key is not None:
            if len(new_secret_key) < 32:
                return False, "Secret key must be at least 32 characters", None
            auto_generated = False
        else:
            # Generate a 64-character hex string (32 random bytes)
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
                        logger.warning("Failed to decrypt %s during secret key rotation", row.key)
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

        return (
            True,
            "Secret key rotated successfully. All sensitive config re-encrypted.",
            (new_secret_key if auto_generated else None),
        )

    async def get_overrides(self) -> dict[str, str]:
        """Get all config overrides from the database."""
        async with AsyncSessionLocal() as session:
            stmt = select(Config).where(Config.key.in_(USER_CONFIG_KEYS))
            result = await session.execute(stmt)
            rows = result.scalars().all()
            return {row.key: row.value for row in rows}


# Module-level singleton
_settings_service: SettingsService | None = None


def get_settings_service() -> SettingsService:
    """Get the global SettingsService instance."""
    global _settings_service
    if _settings_service is None:
        _settings_service = SettingsService()
    return _settings_service


def reset_settings_service() -> None:
    """Reset the SettingsService instance (for testing)."""
    global _settings_service
    _settings_service = None
