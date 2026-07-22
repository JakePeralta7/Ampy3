"""Ollama LLM client service."""
import logging

from src.app.services.base import ServiceBase

logger = logging.getLogger(__name__)


class OllamaService(ServiceBase):
    """Service for managing Ollama client instance."""

    @classmethod
    def create(cls):
        from src.app.llm.ollama import OllamaClient
        from src.app.settings import settings

        instance = OllamaClient(
            host=settings.ollama_host,
            model=settings.ollama_model,
            timeout=settings.ollama_timeout,
        )
        logger.info("Initialized OllamaClient at %s", settings.ollama_host)
        return instance
