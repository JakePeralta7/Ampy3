"""Plex API error categorization and handling."""

from dataclasses import dataclass
from enum import StrEnum


class PlexErrorType(StrEnum):
    """Categorization of Plex API errors."""

    NETWORK_ERROR = "network_error"  # Connection refused, timeout
    AUTH_ERROR = "auth_error"  # 401, 403, invalid token
    NOT_FOUND = "not_found"  # 404, playlist/section doesn't exist
    RATE_LIMITED = "rate_limited"  # 429
    SERVER_ERROR = "server_error"  # 5xx
    UNKNOWN = "unknown"  # Other errors


@dataclass
class PlexErrorInfo:
    """Information about a Plex error."""

    error_type: PlexErrorType
    message: str
    is_transient: bool
    retry_count: int = 0
    max_retries: int = 3

    def __str__(self) -> str:
        return f"{self.error_type}: {self.message}"


def categorize_plex_error(error: Exception) -> PlexErrorInfo:
    """Categorize a Plex error and determine retry strategy.

    Args:
        error: The exception from Plex API

    Returns:
        PlexErrorInfo with error type and retry strategy
    """
    import httpx

    error_msg = str(error)

    # Network errors
    if isinstance(error, (httpx.ConnectError, ConnectionError, httpx.RemoteProtocolError)):
        return PlexErrorInfo(
            error_type=PlexErrorType.NETWORK_ERROR,
            message=f"Connection error: {error_msg}",
            is_transient=True,
        )

    if isinstance(error, httpx.TimeoutException):
        return PlexErrorInfo(
            error_type=PlexErrorType.NETWORK_ERROR,
            message=f"Request timeout: {error_msg}",
            is_transient=True,
        )

    # HTTP status errors
    if isinstance(error, httpx.HTTPStatusError):
        status_code = error.response.status_code

        # Auth errors (401, 403)
        if status_code in (401, 403):
            return PlexErrorInfo(
                error_type=PlexErrorType.AUTH_ERROR,
                message=f"Authentication failed ({status_code}): {error_msg}",
                is_transient=False,
            )

        # Not found (404)
        if status_code == 404:
            return PlexErrorInfo(
                error_type=PlexErrorType.NOT_FOUND,
                message=f"Resource not found ({status_code}): {error_msg}",
                is_transient=False,
            )

        # Rate limited (429)
        if status_code == 429:
            return PlexErrorInfo(
                error_type=PlexErrorType.RATE_LIMITED,
                message=f"Rate limited ({status_code}): {error_msg}",
                is_transient=True,
            )

        # Server errors (5xx)
        if status_code >= 500:
            return PlexErrorInfo(
                error_type=PlexErrorType.SERVER_ERROR,
                message=f"Server error ({status_code}): {error_msg}",
                is_transient=True,
            )

    # Unknown error
    return PlexErrorInfo(
        error_type=PlexErrorType.UNKNOWN,
        message=f"Unknown error: {error_msg}",
        is_transient=False,
    )
