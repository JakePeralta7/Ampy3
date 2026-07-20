"""Tests for Valkey-backed chat history."""
from unittest.mock import AsyncMock, patch

import pytest

from src.app.llm.history import append_message, clear_history, get_history


class TestChatHistory:

    @patch("src.app.llm.history._get_client")
    async def test_append_and_get_history(self, mock_get_client):
        mock_client = AsyncMock()
        mock_client.rpush = AsyncMock()
        mock_client.expire = AsyncMock()
        mock_client.lrange = AsyncMock(return_value=[
            '{"role": "user", "content": "hello"}',
            '{"role": "assistant", "content": "hi there"}',
        ])
        mock_get_client.return_value = mock_client

        await append_message("sess-1", "user", "hello")
        mock_client.rpush.assert_called_once()

        history = await get_history("sess-1")
        assert len(history) == 2
        assert history[0]["role"] == "user"
        assert history[1]["content"] == "hi there"

    @patch("src.app.llm.history._get_client")
    async def test_clear_history(self, mock_get_client):
        mock_client = AsyncMock()
        mock_client.delete = AsyncMock()
        mock_get_client.return_value = mock_client

        await clear_history("sess-1")
        mock_client.delete.assert_called_once_with("chat:sess-1")
