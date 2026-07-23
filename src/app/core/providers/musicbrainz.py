"""MusicBrainz metadata provider."""
from __future__ import annotations

from src.app.core.musicbrainz import MusicBrainzResolver
from src.app.core.providers.base import BaseMetadataProvider


class MusicBrainzProvider(BaseMetadataProvider):
    """Delegates all calls to :class:`MusicBrainzResolver`."""

    provider_id = "musicbrainz"
    display_name = "MusicBrainz"

    def __init__(self, user_agent: str = "ampy3/0.1.0") -> None:
        self._resolver = MusicBrainzResolver(user_agent=user_agent)

    def search_recording(
        self,
        title: str,
        artist: str | None = None,
        duration_ms: int | None = None,
    ) -> dict | None:
        return self._resolver.search_recording(title, artist, duration_ms)

    def search_recordings(
        self,
        query: str,
        artist: str = "",
        limit: int = 10,
    ) -> list[dict]:
        return self._resolver.search_recordings(query, artist, limit)

    def lookup_artist(self, name: str) -> dict | None:
        return self._resolver.lookup_artist(name)

    def search_artists(self, query: str, limit: int = 10) -> list[dict]:
        return self._resolver.search_artists(query, limit)

    def lookup_release_group(
        self,
        title: str,
        artist_name: str | None = None,
    ) -> dict | None:
        return self._resolver.lookup_release_group(title, artist_name)

    def search_releases(
        self,
        query: str,
        artist: str = "",
        limit: int = 10,
    ) -> list[dict]:
        return self._resolver.search_releases(query, artist, limit)

    def lookup_release(self, mbid: str) -> dict | None:
        return self._resolver.lookup_release(mbid)

    def get_artist_releases(self, artist_id: str, limit: int = 25) -> list[dict]:
        return self._resolver.get_artist_releases(artist_id, limit)

    def get_release_tracks(self, release_id: str) -> list[dict]:
        return self._resolver.get_release_tracks(release_id)

    def search_by_tag(
        self,
        tag: str,
        entity: str = "artist",
        limit: int = 10,
    ) -> list[dict]:
        return self._resolver.search_by_tag(tag, entity, limit)
