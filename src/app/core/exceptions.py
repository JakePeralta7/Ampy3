"""Custom exception types for Ampy3.

Provides structured error handling to replace bare `except Exception` clauses.
Each exception category represents a class of failures with specific handling.
"""

from __future__ import annotations


class Ampy3Error(Exception):
    """Base exception for all Ampy3-specific errors."""

    pass


# ─── External Service Errors ─────────────────────────────────────────


class ExternalServiceError(Ampy3Error):
    """Base class for errors from external services (Plex, Jellyfin, YTMusic, etc.)."""

    def __init__(self, service: str, message: str, original: Exception | None = None) -> None:
        self.service = service
        self.original = original
        super().__init__(f"{service}: {message}")


class PlexError(ExternalServiceError):
    """Errors from Plex API interactions."""

    def __init__(self, message: str, original: Exception | None = None) -> None:
        super().__init__("Plex", message, original)


class JellyfinError(ExternalServiceError):
    """Errors from Jellyfin API interactions."""

    def __init__(self, message: str, original: Exception | None = None) -> None:
        super().__init__("Jellyfin", message, original)


class YouTubeMusicError(ExternalServiceError):
    """Errors from YouTube Music API interactions."""

    def __init__(self, message: str, original: Exception | None = None) -> None:
        super().__init__("YouTube Music", message, original)


class MusicBrainzError(ExternalServiceError):
    """Errors from MusicBrainz API interactions."""

    def __init__(self, message: str, original: Exception | None = None) -> None:
        super().__init__("MusicBrainz", message, original)


class DeezerError(ExternalServiceError):
    """Errors from Deezer API interactions."""

    def __init__(self, message: str, original: Exception | None = None) -> None:
        super().__init__("Deezer", message, original)


# ─── Authentication & Authorization Errors ───────────────────────────


class AuthError(Ampy3Error):
    """Base class for authentication/authorization errors."""

    pass


class PlexAuthError(AuthError):
    """Plex authentication failures (PIN exchange, token validation, etc.)."""

    def __init__(self, message: str, original: Exception | None = None) -> None:
        self.original = original
        super().__init__(f"Plex auth: {message}")


class SessionError(AuthError):
    """Session validation/creation failures."""

    def __init__(self, message: str, original: Exception | None = None) -> None:
        self.original = original
        super().__init__(f"Session: {message}")


# ─── Configuration Errors ────────────────────────────────────────────


class ConfigurationError(Ampy3Error):
    """Configuration-related errors (missing, invalid, or malformed config)."""

    pass


class ConfigValidationError(ConfigurationError):
    """Configuration validation failed."""

    pass


class ConfigDecryptionError(ConfigurationError):
    """Failed to decrypt encrypted configuration value."""

    def __init__(self, key: str, original: Exception | None = None) -> None:
        self.key = key
        self.original = original
        super().__init__(f"Failed to decrypt config '{key}'")


class MissingConfigError(ConfigurationError):
    """Required configuration is missing."""

    def __init__(self, key: str) -> None:
        self.key = key
        super().__init__(f"Missing required config: {key}")


# ─── Data & Validation Errors ───────────────────────────────────────


class ValidationError(Ampy3Error):
    """Data validation failures."""

    pass


class MatchRuleValidationError(ValidationError):
    """Match rule YAML validation failed."""

    def __init__(self, message: str, original: Exception | None = None) -> None:
        self.original = original
        super().__init__(f"Match rule validation: {message}")


class SyncDataError(Ampy3Error):
    """Sync-related data errors."""

    pass


# ─── Database & Storage Errors ──────────────────────────────────────


class DatabaseError(Ampy3Error):
    """Database operation failures."""

    def __init__(self, message: str, original: Exception | None = None) -> None:
        self.original = original
        super().__init__(f"Database: {message}")


class CacheError(Ampy3Error):
    """Cache/Valkey operation failures."""

    def __init__(self, message: str, original: Exception | None = None) -> None:
        self.original = original
        super().__init__(f"Cache: {message}")


# ─── Task & Scheduler Errors ────────────────────────────────────────


class SchedulerError(Ampy3Error):
    """APScheduler-related errors."""

    def __init__(self, message: str, original: Exception | None = None) -> None:
        self.original = original
        super().__init__(f"Scheduler: {message}")


class TaskError(Ampy3Error):
    """Background task execution errors."""

    def __init__(self, message: str, original: Exception | None = None) -> None:
        self.original = original
        super().__init__(f"Task: {message}")


# ─── Target Management Errors ────────────────────────────────────────


class TargetError(Ampy3Error):
    """Sync target management errors."""

    def __init__(self, target_id: str, message: str, original: Exception | None = None) -> None:
        self.target_id = target_id
        self.original = original
        super().__init__(f"Target '{target_id}': {message}")


class TargetConnectionError(TargetError):
    """Failed to connect to a sync target."""

    pass


class TargetOperationError(TargetError):
    """Failed to perform an operation on a sync target."""

    pass


# ─── Helper Functions ───────────────────────────────────────────────


def wrap_external_error(service: str, exc: Exception) -> ExternalServiceError:
    """Wrap an arbitrary exception into the appropriate ExternalServiceError."""
    service_lower = service.lower()
    if service_lower == "plex":
        return PlexError(str(exc), exc)
    if service_lower == "jellyfin":
        return JellyfinError(str(exc), exc)
    if service_lower in ("youtube music", "ytmusic", "youtube"):
        return YouTubeMusicError(str(exc), exc)
    if service_lower == "musicbrainz":
        return MusicBrainzError(str(exc), exc)
    if service_lower == "deezer":
        return DeezerError(str(exc), exc)
    return ExternalServiceError(service, str(exc), exc)


def is_retryable_error(exc: Exception) -> bool:
    """Determine if an error is retryable (transient network issues, etc.)."""
    import httpx

    # Network-related errors are typically retryable
    retryable_types = (
        ConnectionError,
        TimeoutError,
        httpx.RequestError,
    )
    if isinstance(exc, retryable_types):
        return True
    # Check wrapped original
    if hasattr(exc, "original") and exc.original is not None:
        return is_retryable_error(exc.original)
    return False
