"""Jellyfin HTTP client management and connection handling."""

import logging
from typing import Any

import httpx

from src.app.core.urls import InvalidServerUrlError, validate_server_url

logger = logging.getLogger(__name__)


class JellyfinClient:
    """Manages the Jellyfin HTTP client and connection state."""

    def __init__(self, api_key: str, base_url: str, user_id: str) -> None:
        try:
            validate_server_url(base_url, field="jellyfin_server_url")
        except InvalidServerUrlError as exc:
            raise ValueError(f"Invalid jellyfin_server_url: {exc}") from exc
        self._api_key = api_key
        self._base_url = base_url.rstrip("/")
        self._user_id = user_id
        self._client: httpx.AsyncClient | None = None

    @property
    def client(self) -> httpx.AsyncClient:
        """Return the lazily-created httpx.AsyncClient.

        The client is created once per target instance and reused for its
        lifetime. Safe because workers run on a single persistent event loop
        (see ``worker.session.run_async``) and FastAPI is single-loop.
        """
        if self._client is None:
            self._client = httpx.AsyncClient(base_url=self._base_url, timeout=15.0)
            self._client.headers.update(
                {
                    "Authorization": f'MediaBrowser Token="{self._api_key}"',
                    "Content-Type": "application/json",
                }
            )
        return self._client

    @property
    def base_url(self) -> str:
        """Return the base URL."""
        return self._base_url

    @property
    def user_id(self) -> str:
        """Return the user ID."""
        return self._user_id

    @property
    def api_key(self) -> str:
        """Return the API key."""
        return self._api_key

    # ─── Helpers ──────────────────────────────────────────────────

    async def _get_all_items(self, path: str, params: dict[str, Any]) -> list[dict[str, Any]]:
        """Fetch every page of a Jellyfin Items response using StartIndex paging.

        Without this, playlists larger than the API ``Limit`` (or a hardcoded
        cap like 1000) would be silently truncated. ``limit=200`` was found in
        working set as truncation risk for large libraries.

        Safety limits prevent infinite loops if the server returns an incorrect
        TotalRecordCount or never empties the response.
        """
        page_size = 500
        max_pages = 100
        max_total_items = 50_000
        all_items: list[dict[str, Any]] = []
        start_index = 0
        pages_fetched = 0
        while True:
            if pages_fetched >= max_pages:
                logger.warning(
                    "Jellyfin pagination hit max_pages=%d for %s, stopping",
                    max_pages,
                    path,
                )
                break
            if len(all_items) >= max_total_items:
                logger.warning(
                    "Jellyfin pagination hit max_total_items=%d for %s, stopping",
                    max_total_items,
                    path,
                )
                break
            page_params = dict(params)
            page_params["Limit"] = str(page_size)
            page_params["StartIndex"] = str(start_index)
            resp = await self.client.get(path, params=page_params)
            resp.raise_for_status()
            data = resp.json()
            items = data.get("Items", [])
            all_items.extend(items)
            total = int(data.get("TotalRecordCount") or 0)
            start_index += len(items)
            pages_fetched += 1
            if start_index >= total or not items:
                break
        return all_items

    @staticmethod
    def _to_duration_seconds(runtime_ticks: int | None) -> int:
        if not runtime_ticks:
            return 0
        return int(runtime_ticks / 10_000_000)

    @staticmethod
    def _pick_artist(item: dict[str, Any]) -> str:
        artists = item.get("ArtistItems") or []
        if artists and isinstance(artists, list):
            first = artists[0] or {}
            name = first.get("Name")
            if isinstance(name, str):
                return name
        artist = item.get("Artists") or []
        if artist and isinstance(artist, list) and isinstance(artist[0], str):
            return artist[0]
        return ""

    def _track_out(self, item: dict[str, Any]) -> dict[str, Any]:
        item_id = str(item.get("Id", ""))
        provider_ids = item.get("ProviderIds") or {}
        return {
            "item_id": item_id,
            "title": item.get("Name", "") or "",
            "artist_name": self._pick_artist(item),
            "album_name": item.get("Album", "") or "",
            "duration": self._to_duration_seconds(item.get("RunTimeTicks")),
            "duration_ms": int((item.get("RunTimeTicks") or 0) / 10_000),
            "playlist_item_id": item.get("PlaylistItemId"),
            "mbid": provider_ids.get("MusicBrainzRecording"),
            "artist_mbid": provider_ids.get("MusicBrainzArtist"),
            "album_mbid": provider_ids.get("MusicBrainzAlbum"),
        }

    def _playlist_out(self, item: dict[str, Any]) -> dict[str, Any]:
        pid = str(item.get("Id", ""))
        return {
            "title": item.get("Name", ""),
            "rating_key": pid,
            "playlist_id": pid,
            "summary": item.get("Overview", "") or "",
            "track_count": int(item.get("ChildCount") or 0),
        }

    # ─── Connection test ─────────────────────────────────────────

    async def test_connection(self) -> None:
        """Verify connectivity with the Jellyfin server."""
        resp = await self.client.get(f"/Users/{self._user_id}")
        resp.raise_for_status()

    # ─── Lifecycle ────────────────────────────────────────────────

    async def close(self) -> None:
        if self._client is not None:
            await self._client.aclose()
            self._client = None
