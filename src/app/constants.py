"""Platform identifiers and shared constants."""

from datetime import timedelta

# Target platform IDs (case-sensitive — must match @register_target values)
TARGET_PLEX = "Plex"
TARGET_JELLYFIN = "Jellyfin"

# Source platform IDs
SOURCE_YOUTUBE_MUSIC = "youtube_music"
SOURCE_YOUTUBE_MUSIC_DISPLAY = "YouTube Music"
SOURCE_DEEZER = "deezer"
SOURCE_DEEZER_DISPLAY = "Deezer"

# Defaults
DEFAULT_TARGET = TARGET_PLEX
DEFAULT_SOURCE = SOURCE_YOUTUBE_MUSIC

# Schedule interval → timedelta mapping (shared by scheduler + pipeline)
INTERVAL_DELTAS: dict[str, timedelta] = {
    "every_6h": timedelta(hours=6),
    "every_12h": timedelta(hours=12),
    "every_24h": timedelta(hours=24),
    "daily": timedelta(days=1),
    "weekly": timedelta(weeks=1),
}

# Marker used for one-off (ad-hoc) syncs. It is deliberately not a member of
# ScheduleIntervalEnum: recurring schedules can never carry it. The idempotency
# unique index is scoped to rows with this marker so a client key stays scoped
# to the request that created it.
AD_HOC_INTERVAL = "once"

# Config keys that contain sensitive credentials and should be encrypted at rest
SENSITIVE_CONFIG_KEYS: frozenset[str] = frozenset(
    {
        "plex_token",
        "jellyfin_api_key",
        "owner_plex_token",
        "ytmusic_auth",
        "secret_key",
        "database_username",
        "database_password",
    }
)
