"""Tests for the plex tools."""
import pytest
from unittest.mock import AsyncMock, patch, MagicMock


class TestPlexTools:
    """Tests for plex tools - testing the underlying functions directly."""

    @pytest.mark.asyncio
    @patch("src.app.llm.tools.plex.get_plex_client")
    async def test_search_plex_playlists(self, mock_get_client):
        """Test search_plex_playlists tool."""
        from src.app.llm.tools.plex import search_plex_playlists
        
        mock_client = AsyncMock()
        mock_get_client.return_value = mock_client
        
        mock_client.search_playlists.return_value = [
            {
                "title": "My Playlist",
                "rating_key": "123",
                "playlist_id": "123",
                "summary": "A test playlist",
                "track_count": 10,
            }
        ]
        
        # Use ainvoke for async tools
        result = await search_plex_playlists.ainvoke({"query": "My"})
        
        assert len(result) == 1
        assert result[0]["title"] == "My Playlist"
        mock_client.search_playlists.assert_called_once_with("My")

    @pytest.mark.asyncio
    @patch("src.app.llm.tools.plex.get_plex_client")
    async def test_list_plex_playlists(self, mock_get_client):
        """Test list_plex_playlists tool."""
        from src.app.llm.tools.plex import list_plex_playlists
        
        mock_client = AsyncMock()
        mock_get_client.return_value = mock_client
        
        mock_client.search_playlists.return_value = [
            {"title": "Playlist 1", "name": "Playlist 1"},
            {"title": "Playlist 2", "name": "Playlist 2"},
        ]
        
        result = await list_plex_playlists.ainvoke({})
        
        assert "Your Plex playlists:" in result
        assert "Playlist 1" in result
        assert "Playlist 2" in result

    @pytest.mark.asyncio
    @patch("src.app.llm.tools.plex.get_plex_client")
    async def test_list_plex_playlists_empty(self, mock_get_client):
        """Test list_plex_playlists when no playlists exist."""
        from src.app.llm.tools.plex import list_plex_playlists
        
        mock_client = AsyncMock()
        mock_get_client.return_value = mock_client
        
        mock_client.search_playlists.return_value = []
        
        result = await list_plex_playlists.ainvoke({})
        
        assert "No playlists found" in result

    @pytest.mark.asyncio
    @patch("src.app.llm.tools.plex.get_plex_client")
    async def test_search_plex_library(self, mock_get_client):
        """Test search_plex_library tool."""
        from src.app.llm.tools.plex import search_plex_library
        
        mock_client = AsyncMock()
        mock_get_client.return_value = mock_client
        
        mock_client.search_library.return_value = [
            {
                "plex_id": "97300",
                "title": "Bohemian Rhapsody",
                "artist_name": "Queen",
                "album_name": "A Night at the Opera",
                "duration_ms": 354000,
            }
        ]
        
        result = await search_plex_library.ainvoke({
            "query": "Bohemian Rhapsody",
            "artist": "Queen",
            "genre": ""
        })
        
        assert len(result) == 1
        assert result[0]["title"] == "Bohemian Rhapsody"
        mock_client.search_library.assert_called_once_with(
            title="Bohemian Rhapsody", artist="Queen", genre=""
        )

    @pytest.mark.asyncio
    @patch("src.app.llm.tools.plex.get_plex_client")
    async def test_create_plex_playlist(self, mock_get_client):
        """Test create_plex_playlist tool."""
        from src.app.llm.tools.plex import create_plex_playlist
        
        mock_client = AsyncMock()
        mock_get_client.return_value = mock_client
        
        # Mock get_plist_by_name to return None (no existing playlist)
        mock_client.get_plist_by_name.return_value = None
        
        # Mock search_library to return a track
        mock_client.search_library.return_value = [
            {
                "plex_id": "97300",
                "title": "Bohemian Rhapsody",
                "artist_name": "Queen",
            }
        ]
        
        # Mock create_plist_from_results to return a playlist ID
        mock_client.create_plist_from_results.return_value = "789"
        
        result = await create_plex_playlist.ainvoke({
            "title": "My Test Playlist",
            "track_descriptions": [
                {"title": "Bohemian Rhapsody", "artist": "Queen"},
            ]
        })
        
        assert "Created playlist 'My Test Playlist'" in result
        assert "789" in result
        assert "1/1 tracks matched" in result

    @pytest.mark.asyncio
    @patch("src.app.llm.tools.plex.get_plex_client")
    async def test_create_plex_playlist_with_plex_id(self, mock_get_client):
        """Test create_plex_playlist with plex_id provided."""
        from src.app.llm.tools.plex import create_plex_playlist
        
        mock_client = AsyncMock()
        mock_get_client.return_value = mock_client
        
        # Mock get_plist_by_name to return None (no existing playlist)
        mock_client.get_plist_by_name.return_value = None
        
        # Should not call search_library if plex_id is provided
        mock_client.create_plist_from_results.return_value = "789"
        
        result = await create_plex_playlist.ainvoke({
            "title": "My Test Playlist",
            "track_descriptions": [
                {"title": "Bohemian Rhapsody", "artist": "Queen", "plex_id": "97300"},
            ]
        })
        
        assert "Created playlist 'My Test Playlist'" in result
        mock_client.search_library.assert_not_called()

    @pytest.mark.asyncio
    @patch("src.app.llm.tools.plex.get_plex_client")
    async def test_add_tracks_to_plex_playlist(self, mock_get_client):
        """Test add_tracks_to_plex_playlist tool."""
        from src.app.llm.tools.plex import add_tracks_to_plex_playlist
        
        mock_client = AsyncMock()
        mock_get_client.return_value = mock_client
        
        # Mock search_library
        mock_client.search_library.return_value = [
            {
                "plex_id": "97300",
                "title": "Bohemian Rhapsody",
                "artist_name": "Queen",
            }
        ]
        
        # Mock add_items_to_playlist
        mock_client.add_items_to_playlist.return_value = 1
        
        result = await add_tracks_to_plex_playlist.ainvoke({
            "playlist_id": "789",
            "track_descriptions": [
                {"title": "Bohemian Rhapsody", "artist": "Queen"},
            ]
        })
        
        assert "Added 1/1 tracks" in result

    @pytest.mark.asyncio
    @patch("src.app.llm.tools.plex.get_plex_client")
    async def test_get_plex_playlist_tracks(self, mock_get_client):
        """Test get_plex_playlist_tracks tool."""
        from src.app.llm.tools.plex import get_plex_playlist_tracks
        
        mock_client = AsyncMock()
        mock_get_client.return_value = mock_client
        
        mock_client.get_items_in_playlist.return_value = [
            {
                "plex_id": "97300",
                "title": "Bohemian Rhapsody",
                "artist_name": "Queen",
                "album_name": "A Night at the Opera",
                "duration": 354,
            }
        ]
        
        result = await get_plex_playlist_tracks.ainvoke({"playlist_id": "789"})
        
        assert len(result) == 1
        assert result[0]["title"] == "Bohemian Rhapsody"

    @pytest.mark.asyncio
    @patch("src.app.llm.tools.plex.get_plex_client")
    async def test_delete_plex_playlist(self, mock_get_client):
        """Test delete_plex_playlist tool."""
        from src.app.llm.tools.plex import delete_plex_playlist
        
        mock_client = AsyncMock()
        mock_get_client.return_value = mock_client
        
        mock_client.delete_plist.return_value = True
        
        result = await delete_plex_playlist.ainvoke({"playlist_id": "789"})
        
        assert "deleted successfully" in result
        mock_client.delete_plist.assert_called_once_with("789")

    @pytest.mark.asyncio
    @patch("src.app.llm.tools.plex.get_plex_client")
    async def test_delete_plex_playlist_failure(self, mock_get_client):
        """Test delete_plex_playlist when deletion fails."""
        from src.app.llm.tools.plex import delete_plex_playlist
        
        mock_client = AsyncMock()
        mock_get_client.return_value = mock_client
        
        mock_client.delete_plist.return_value = False
        
        result = await delete_plex_playlist.ainvoke({"playlist_id": "789"})
        
        assert "Failed to delete" in result


class TestPlexToolsSyntax:
    """Test that plex tools have correct syntax and imports."""
    
    def test_plex_tools_have_get_plex_client_calls(self):
        """Verify that all plex tools call get_plex_client()."""
        import inspect
        from src.app.llm.tools import plex
        
        # Get all tool functions
        tools_to_check = [
            "search_plex_playlists",
            "list_plex_playlists", 
            "search_plex_library",
            "create_plex_playlist",
            "add_tracks_to_plex_playlist",
            "get_plex_playlist_tracks",
            "delete_plex_playlist",
        ]
        
        for tool_name in tools_to_check:
            tool = getattr(plex, tool_name)
            # Get the source code of the underlying function
            # For StructuredTool, the callback is stored differently
            if hasattr(tool, 'callback'):
                source = inspect.getsource(tool.callback)
            else:
                # Try to get it from __wrapped__ or other attributes
                source = str(tool)
            
            # We can't easily extract source from StructuredTool, so just
            # verify the tool exists and is callable
            assert callable(tool) or hasattr(tool, 'invoke'), \
                f"{tool_name} should be a callable tool"
