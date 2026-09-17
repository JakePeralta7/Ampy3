from typing import Any, Literal, Self

from pydantic import Field, field_validator, model_validator
from pydantic_settings import BaseSettings


class Settings(BaseSettings):
    # Database
    database_url: str = Field(
        default="postgresql://ampy3:ampy3@localhost:5432/ampy3",
        description="PostgreSQL database URL",
    )

    # Celery / Valkey
    celery_broker_url: str = Field(default="redis://valkey:6379/0")
    celery_result_backend: str = Field(default="redis://valkey:6379/1")
    celery_worker_concurrency: int = Field(default=1, ge=1)
    celery_log_level: Literal["debug", "info", "warning", "error", "critical"] = "info"
    log_format: Literal["json", "console"] = "json"
    source_playlist_cache_ttl_seconds: int = Field(default=300, ge=1)
    explore_cache_ttl_seconds: int = Field(default=900, ge=1)

    # YouTube Music
    ytmusic_auth: str = ""
    yt_dlp_timeout: int = 300

    # Auth (Plex SSO)
    require_auth: bool = False
    plex_client_id: str = ""
    app_url: str = "http://localhost:8000"
    secret_key: str = ""
    session_ttl_hours: int = Field(default=168, ge=1, le=8760)

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

    @model_validator(mode="after")
    def _validate_secret_key(self) -> Self:
        # A short-but-present key is always rejected. An *empty* key is left
        # to the startup gate in main.py (REQUIRE_AUTH=false is fine; failing
        # closed at boot covers REQUIRE_AUTH=true), per the test contract.
        if self.require_auth and self.secret_key and len(self.secret_key) < 32:
            raise ValueError(
                "REQUIRE_AUTH=true requires SECRET_KEY to be set to at least 32 characters. "
                'Generate one with: python -c "import secrets; print(secrets.token_hex(32))"'
            )
        return self

    # App
    app_env: str = "development"
    debug: bool = False

    model_config = {"env_prefix": "", "validate_assignment": True}

    def load_overrides(self, overrides: dict[str, Any]) -> None:
        """Apply DB-stored overrides, coercing string values to field types.

        Values read back from the ``config`` table are strings; assignment
        validation (``validate_assignment``) coerces them to the declared
        field type (e.g. ``"300"`` → ``int``) so downstream code never sees a
        str where an int/bool is expected.
        """
        for key, value in overrides.items():
            if key in self.model_fields:
                setattr(self, key, value)


settings = Settings()
