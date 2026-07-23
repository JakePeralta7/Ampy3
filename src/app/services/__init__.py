"""Application service container with dependency injection.

Manages singleton instances of external services (Plex, Ollama, Celery, Valkey).
Provides factory functions for creating and retrieving service instances.
"""
import logging

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


def get_ollama_client():
    """Dependency injection: Get Ollama client instance (lazy singleton)."""
    return OllamaService.get_instance()


def get_celery_app():
    """Dependency injection: Get Celery app instance (lazy singleton)."""
    return CeleryService.get_instance()


def get_valkey_client():
    """Dependency injection: Get Valkey client instance (lazy singleton)."""
    return ValkeyService.get_instance()


async def get_plex_client():
    """Dependency injection: Get Plex client instance (lazy singleton)."""
    return await PlexService.get_instance_async()


async def get_sync_target(target_id: str = "plex"):
    """Get a sync target instance by ID.

    Returns a :class:`BaseTarget` implementation (e.g. ``PlexTarget``).
    Defaults to ``"plex"`` for backward compatibility.
    """
    from src.app.core.targets.registry import TargetRegistry

    TargetRegistry.get(target_id)  # validate target_id exists

    if target_id == "plex":
        from src.app.core.targets.plex import PlexTarget

        plex_client = await get_plex_client()
        return PlexTarget(plex_client)

    raise NotImplementedError(
        f"Target '{target_id}' has no factory registered in get_sync_target()"
    )


async def list_sync_targets():
    """Return all registered sync targets."""
    from src.app.core.targets.registry import TargetRegistry

    return TargetRegistry.list_targets()


__all__ = [
    "reset_services",
    "get_plex_client",
    "get_ollama_client",
    "get_celery_app",
    "get_valkey_client",
    "get_sync_target",
    "list_sync_targets",
]
