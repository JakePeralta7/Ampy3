"""Tests for the chat API endpoints."""
from unittest.mock import AsyncMock, patch

import pytest
from fastapi.testclient import TestClient

from src.main import app

client = TestClient(app)


class TestChatHistoryAPI:
    """Tests for chat history endpoints."""

    @patch("src.app.api.chat.get_history")
    async def test_get_chat_history(self, mock_get_history):
        mock_get_history.return_value = [
            {"role": "user", "content": "hello"},
            {"role": "assistant", "content": "world"},
        ]
        resp = client.get("/api/v1/chat/history/sess-1")
        assert resp.status_code == 200
        data = resp.json()
        assert len(data["messages"]) == 2

    @patch("src.app.api.chat.clear_history")
    async def test_delete_chat_history(self, mock_clear):
        mock_clear.return_value = None
        resp = client.delete("/api/v1/chat/history/sess-1")
        assert resp.status_code == 200
        assert resp.json()["status"] == "cleared"
