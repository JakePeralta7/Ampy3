"""Application service container with dependency injection.

Manages singleton instances of external services (Plex, Ollama, Celery, Valkey).
Provides factory functions for creating and retrieving service instances.
"""
import logging
from functools import lru_cache

from src.app.services.celery import CeleryService
from src.app.services.ollama import OllamaService
from src.app.services.plex import PlexService
from src.app.services.valkey import ValkeyService

logger = logging.getLogger(__name__)


def reset_services():
    """Reset all service instances (useful for testing)."""
    PlexService.reset()
    OllamaService.reset()
    CeleryService.reset()
    ValkeyService.reset()
    logger.info("All services reset")


@lru_cache(maxsize=1)
def get_ollama_client():
    """Dependency injection: Get Ollama client instance (lazy singleton)."""
    return OllamaService.get_client()


@lru_cache(maxsize=1)
def get_celery_app():
    """Dependency injection: Get Celery app instance (lazy singleton)."""
    return CeleryService.get_app()


@lru_cache(maxsize=1)
def get_valkey_client():
    """Dependency injection: Get Valkey client instance (lazy singleton)."""
    return ValkeyService.get_client()


async def get_plex_client():
    """Dependency injection: Get Plex client instance (lazy singleton)."""
    return await PlexService.get_client()


__all__ = [
    "reset_services",
    "get_plex_client",
    "get_ollama_client",
    "get_celery_app",
    "get_valkey_client",
]
