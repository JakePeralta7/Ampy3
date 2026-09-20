"""Search strategy abstractions for sync targets."""

from __future__ import annotations

from abc import ABC, abstractmethod
from dataclasses import dataclass
from typing import TYPE_CHECKING

if TYPE_CHECKING:
    from src.app.core.matching.candidate import TrackCandidate
    from src.app.core.targets.base import BaseTarget


@dataclass(frozen=True, slots=True)
class SearchCriteria:
    """Normalized search criteria for target library queries."""

    title: str = ""
    artist: str = ""
    album: str = ""
    genre: str = ""


class SearchStrategy(ABC):
    """Abstract base class for target library search strategies.

    Each strategy encapsulates a specific search approach (title+artist+album,
    artist-only expansion, title-only fallback, etc.) and can be composed
    or selected per-target.
    """

    @abstractmethod
    async def search(self, target: BaseTarget, criteria: SearchCriteria) -> list[TrackCandidate]:
        """Execute the search strategy against the target.

        Args:
            target: The sync target to search against.
            criteria: Normalized search criteria.

        Returns:
            List of track candidates matching the criteria.
        """
        ...


class UnifiedSearchStrategy(SearchStrategy):
    """Single-request search strategy (Jellyfin-style).

    Delegates to target._do_search with all criteria at once.
    Suitable for targets with unified search endpoints.
    """

    async def search(self, target: BaseTarget, criteria: SearchCriteria) -> list[TrackCandidate]:
        from src.app.core.matching.candidate import TrackCandidate

        results = await target._do_search(criteria)
        return [
            TrackCandidate(
                item_id=r.get("item_id") or r.get("id", ""),
                title=r.get("title", ""),
                artist_name=r.get("artist_name", ""),
                album_name=r.get("album_name", ""),
                duration_ms=r.get("duration_ms"),
                mbid=r.get("mbid"),
                artist_mbid=r.get("artist_mbid"),
                album_mbid=r.get("album_mbid"),
                raw_data=r,
            )
            for r in results
        ]


class TitleArtistAlbumSearch(SearchStrategy):
    """Plex-style multi-strategy search with artist expansion.

    Tries title+artist+album first, then falls back to artist track expansion
    for better coverage. This mirrors PlexTarget's original search_library logic.
    """

    async def search(self, target: BaseTarget, criteria: SearchCriteria) -> list[TrackCandidate]:
        from src.app.core.matching.candidate import TrackCandidate

        if criteria.title and criteria.artist:
            results = await target._search_by_title_artist_album(
                title=criteria.title,
                artist=criteria.artist,
                album=criteria.album,
                genre=criteria.genre,
            )
            if results:
                return [
                    TrackCandidate(
                        item_id=r.get("item_id") or r.get("id", ""),
                        title=r.get("title", ""),
                        artist_name=r.get("artist_name", ""),
                        album_name=r.get("album_name", ""),
                        duration_ms=r.get("duration_ms"),
                        mbid=r.get("mbid"),
                        artist_mbid=r.get("artist_mbid"),
                        album_mbid=r.get("album_mbid"),
                        raw_data=r,
                    )
                    for r in results
                ]

        if criteria.artist and not criteria.title:
            results = await target.search_artist_tracks(criteria.artist, criteria.genre)
            if results:
                return [
                    TrackCandidate(
                        item_id=r.get("item_id") or r.get("id", ""),
                        title=r.get("title", ""),
                        artist_name=r.get("artist_name", ""),
                        album_name=r.get("album_name", ""),
                        duration_ms=r.get("duration_ms"),
                        mbid=r.get("mbid"),
                        artist_mbid=r.get("artist_mbid"),
                        album_mbid=r.get("album_mbid"),
                        raw_data=r,
                    )
                    for r in results
                ]

        if criteria.title and not criteria.artist:
            results = await target.search_title_only(criteria.title)
            if results:
                return [
                    TrackCandidate(
                        item_id=r.get("item_id") or r.get("id", ""),
                        title=r.get("title", ""),
                        artist_name=r.get("artist_name", ""),
                        album_name=r.get("album_name", ""),
                        duration_ms=r.get("duration_ms"),
                        mbid=r.get("mbid"),
                        artist_mbid=r.get("artist_mbid"),
                        album_mbid=r.get("album_mbid"),
                        raw_data=r,
                    )
                    for r in results
                ]

        if criteria.genre and not criteria.title and not criteria.artist:
            results = await target._search_by_genre(criteria.genre)
            if results:
                return [
                    TrackCandidate(
                        item_id=r.get("item_id") or r.get("id", ""),
                        title=r.get("title", ""),
                        artist_name=r.get("artist_name", ""),
                        album_name=r.get("album_name", ""),
                        duration_ms=r.get("duration_ms"),
                        mbid=r.get("mbid"),
                        artist_mbid=r.get("artist_mbid"),
                        album_mbid=r.get("album_mbid"),
                        raw_data=r,
                    )
                    for r in results
                ]

        return []


class ArtistTracksSearch(SearchStrategy):
    """Artist track expansion strategy.

    Searches for an artist directory and expands all their tracks.
    Used as a fallback when primary search fails to find the artist.
    """

    async def search(self, target: BaseTarget, criteria: SearchCriteria) -> list[TrackCandidate]:
        from src.app.core.matching.candidate import TrackCandidate

        if not criteria.artist:
            return []

        results = await target.search_artist_tracks(criteria.artist, criteria.genre)
        return [
            TrackCandidate(
                item_id=r.get("item_id") or r.get("id", ""),
                title=r.get("title", ""),
                artist_name=r.get("artist_name", ""),
                album_name=r.get("album_name", ""),
                duration_ms=r.get("duration_ms"),
                mbid=r.get("mbid"),
                artist_mbid=r.get("artist_mbid"),
                album_mbid=r.get("album_mbid"),
                raw_data=r,
            )
            for r in results
        ]


class TitleOnlySearch(SearchStrategy):
    """Title-only fallback search strategy."""

    async def search(self, target: BaseTarget, criteria: SearchCriteria) -> list[TrackCandidate]:
        from src.app.core.matching.candidate import TrackCandidate

        if not criteria.title:
            return []

        results = await target.search_title_only(criteria.title)
        return [
            TrackCandidate(
                item_id=r.get("item_id") or r.get("id", ""),
                title=r.get("title", ""),
                artist_name=r.get("artist_name", ""),
                album_name=r.get("album_name", ""),
                duration_ms=r.get("duration_ms"),
                mbid=r.get("mbid"),
                artist_mbid=r.get("artist_mbid"),
                album_mbid=r.get("album_mbid"),
                raw_data=r,
            )
            for r in results
        ]
