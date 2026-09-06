"""Settings request/response schemas."""

from pydantic import BaseModel


class SettingsUpdate(BaseModel):
    plex_host: str | None = None
    plex_token: str | None = None
    jellyfin_server_url: str | None = None
    jellyfin_api_key: str | None = None
    jellyfin_user_id: str | None = None
    ytmusic_auth: str | None = None
    yt_dlp_timeout: int | None = None


class SettingsOut(BaseModel):
    plex_host: str
    plex_token_set: bool
    jellyfin_server_url: str
    jellyfin_api_key_set: bool
    jellyfin_user_id: str
    ytmusic_auth_set: bool
    yt_dlp_timeout: int
