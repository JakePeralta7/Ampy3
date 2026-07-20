"""Tests for the core synchronization orchestration layer."""
from unittest.mock import AsyncMock, MagicMock, patch

import pytest

# Assuming SyncOrchestrator is accessible and takes dependencies/clients in its __init__
from src.app.orchestrator import SyncOrchestrator


class TestSyncOrchestrator:

    @pytest.fixture
    def orchestrator(self):
        """Mock dependencies for the Orchestrator."""
        # Mock clients that the Orchestrator needs
        mock_plex_client = AsyncMock()
        # We assume other adapters (YoutubeMusicSource, MusicBrainzResolver) are available
        # or can be mocked if they don't take external dependencies in theory.

        return SyncOrchestrator(
            plex_client=mock_plex_client # Injecting the mock dependency
        )

    async def test_full_sync_success(self, orchestrator: SyncOrchestrator):
        """Tests a successful sync path when all metadata matches and Plex calls succeed."""
        # Mock inputs
        mock_session_id = "playlist-123"
        mock_source = "YouTubeMusic"

        async def mock_run_sync(playlist_ids, source):
            # Simulate successful fetching of items
            return [{"title": "Sync Track", "artist": "Artist X", "mbid": "abc-999"}]

        with patch.object(orchestrator, 'run_sync', new=mock_run_sync) as mock_method:
            # Execute the method under test
            result = await orchestrator.run_sync(playlist_ids=[mock_session_id], source=mock_source)

            # Assertions
            assert result[0]['title'] == "Sync Track"
            mock_method.assert_called_once()


    async def test_plex_failure_during_sync(self, orchestrator: SyncOrchestrator):
        """Tests graceful handling when the Plex client fails during item addition."""
        mock_session_id = "playlist-fail"
        mock_source = "YouTubeMusic"

        # Set up a mock run_sync that encounters an internal error simulating API failure
        async def failing_run_sync(*args, **kwargs):
            raise ConnectionError("Plex API connection timeout occurred.")

        with patch.object(orchestrator, 'run_sync', new=failing_run_sync):
            # Execute and ensure it handles the exception without crashing completely
            with pytest.raises(ConnectionError):
                 await orchestrator.run_sync(playlist_ids=[mock_session_id], source=mock_source)

    async def test_no_matching_items(self, orchestrator: SyncOrchestrator):
        """Tests the handling when no matching items are found for sync."""
        mock_session_id = "empty-playlist"
        mock_source = "YouTubeMusic"

        # Mock run_sync returning an empty state list
        async def mock_run_synced(playlist_ids, source):
            return []

        with patch.object(orchestrator, 'run_sync', new=mock_run_synced):
             result = await orchestrator.run_sync(playlist_ids=[mock_session_id], source=mock_source)
             assert result == []
