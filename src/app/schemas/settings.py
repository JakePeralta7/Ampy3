"""Settings request/response schemas."""

from pydantic import BaseModel


class SettingsUpdate(BaseModel):
    # Credentials (Sources & Targets)
    plex_host: str | None = None
    plex_token: str | None = None
    jellyfin_server_url: str | None = None
    jellyfin_api_key: str | None = None
    jellyfin_user_id: str | None = None
    ytmusic_auth: str | None = None

    # Infrastructure
    yt_dlp_timeout: int | None = None
    celery_broker_url: str | None = None
    celery_worker_concurrency: int | None = None
    celery_log_level: str | None = None
    log_format: str | None = None
    source_playlist_cache_ttl_seconds: int | None = None
    explore_cache_ttl_seconds: int | None = None
    session_ttl_hours: int | None = None

    # Network
    behind_proxy: bool | None = None
    trusted_proxies: list[str] | None = None

    # Security & Server
    require_auth: bool | None = None
    app_url: str | None = None
    plex_client_id: str | None = None


class SettingsOut(BaseModel):
    # Credentials
    plex_host: str
    plex_token_set: bool
    jellyfin_server_url: str
    jellyfin_api_key_set: bool
    jellyfin_user_id: str
    ytmusic_auth_set: bool

    # Infrastructure
    yt_dlp_timeout: int
    celery_broker_url: str
    celery_worker_concurrency: int
    celery_log_level: str
    log_format: str
    source_playlist_cache_ttl_seconds: int
    explore_cache_ttl_seconds: int
    session_ttl_hours: int

    # Network
    behind_proxy: bool
    trusted_proxies: list[str]

    # Security & Server
    require_auth: bool
    app_url: str
    plex_client_id: str
    secret_key_set: bool
