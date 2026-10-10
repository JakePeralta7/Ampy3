"""Jellyfin sync target."""

from __future__ import annotations

import json
import logging
import re
from typing import Any, ClassVar

import httpx

from src.app.constants import TARGET_JELLYFIN
from src.app.core.matching import normalize
from src.app.core.targets.base import BaseTarget
from src.app.core.targets.factory import TargetFactory, target_factory
from src.app.core.targets.registry import TargetRegistry
from src.app.core.targets.search import SearchStrategy, UnifiedSearchStrategy
from src.app.core.urls import (
    InvalidServerUrlError,
    source_id_from_url,
    validate_server_url,
)

logger = logging.getLogger(__name__)


def _normalize_search_query(query: str) -> str:
    """Strip characters that cause Jellyfin Lucene search issues."""
    query = re.sub(r"\(.*?\)", "", query)
    query = re.sub(r"\[.*?\]", "", query)
    query = re.sub(r"\{.*?\}", "", query)
    query = re.sub(r"[(){}\[\]]", "", query)
    query = re.sub(r"\.{2,}", " ", query)
    query = re.sub(r"^[.\u2026]+", "", query)
    query = query.replace(",", " ")
    return normalize(query, strip_quotes=True, collapse_whitespace=True)


class JellyfinTarget(BaseTarget):
    """Jellyfin sync target."""

    target_id: ClassVar[str] = TARGET_JELLYFIN
    display_name: ClassVar[str] = TARGET_JELLYFIN

    search_strategy: ClassVar[SearchStrategy] = UnifiedSearchStrategy()

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

    # ── Helpers ──────────────────────────────────────────────────

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

    def _playlist_out(self, item: dict[str, Any]) -> dict[str, Any]:
        pid = str(item.get("Id", ""))
        return {
            "title": item.get("Name", ""),
            "rating_key": pid,
            "playlist_id": pid,
            "summary": item.get("Overview", "") or "",
            "track_count": int(item.get("ChildCount") or 0),
        }

    async def client_url(self, playlist_id: str) -> str:
        """Return the Jellyfin web-app URL that opens the given playlist item.

        Jellyfin web is a hash-routed SPA served from the server base URL.
        The item details page is reached via ``/web/index.html#/details?id={itemId}``.
        """
        return f"{self._base_url}/web/index.html#/details?id={playlist_id}"

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

    # ── Playlist operations ──────────────────────────────────────

    async def search_playlists(self, query: str) -> list[dict[str, Any]]:
        try:
            items = await self._get_all_items(
                f"/Users/{self._user_id}/Items",
                {
                    "IncludeItemTypes": "Playlist",
                    "Recursive": "true",
                    "Fields": "ChildCount,Overview",
                    "SortBy": "SortName",
                },
            )
            out = [self._playlist_out(item) for item in items]
            if not query:
                return out
            q = query.lower().strip()
            return [p for p in out if q in str(p.get("title", "")).lower()]
        except Exception as exc:
            logger.error("Failed to search Jellyfin playlists: %s", exc)
            return []

    async def get_playlist_details(self, playlist_id: str) -> dict[str, Any] | None:
        try:
            resp = await self.client.get(f"/Users/{self._user_id}/Items/{playlist_id}")
            resp.raise_for_status()
            item = resp.json()
            return self._playlist_out(item)
        except Exception as exc:
            logger.error("Failed to get Jellyfin playlist %s: %s", playlist_id, exc)
            return None

    async def create_playlist(
        self,
        title: str,
        items: list[dict[str, Any]],
        custom_metadata: dict[str, Any] | None = None,
    ) -> str | None:
        ids = [str(i.get("item_id") or i.get("id") or "") for i in items]
        ids = [i for i in ids if i]
        try:
            params = {
                "Name": title,
                "UserId": self._user_id,
                "MediaType": "Audio",
            }
            if ids:
                params["Ids"] = ",".join(ids)
            resp = await self.client.post("/Playlists", params=params)
            resp.raise_for_status()
            data = resp.json()
            playlist_id = data.get("Id")
            if (not isinstance(playlist_id, str) or not playlist_id) and isinstance(
                data.get("ItemId"), str
            ):
                playlist_id = data["ItemId"]
            if not isinstance(playlist_id, str) or not playlist_id:
                logger.error("Jellyfin playlist creation response missing Id: %s", data)
                return None

            # CreatePlaylistDto has no Overview field: write metadata via a
            # follow-up item update so get_playlist_by_source_id can locate
            # this playlist by its source identity later.
            if custom_metadata:
                try:
                    meta_resp = await self.client.post(
                        f"/Items/{playlist_id}",
                        json={"Overview": json.dumps(custom_metadata, default=str)},
                    )
                    meta_resp.raise_for_status()
                except Exception as exc:
                    logger.warning(
                        "Created Jellyfin playlist %s but failed to store metadata: %s",
                        playlist_id,
                        exc,
                    )

            return playlist_id
        except Exception as exc:
            logger.error("Failed to create Jellyfin playlist '%s': %s", title, exc)
            return None

    async def update_playlist(self, playlist_id: str, items: list[dict[str, Any]]) -> bool:
        try:
            current = await self.get_items_in_playlist(playlist_id)
            existing_ids = [str(i.get("item_id")) for i in current if i.get("item_id")]
            if existing_ids:
                removed = await self.remove_items_from_playlist(playlist_id, existing_ids)
                if removed < len(existing_ids):
                    logger.error(
                        "Jellyfin playlist %s: only removed %d/%d stale items",
                        playlist_id,
                        removed,
                        len(existing_ids),
                    )
                    return False

            desired_ids = [str(i.get("item_id") or i.get("id") or "") for i in items]
            desired_ids = [i for i in desired_ids if i]
            if desired_ids:
                added = await self.add_items_to_playlist(playlist_id, desired_ids)
                if added < len(desired_ids):
                    logger.error(
                        "Jellyfin playlist %s: only added %d/%d desired items",
                        playlist_id,
                        added,
                        len(desired_ids),
                    )
                    return False
            return True
        except Exception as exc:
            logger.error("Failed updating Jellyfin playlist %s: %s", playlist_id, exc)
            return False

    async def delete_playlist(self, playlist_id: str) -> bool:
        try:
            resp = await self.client.delete(f"/Items/{playlist_id}")
            resp.raise_for_status()
            return True
        except Exception as exc:
            logger.error("Failed deleting Jellyfin playlist %s: %s", playlist_id, exc)
            return False

    async def get_items_in_playlist(self, playlist_id: str) -> list[dict[str, Any]]:
        try:
            items = await self._get_all_items(
                f"/Playlists/{playlist_id}/Items",
                {
                    "UserId": self._user_id,
                    "Fields": "RunTimeTicks,ArtistItems,Album,PlaylistItemId",
                },
            )
            return [self._track_out(item) for item in items]
        except Exception as exc:
            logger.error("Failed to list Jellyfin playlist items for %s: %s", playlist_id, exc)
            return []

    # ── Playlist lookup ──────────────────────────────────────────

    async def get_playlist_by_name(self, name: str) -> dict[str, Any] | None:
        results = await self.search_playlists(name)
        target = name.lower().strip()
        for playlist in results:
            if str(playlist.get("title", "")).lower().strip() == target:
                return playlist
        return None

    async def get_playlist_by_source_id(self, source_id: str) -> dict[str, Any] | None:
        """Find a playlist by the exact source id stored in its metadata.

        Every Ampy3-created playlist stores ``{"source_url": ...,
        "sync_id": ...}`` (and, going forward, ``source_id``) as a JSON
        ``Overview`` string. We compare exact values rather than substring
        matching so one id can never match a foreign playlist's metadata.
        """
        if not source_id:
            return None
        source_id = str(source_id).strip()
        results = await self.search_playlists("")
        for playlist in results:
            meta = self._meta_from_overview(playlist)
            if meta.get("source_id") == source_id:
                return playlist
            url = meta.get("source_url")
            if isinstance(url, str) and self._source_id_from_url(url) == source_id:
                return playlist
        return None

    @staticmethod
    def _meta_from_overview(playlist: dict[str, Any]) -> dict[str, Any]:
        summary = str(playlist.get("summary") or "")
        if not summary:
            return {}
        try:
            data = json.loads(summary)
        except ValueError, TypeError:
            return {}
        return data if isinstance(data, dict) else {}

    @staticmethod
    def _source_id_from_url(url: str) -> str:
        return source_id_from_url(url)

    # ── Item management ──────────────────────────────────────────

    async def add_items_to_playlist(self, playlist_id: str, item_ids: list[str]) -> int:
        if not item_ids:
            return 0
        ids = [str(i) for i in item_ids if i]
        try:
            resp = await self.client.post(
                f"/Playlists/{playlist_id}/Items",
                params={
                    "UserId": self._user_id,
                    "Ids": ",".join(ids),
                },
            )
            resp.raise_for_status()
            return len(ids)
        except Exception as exc:
            logger.error("Failed adding items to Jellyfin playlist %s: %s", playlist_id, exc)
            return 0

    async def remove_items_from_playlist(self, playlist_id: str, item_ids: list[str]) -> int:
        if not item_ids:
            return 0
        items = await self.get_items_in_playlist(playlist_id)
        remove_set = {str(i) for i in item_ids}
        entry_ids = [
            str(item.get("playlist_item_id"))
            for item in items
            if str(item.get("item_id")) in remove_set and item.get("playlist_item_id")
        ]
        if not entry_ids:
            return 0
        try:
            resp = await self.client.delete(
                f"/Playlists/{playlist_id}/Items",
                params={
                    "UserId": self._user_id,
                    "EntryIds": ",".join(entry_ids),
                },
            )
            resp.raise_for_status()
            return len(entry_ids)
        except Exception as exc:
            logger.error("Failed removing items from Jellyfin playlist %s: %s", playlist_id, exc)
            return 0

    # ── Library search ───────────────────────────────────────────

    async def _do_search(self, criteria) -> list[dict[str, Any]]:
        """Execute the actual Jellyfin search against the API.

        This is called by UnifiedSearchStrategy to avoid infinite recursion.
        """
        search_term = criteria.title or criteria.artist or criteria.album or criteria.genre
        search_term = _normalize_search_query(search_term) if search_term else ""
        params = {
            "IncludeItemTypes": "Audio",
            "Recursive": "true",
            "Limit": "200",
            "Fields": "RunTimeTicks,ArtistItems,Album,ProviderIds",
        }
        if search_term:
            params["SearchTerm"] = search_term

        try:
            resp = await self.client.get(f"/Users/{self._user_id}/Items", params=params)
            resp.raise_for_status()
            items = [self._track_out(item) for item in resp.json().get("Items", [])]
        except Exception as exc:
            logger.error("Failed searching Jellyfin library: %s", exc)
            return []

        n_title = normalize(criteria.title)
        n_artist = normalize(criteria.artist)
        n_album = normalize(criteria.album)

        def _matches(item: dict[str, Any]) -> bool:
            if n_title and n_title not in normalize(str(item.get("title", ""))):
                return False
            if n_artist and n_artist not in normalize(str(item.get("artist_name", ""))):
                return False
            return not (n_album and n_album not in normalize(str(item.get("album_name", ""))))

        return [i for i in items if _matches(i)]

    async def search_library(
        self,
        title: str = "",
        artist: str = "",
        genre: str = "",
        album: str = "",
    ) -> list[dict[str, Any]]:
        """Search the Jellyfin music library using the configured search strategy."""
        return await self._search_via_strategy(title=title, artist=artist, genre=genre, album=album)

    async def _search_by_title_artist_album(
        self,
        title: str,
        artist: str,
        album: str = "",
        genre: str = "",
    ) -> list[dict[str, Any]]:
        """Jellyfin uses unified search - delegate to _do_search."""
        from src.app.core.targets.search import SearchCriteria

        criteria = SearchCriteria(title=title, artist=artist, album=album, genre=genre)
        return await self._do_search(criteria)

    async def _search_by_genre(self, genre: str) -> list[dict[str, Any]]:
        """Jellyfin uses unified search - delegate to _do_search."""
        from src.app.core.targets.search import SearchCriteria

        criteria = SearchCriteria(genre=genre)
        return await self._do_search(criteria)

    async def search_artist_tracks(self, artist: str, genre: str = "") -> list[dict[str, Any]]:
        from src.app.core.targets.search import SearchCriteria

        criteria = SearchCriteria(artist=artist, genre=genre)
        return await self._do_search(criteria)

    async def search_title_only(self, title: str) -> list[dict[str, Any]]:
        from src.app.core.targets.search import SearchCriteria

        criteria = SearchCriteria(title=title)
        return await self._do_search(criteria)

    # ── Connection test ─────────────────────────────────────────

    async def test_connection(self) -> None:
        """Verify connectivity with the Jellyfin server."""
        resp = await self.client.get(f"/Users/{self._user_id}")
        resp.raise_for_status()

    # ── Lifecycle ────────────────────────────────────────────────

    async def close(self) -> None:
        if self._client is not None:
            await self._client.aclose()
            self._client = None


@target_factory(TARGET_JELLYFIN, "Jellyfin")
class JellyfinTargetFactory(TargetFactory):
    REQUIRED_KEYS = ["jellyfin_server_url", "jellyfin_api_key", "jellyfin_user_id"]
    SENSITIVE_KEYS = {"jellyfin_api_key"}
    target_class = JellyfinTarget

    @classmethod
    def _build_kwargs(cls, config: dict[str, str]) -> dict[str, Any]:
        return {
            "api_key": config["jellyfin_api_key"],
            "base_url": config["jellyfin_server_url"],
            "user_id": config["jellyfin_user_id"],
        }
