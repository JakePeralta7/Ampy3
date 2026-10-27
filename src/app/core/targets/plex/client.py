"""Plex HTTP client management and connection handling."""

import logging
import xml.etree.ElementTree as ET
from typing import Any

import httpx

from src.app.core.targets.plex_errors import PlexErrorInfo, categorize_plex_error
from src.app.core.urls import InvalidServerUrlError, validate_server_url

logger = logging.getLogger(__name__)


class PlexClient:
    """Manages the Plex HTTP client and connection state."""

    def __init__(self, token: str, base_url: str) -> None:
        try:
            validate_server_url(base_url, field="plex_host")
        except InvalidServerUrlError as exc:
            raise ValueError(f"Invalid plex_host: {exc}") from exc
        self._token = token
        self._base_url = base_url.rstrip("/")
        self._client: httpx.AsyncClient | None = None
        self._machine_identifier: str | None = None

    @property
    def client(self) -> httpx.AsyncClient:
        """Return the lazily-created httpx.AsyncClient.

        The client is created once per target instance and reused for its
        lifetime. Safe because workers run on a single persistent event loop
        (see ``worker.session.run_async``) and FastAPI is single-loop.
        """
        if self._client is None:
            self._client = httpx.AsyncClient(base_url=self._base_url, timeout=10.0)
            self._client.headers.update(
                {
                    "X-Plex-Token": self._token,
                    "Content-Type": "application/json",
                }
            )
        return self._client

    @property
    def base_url(self) -> str:
        """Return the base URL."""
        return self._base_url

    @property
    def machine_identifier(self) -> str | None:
        """Return cached machine identifier."""
        return self._machine_identifier

    async def _ensure_machine_id(self) -> str:
        """Lazily fetches and caches the Plex server machine identifier."""
        if self._machine_identifier:
            return self._machine_identifier
        response = await self.client.get("/")
        response.raise_for_status()
        root = ET.fromstring(response.text)
        self._machine_identifier = root.get("machineIdentifier", "")
        if not self._machine_identifier:
            raise RuntimeError("Could not determine Plex server machine identifier")
        return self._machine_identifier

    def _rating_key(self, item_id: str) -> str:
        """Extracts the numeric rating_key from an item_id.

        Accepts either '/library/metadata/97300' or bare '97300'.
        """
        if item_id.startswith("/library/metadata/"):
            return item_id.split("/")[-1]
        if item_id.startswith("/"):
            return item_id.rsplit("/", 1)[-1]
        return item_id

    async def test_connection(self) -> None:
        """Verify connectivity with the Plex server.

        Failures are re-raised with the categorized reason so the caller (and
        the user running the connection test) sees *why* the call failed —
        a rejected token reads very differently from an unreachable server.
        """
        try:
            resp = await self.client.get("/library/sections")
            resp.raise_for_status()
        except (httpx.HTTPStatusError, httpx.RequestError) as e:
            info = categorize_plex_error(e)
            raise RuntimeError(f"Plex connection failed ({info.error_type}): {info.message}") from e

    async def close(self) -> None:
        """Closes the underlying httpx client session."""
        if self._client is not None:
            await self._client.aclose()
            self._client = None

    @staticmethod
    def _log_plex_error(operation: str, error: Exception) -> PlexErrorInfo:
        """Log a failed Plex API call with its category and retry guidance."""
        info = categorize_plex_error(error)
        logger.log(
            logging.WARNING if info.is_transient else logging.ERROR,
            "Plex %s failed [%s, %s, max %d retries]: %s",
            operation,
            info.error_type,
            "transient" if info.is_transient else "permanent",
            info.max_retries,
            info.message,
        )
        return info
