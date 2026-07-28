"""Source adapter registry with plugin-style registration."""

from __future__ import annotations

import logging
from collections.abc import Callable
from typing import TYPE_CHECKING

if TYPE_CHECKING:
    from src.app.core.models import IPlatformSource

logger = logging.getLogger(__name__)


class SourceRegistry:
    """Central registry of platform source adapters.

    Sources self-register via the ``@register_source`` decorator.  The
    registry enables dynamic lookup by source ID and automatic source
    detection from a URL.
    """

    _sources: dict[str, type[IPlatformSource]] = {}

    @classmethod
    def register(cls, source_id: str, source_class: type[IPlatformSource]) -> None:
        """Register a source adapter class under *source_id*."""
        if source_id in cls._sources:
            logger.warning(
                "Overwriting existing source registration for '%s': %s -> %s",
                source_id,
                cls._sources[source_id].__name__,
                source_class.__name__,
            )
        cls._sources[source_id] = source_class
        logger.debug("Registered source '%s' -> %s", source_id, source_class.__name__)

    @classmethod
    def get(cls, source_id: str) -> type[IPlatformSource]:
        """Return the source adapter class for *source_id*.

        Raises ``KeyError`` if the source is not registered.
        """
        try:
            return cls._sources[source_id]
        except KeyError:
            available = ", ".join(sorted(cls._sources)) or "(none)"
            raise KeyError(f"Unknown source '{source_id}'. Available: {available}") from None

    @classmethod
    def detect(cls, url: str) -> type[IPlatformSource] | None:
        """Auto-detect which source can handle *url*.

        Iterates registered sources and calls ``supports_url()``.
        Returns the first match, or ``None`` if no source matches.
        """
        for source_class in cls._sources.values():
            if source_class.supports_url(url):
                return source_class
        return None

    @classmethod
    def list_sources(cls) -> list[dict[str, str]]:
        """Return metadata for all registered sources."""
        return [
            {
                "id": source_class.source_id,
                "name": source_class.display_name,
            }
            for source_class in cls._sources.values()
        ]


def register_source(source_id: str) -> Callable[[type[IPlatformSource]], type[IPlatformSource]]:
    """Decorator to register a source adapter class.

    Usage::

        @register_source("youtube_music")
        class YouTubeMusicSource(IPlatformSource):
            source_id = "youtube_music"
            display_name = "YouTube Music"
            ...
    """

    def decorator(cls: type[IPlatformSource]) -> type[IPlatformSource]:
        cls.source_id = source_id
        SourceRegistry.register(source_id, cls)
        return cls

    return decorator
