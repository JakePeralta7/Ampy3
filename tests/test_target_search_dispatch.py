"""Regression tests for target search-strategy dispatch.

The strategy interface takes ``(target, SearchCriteria)`` and returns
``TrackCandidate`` objects. The Plex/Jellyfin search managers previously
called the old kwargs-based interface (``search(self, title=..., ...)``),
which raised ``TypeError`` on every sync.
"""

import asyncio

import pytest

from src.app.core.matching.candidate import TrackCandidate
from src.app.core.targets.jellyfin.search import JellyfinSearchManager
from src.app.core.targets.plex.search import PlexSearchManager
from src.app.core.targets.search import SearchCriteria
from src.app.services.sync_repository import SyncRepository
from src.app.worker.context import SyncContext


class _RecordingStrategy:
    """Strategy double that records how it was invoked."""

    def __init__(self):
        self.calls = []

    async def search(self, target, criteria):
        self.calls.append((target, criteria))
        return [
            TrackCandidate(
                item_id="42",
                title="Song",
                artist_name="Artist",
                album_name="Album",
                duration_ms=1234,
            )
        ]


@pytest.mark.parametrize("manager_cls", [PlexSearchManager, JellyfinSearchManager])
def test_search_library_passes_criteria_to_strategy(manager_cls):
    manager = manager_cls(client=None)
    strategy = _RecordingStrategy()
    manager.search_strategy = strategy

    results = asyncio.run(
        manager.search_library(title="Song", artist="Artist", album="Album", genre="Rock")
    )

    target, criteria = strategy.calls[0]
    assert target is manager
    assert criteria == SearchCriteria(title="Song", artist="Artist", album="Album", genre="Rock")
    assert results[0]["item_id"] == "42"
    assert results[0]["title"] == "Song"
    assert results[0]["artist_name"] == "Artist"


def test_repository_get_existing_playlist_id_uses_context(monkeypatch):
    seen = {}

    class _FakePlaylistSync:
        def __init__(self, ctx):
            seen["ctx"] = ctx

        def get_existing_playlist_id(self, sync_id):
            seen["sync_id"] = sync_id
            return "plex-playlist-1"

    monkeypatch.setattr("src.app.worker.playlist_sync.PlaylistSync", _FakePlaylistSync)

    ctx = SyncContext(
        sync_id=7,
        target_id="Plex",
        user_id="u1",
        playlist_title="Title",
        source_url="https://example.test/playlist",
    )

    assert SyncRepository().get_existing_playlist_id(ctx) == "plex-playlist-1"
    assert seen["ctx"] is ctx
    assert seen["sync_id"] == 7
