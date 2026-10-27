"""Jellyfin library search operations."""

import logging
import re
from typing import Any

from src.app.core.matching import normalize
from src.app.core.targets.jellyfin.client import JellyfinClient
from src.app.core.targets.search import SearchStrategy, UnifiedSearchStrategy

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


class JellyfinSearchManager:
    """Handles all library search operations for Jellyfin."""

    search_strategy: SearchStrategy = UnifiedSearchStrategy()

    def __init__(self, client: JellyfinClient) -> None:
        self._client = client

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
            resp = await self._client.client.get(
                f"/Users/{self._client.user_id}/Items", params=params
            )
            resp.raise_for_status()
            items = [self._client._track_out(item) for item in resp.json().get("Items", [])]
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

    async def _search_via_strategy(
        self,
        title: str = "",
        artist: str = "",
        genre: str = "",
        album: str = "",
    ) -> list[dict[str, Any]]:
        """Dispatch to the configured search strategy.

        The strategy calls back into this manager (``_do_search``), which is
        why the manager is passed as the strategy's ``target``.
        """
        from src.app.core.targets.search import SearchCriteria

        criteria = SearchCriteria(title=title, artist=artist, genre=genre, album=album)
        candidates = await self.search_strategy.search(self, criteria)
        return [candidate.to_dict() for candidate in candidates]

    # Abstract methods required by BaseTarget (delegated to _do_search)
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
