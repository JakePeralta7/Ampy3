"""Tests for the LLM Ollama client."""
from unittest.mock import AsyncMock, patch

import pytest

from src.app.llm.ollama_client import get_llm, health_check


class TestOllamaClient:

    def test_get_llm_returns_chatollama(self):
        llm = get_llm()
        assert llm.model is not None
        assert llm.base_url is not None

    @patch("httpx.AsyncClient.get")
    async def test_health_check_success(self, mock_get):
        mock_get.return_value = AsyncMock(
            status_code=200,
            json=lambda: {"models": [{"name": "llama3.1:8b"}]},
        )
        result = await health_check()
        assert "models" in result
        assert result["models"][0]["name"] == "llama3.1:8b"

    @patch("httpx.AsyncClient.get")
    async def test_health_check_failure(self, mock_get):
        mock_get.side_effect = ConnectionError("Connection refused")
        with pytest.raises(ConnectionError):
            await health_check()
