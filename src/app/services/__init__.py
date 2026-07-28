"""Application service container with dependency injection.

Manages singleton instances of external services (Ollama, Celery, Valkey).
Provides factory functions for creating and retrieving service instances.
"""

import logging
from typing import Any

from src.app.services.celery import CeleryService
from src.app.services.ollama import OllamaService
from src.app.services.target import TargetService
from src.app.services.valkey import ValkeyService

logger = logging.getLogger(__name__)


def reset_services() -> None:
    """Reset all service instances (useful for testing)."""
    TargetService.reset()
    OllamaService.reset()
    CeleryService.reset()
    ValkeyService.reset()
    logger.info("All services reset")


def get_ollama_client() -> Any:
    """Dependency injection: Get Ollama client instance (lazy singleton)."""
    return OllamaService.get_instance()


def get_celery_app() -> Any:
    """Dependency injection: Get Celery app instance (lazy singleton)."""
    return CeleryService.get_instance()


def get_valkey_client() -> Any:
    """Dependency injection: Get Valkey client instance (lazy singleton)."""
    return ValkeyService.get_instance()


async def get_sync_target(target_id: str = "Plex") -> Any:
    """Get a sync target instance by ID.

    Returns a :class:`BaseTarget` implementation (e.g. ``PlexTarget``).
    Uses the target registry's registered factory to construct the target.
    Defaults to ``"Plex"`` for backward compatibility.
    """
    return await TargetService.get_target_async(target_id)


async def list_sync_targets() -> list[dict[str, str]]:
    """Return all registered sync targets."""
    import src.app.core.targets  # noqa: F401
    from src.app.core.targets.registry import TargetRegistry

    return TargetRegistry.list_targets()


__all__ = [
    "reset_services",
    "get_ollama_client",
    "get_celery_app",
    "get_valkey_client",
    "get_sync_target",
    "list_sync_targets",
]
