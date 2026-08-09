"""Explore provider plugin registry.

Follows the same decorator-based pattern as ``SourceRegistry``,
``TargetRegistry``, and ``ProviderRegistry``.
"""

from __future__ import annotations

import logging
from collections.abc import Callable
from typing import TYPE_CHECKING

if TYPE_CHECKING:
    from src.app.core.explore.base import ExploreProvider

logger = logging.getLogger(__name__)


class ExploreRegistry:
    """Central registry of Explore content providers.

    Providers self-register via the ``@register_explore_provider``
    decorator.  The registry enables dynamic lookup by ID and
    enumeration of available sources.
    """

    _providers: dict[str, type[ExploreProvider]] = {}

    @classmethod
    def register(cls, provider_id: str, provider_class: type[ExploreProvider]) -> None:
        if provider_id in cls._providers:
            logger.warning(
                "Overwriting existing explore provider '%s': %s -> %s",
                provider_id,
                cls._providers[provider_id].__name__,
                provider_class.__name__,
            )
        cls._providers[provider_id] = provider_class
        logger.debug("Registered explore provider '%s' -> %s", provider_id, provider_class.__name__)

    @classmethod
    def get(cls, provider_id: str) -> type[ExploreProvider]:
        try:
            return cls._providers[provider_id]
        except KeyError:
            available = ", ".join(sorted(cls._providers)) or "(none)"
            msg = f"Unknown explore provider '{provider_id}'. Available: {available}"
            raise KeyError(msg) from None

    @classmethod
    def list_providers(cls) -> list[dict[str, str]]:
        return [
            {
                "provider_id": provider_class.provider_id,
                "display_name": provider_class.display_name,
            }
            for provider_class in cls._providers.values()
        ]


def register_explore_provider(
    provider_id: str,
) -> Callable[[type[ExploreProvider]], type[ExploreProvider]]:
    """Decorator to register an Explore provider class.

    Usage::

        @register_explore_provider("youtube_music")
        class YTMusicExploreProvider(ExploreProvider):
            provider_id = "youtube_music"
            display_name = "YouTube Music"
            ...
    """

    def decorator(cls: type[ExploreProvider]) -> type[ExploreProvider]:
        cls.provider_id = provider_id
        ExploreRegistry.register(provider_id, cls)
        return cls

    return decorator
