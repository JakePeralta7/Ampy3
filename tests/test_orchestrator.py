"""Tests for the core synchronization orchestration layer."""
from unittest.mock import AsyncMock

import pytest

from src.app.core.services.orchestrator import SyncOrchestrator
from src.app.core.models import PlaylistMetadata, TrackMetadata


def _make_match_result():
    return {
        "found": True,
        "type": "match_engine",
        "match": {"rating_key": "plex-1", "title": "Sync Track", "artist_name": "Artist X", "album_name": "Album Y"},
        "rule_id": 1,
    }


class TestSyncOrchestrator:

    @pytest.fixture
    def orchestrator(self):
        mock_target = AsyncMock()
        mock_target.get_playlist_by_name = AsyncMock(return_value=None)
        return SyncOrchestrator(target=mock_target)

    @pytest.fixture
    def sample_playlist(self):
        return PlaylistMetadata(
            source="YouTubeMusic",
            title="Test Playlist",
            source_id="playlist-123",
            tracks=[
                TrackMetadata(title="Sync Track", artist_name="Artist X", album_name="Album Y", source_id="yt-1"),
            ],
        )

    async def test_full_sync_success(self, orchestrator: SyncOrchestrator, sample_playlist):
        orchestrator._resolve_track = AsyncMock(return_value=_make_match_result())
        result = await orchestrator.sync_playlist(sample_playlist, rules=[])
        assert result["matched"] == 1
        assert result["failed"] == 0

    async def test_target_failure_during_sync(self, orchestrator: SyncOrchestrator, sample_playlist):
        orchestrator._resolve_track = AsyncMock(return_value=_make_match_result())
        orchestrator._target.create_playlist = AsyncMock(
            side_effect=ConnectionError("Target API connection timeout occurred.")
        )
        result = await orchestrator.sync_playlist(sample_playlist, rules=[])
        assert any("Target API connection timeout" in e for e in result["errors"])

    async def test_no_matching_items(self, orchestrator: SyncOrchestrator, sample_playlist):
        orchestrator._resolve_track = AsyncMock(return_value=None)
        result = await orchestrator.sync_playlist(sample_playlist, rules=[])
        assert result["matched"] == 0
        assert result["failed"] == 1
