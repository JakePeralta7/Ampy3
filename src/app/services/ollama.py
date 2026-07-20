"""Ollama LLM client service."""
import logging
from typing import Optional

logger = logging.getLogger(__name__)


class OllamaService:
    """Service for managing Ollama client instance."""

    _instance: object | None = None

    @classmethod
    def get_client(cls):
        """Get or initialize Ollama client instance (lazy singleton)."""
        if cls._instance is None:
            from src.app.llm.ollama import OllamaClient
            from src.app.settings import settings

            cls._instance = OllamaClient(
                host=settings.ollama_host,
                model=settings.ollama_model,
                timeout=settings.ollama_timeout
            )
            logger.info(f"Initialized OllamaClient at {settings.ollama_host}")
        return cls._instance

    @classmethod
    def reset(cls):
        """Reset Ollama client instance."""
        cls._instance = None
        logger.info("Ollama client reset")
