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

    auth_required: bool = False
    """Whether an authenticated account unlocks meaningfully more content.

    ``anonymous`` covers *whether anything works at all*; ``auth_required``
    signals that configuring an account (e.g. via Settings → Sources)
    meaningfully improves the experience (for example YT Music's
    personalised home feed).  Providers without any auth concept leave it
    ``False``.
    """

    @abstractmethod
    async def get_home(self, force: bool = False) -> ExploreHome:
        """Return the main Explore page as a set of sections.

        :param force: bypass the shared client's cache (used by a UI refresh).
        """
        ...

    @abstractmethod
    async def get_charts(self, force: bool = False) -> ChartsBundle:
        """Return top songs, artists, and optionally videos."""
        ...

    @abstractmethod
    async def get_moods(self, force: bool = False) -> list[MoodCategory]:
        """Return available mood / genre categories."""
        ...

    @abstractmethod
    async def get_mood_playlists(self, mood_id: str, force: bool = False) -> list[ExploreItem]:
        """Return playlists for a given mood or genre category."""
        ...

    @abstractmethod
    async def search_playlists(self, query: str, force: bool = False) -> list[ExploreItem]:
        """Search this source for playlists matching *query*."""
        ...
