"""Abstract base class for metadata providers (MusicBrainz, Deezer, etc.)."""

from __future__ import annotations

from abc import ABC, abstractmethod


class BaseMetadataProvider(ABC):
    """Interface that every metadata provider must implement.

    Subclasses must set ``provider_id`` and ``display_name`` class
    attributes and implement the search / lookup methods below.
    """

    provider_id: str
    """Unique identifier, e.g. ``"musicbrainz"``."""

    display_name: str
    """Human-readable name, e.g. ``"MusicBrainz"``."""

    # ── recording search ──────────────────────────────────────────────

    @abstractmethod
    def search_recording(
        self,
        title: str,
        artist: str | None = None,
        duration_ms: int | None = None,
    ) -> dict | None:
        """Search for a recording by title/artist/duration and return the best match."""
        ...

    @abstractmethod
    def search_recordings(
        self,
        query: str,
        artist: str = "",
        limit: int = 10,
    ) -> list[dict]:
        """Return a list of recording dicts matching *query*."""
        ...

    # ── artist search ─────────────────────────────────────────────────

    @abstractmethod
    def lookup_artist(self, name: str) -> dict | None:
        """Look up a single artist by name."""
        ...

    @abstractmethod
    def search_artists(self, query: str, limit: int = 10) -> list[dict]:
        """Search for artists matching *query*."""
        ...

    # ── release search ────────────────────────────────────────────────

    @abstractmethod
    def lookup_release_group(
        self,
        title: str,
        artist_name: str | None = None,
    ) -> dict | None:
        """Look up a release group by title (and optional artist)."""
        ...

    @abstractmethod
    def search_releases(
        self,
        query: str,
        artist: str = "",
        limit: int = 10,
    ) -> list[dict]:
        """Search for releases/albums matching *query*."""
        ...

    @abstractmethod
    def lookup_release(self, mbid: str) -> dict | None:
        """Look up a specific release by its provider-specific ID."""
        ...

    @abstractmethod
    def get_artist_releases(
        self,
        artist_id: str,
        limit: int = 25,
    ) -> list[dict]:
        """Get releases for an artist by their provider-specific ID."""
        ...

    @abstractmethod
    def get_release_tracks(self, release_id: str) -> list[dict]:
        """Get all tracks in a release by its provider-specific ID."""
        ...

    # ── tag / genre search ────────────────────────────────────────────

    @abstractmethod
    def search_by_tag(
        self,
        tag: str,
        entity: str = "artist",
        limit: int = 10,
    ) -> list[dict]:
        """Search for entities by genre / style tag."""
        ...
