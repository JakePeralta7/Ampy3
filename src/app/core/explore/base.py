"""Abstract base class for Explore providers.

Each ``ExploreProvider`` subclass is a plugin that sources discoverable
music content — new releases, charts, moods, trending, etc. — from a
particular platform (YouTube Music, MusicBrainz, Last.fm, Spotify, …).
"""

from __future__ import annotations

from abc import ABC, abstractmethod

from src.app.core.explore.models import ChartsBundle, ExploreHome, ExploreItem, MoodCategory


class ExploreProvider(ABC):
    """Interface every Explore provider must implement.

    Subclasses must set ``provider_id`` and ``display_name`` class
    attributes and implement the abstract methods below.
    """

    provider_id: str
    display_name: str
    anonymous: bool = True
    """Whether this provider works without any source authentication."""

    @abstractmethod
    async def get_home(self) -> ExploreHome:
        """Return the main Explore page as a set of sections."""
        ...

    @abstractmethod
    async def get_charts(self) -> ChartsBundle:
        """Return top songs, artists, and optionally videos."""
        ...

    @abstractmethod
    async def get_moods(self) -> list[MoodCategory]:
        """Return available mood / genre categories."""
        ...

    @abstractmethod
    async def get_mood_playlists(self, mood_id: str) -> list[ExploreItem]:
        """Return playlists for a given mood or genre category."""
        ...

    @abstractmethod
    async def search_playlists(self, query: str) -> list[ExploreItem]:
        """Search this source for playlists matching *query*."""
        ...
