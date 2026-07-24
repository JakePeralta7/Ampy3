from typing import Any

from pydantic import Field
from pydantic_settings import BaseSettings


class Settings(BaseSettings):
    # Database
    database_url: str = Field(
        default="postgresql://ampy3:ampy3@localhost:5432/ampy3",
        description="PostgreSQL database URL"
    )

    # Celery / Valkey
    celery_broker_url: str = Field(default="redis://valkey:6379/0")
    celery_result_backend: str = Field(default="redis://valkey:6379/1")
    celery_worker_concurrency: int = Field(default=1, ge=1)
    celery_log_level: str = Field(default="info")

    # yt-dlp
    yt_dlp_cookies: str = ""
    yt_dlp_timeout: int = 300

    # Ollama (external)
    ollama_host: str = "http://localhost:11434"
    ollama_model: str = "gemma4-e4b-128:latest"
    ollama_timeout: int = 120

    # Auth (Plex SSO)
    require_auth: bool = False
    plex_client_id: str = ""
    app_url: str = "http://localhost:8000"
    secret_key: str = ""
    session_ttl_hours: int = 168

    # App
    app_env: str = "development"
    debug: bool = False

    model_config = {"env_prefix": ""}

    def load_overrides(self, overrides: dict[str, Any]) -> None:
        for key, value in overrides.items():
            if key in self.model_fields:
                setattr(self, key, value)


settings = Settings()
