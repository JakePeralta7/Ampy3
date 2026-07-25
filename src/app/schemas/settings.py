"""Settings request/response schemas."""

from pydantic import BaseModel


class SettingsUpdate(BaseModel):
    plex_host: str | None = None
    plex_token: str | None = None
    jellyfin_server_url: str | None = None
    jellyfin_api_key: str | None = None
    jellyfin_user_id: str | None = None
    ollama_host: str | None = None
    ollama_model: str | None = None
    ollama_timeout: int | None = None
    yt_dlp_cookies: str | None = None
    yt_dlp_timeout: int | None = None


class SettingsOut(BaseModel):
    plex_host: str
    plex_token: str
    jellyfin_server_url: str
    jellyfin_api_key: str
    jellyfin_user_id: str
    ollama_host: str
    ollama_model: str
    ollama_timeout: int
    yt_dlp_cookies: str
    yt_dlp_timeout: int
