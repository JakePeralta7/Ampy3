import json
import logging
from typing import Annotated, Any, Literal, Self

from pydantic import Field, field_validator, model_validator
from pydantic_settings import BaseSettings, NoDecode

logger = logging.getLogger(__name__)


class Settings(BaseSettings):
    # Database — host/port hardcoded; user/pass from env vars
    database_host: str = "postgres"
    database_port: int = 5432
    database_name: str = "ampy3"
    database_username: str = Field(
        description="Database username (from DATABASE_USERNAME env var)",
        validation_alias="DATABASE_USERNAME",
    )
    database_password: str = Field(
        description="Database password (from DATABASE_PASSWORD env var)",
        validation_alias="DATABASE_PASSWORD",
    )

    @property
    def database_url(self) -> str:
        """Construct database URL from hardcoded host/port + env-sourced credentials."""
        return f"postgresql://{self.database_username}:{self.database_password}@{self.database_host}:{self.database_port}/{self.database_name}"

    # Celery / Valkey
    celery_broker_url: str = Field(default="redis://valkey:6379/0")
    celery_result_backend: str = Field(default="redis://valkey:6379/1")
    celery_worker_concurrency: int = Field(default=1, ge=1)
    celery_log_level: Literal["debug", "info", "warning", "error", "critical"] = "info"
    log_format: Literal["json", "console"] = "json"
    source_playlist_cache_ttl_seconds: int = Field(default=300, ge=1)
    explore_cache_ttl_seconds: int = Field(default=900, ge=1)
    max_bulk_operations: int = Field(default=100, ge=1, le=1000)

    # YouTube Music
    ytmusic_auth: str = ""
    yt_dlp_timeout: int = 300

    # User-editable settings (persisted in config table, merged at startup)
    plex_host: str = ""
    plex_token: str = ""
    jellyfin_server_url: str = ""
    jellyfin_api_key: str = ""
    jellyfin_user_id: str = ""

    # Auth (Plex SSO)
    require_auth: bool = False
    plex_client_id: str = ""
    app_url: str = "http://localhost:8000"
    secret_key: str = ""
    session_ttl_hours: int = Field(default=168, ge=1, le=8760)

    # Network / Reverse proxy (editable via UI, stored in config table)
    behind_proxy: bool = False
    trusted_proxies: list[str] = Field(default_factory=list)

    @field_validator("celery_log_level", "log_format", mode="before")
    @classmethod
    def _lower_on_reading(cls, value: Any) -> Any:
        if isinstance(value, str):
            return value.lower()
        return value

    @field_validator("app_url")
    @classmethod
    def _validate_app_url(cls, value: str) -> str:
        if not value.startswith(("http://", "https://")):
            raise ValueError("APP_URL must be an absolute http(s) URL")
        return value

    @field_validator("trusted_proxies", mode="before")
    @classmethod
    def _parse_trusted_proxies(cls, value: Any) -> Any:
        """Accept a comma-separated list or a JSON array of CIDR ranges."""
        if not isinstance(value, str):
            return value
        raw = value.strip()
        if not raw:
            return []
        if raw.startswith("["):
            try:
                parsed = json.loads(raw)
            except ValueError:
                logger.warning("trusted_proxies is not valid JSON — falling back to a plain list")
            else:
                return [str(item).strip() for item in parsed if str(item).strip()]
        return [part.strip() for part in raw.split(",") if part.strip()]

    @model_validator(mode="after")
    def _validate_secret_key(self) -> Self:
        # A present-but-too-short key is always rejected. An *empty* key is
        # allowed here: the working key may still come from the config table,
        # which is only read after import, and a fresh production install must
        # be able to boot into the setup wizard to store one. Presence is
        # enforced by the startup gates once DB settings are loaded.
        if self.secret_key and len(self.secret_key) < 32:
            if self.app_env == "production":
                raise ValueError(
                    "APP_ENV=production requires SECRET_KEY to be at least 32 characters. "
                    'Generate one with: python -c "import secrets; print(secrets.token_hex(32))"'
                )
            if self.require_auth:
                raise ValueError(
                    "REQUIRE_AUTH=true requires SECRET_KEY to be at least 32 characters. "
                    'Generate one with: python -c "import secrets; print(secrets.token_hex(32))"'
                )
        return self

    # App
    # Default to development mode unless explicitly set to production via env
    # This allows tests and local dev to run without SECRET_KEY requirements
    app_env: Annotated[str, Field(validation_alias="APP_ENV")] = "development"
    debug: bool = False

    model_config = {
        "env_prefix": "",
        "validate_assignment": True,
        # Unknown keys are ignored rather than rejected: ``.env`` is
        # user-owned and shared with docker-compose, which may carry keys
        # this app does not consume. A stray key must never prevent the
        # service from starting.
        "extra": "ignore",
    }

    def load_overrides(self, overrides: dict[str, Any]) -> None:
        """Apply DB-stored overrides, coercing string values to field types.

        Values read back from the ``config`` table are strings; assignment
        validation (``validate_assignment``) coerces them to the declared
        field type (e.g. ``"300"`` → ``int``) so downstream code never sees a
        str where an int/bool is expected.

        Sensitive config keys are stored encrypted in the DB; they are
        decrypted here before being applied to the settings object.
        """
        from src.app.constants import SENSITIVE_CONFIG_KEYS
        from src.app.services.crypto import DecryptionError, decrypt_boot_token, decrypt_token

        # Apply the secret key first so dependent values (and the startup
        # gate) see the working key; config row order is not guaranteed.
        items = sorted(overrides.items(), key=lambda item: item[0] != "secret_key")

        for key, value in items:
            if key in self.model_fields:
                if key in SENSITIVE_CONFIG_KEYS:
                    try:
                        # The secret key itself is wrapped with the boot
                        # (deployment) key; everything else uses the working
                        # key it holds.
                        if key == "secret_key":
                            value = decrypt_boot_token(value)
                        else:
                            value = decrypt_token(value)
                    except DecryptionError:
                        logger.warning(
                            "Failed to decrypt config key '%s' — falling back to env default. "
                            "Re-enter the value in Settings if needed.",
                            key,
                        )
                        continue
                setattr(self, key, value)


settings = Settings()
