"""Registry for metadata providers (MusicBrainz, Deezer, etc.)."""

from __future__ import annotations

import logging
from typing import TYPE_CHECKING

if TYPE_CHECKING:
    from src.app.core.providers.base import BaseMetadataProvider

logger = logging.getLogger(__name__)


class ProviderRegistry:
    """Singleton registry that maps provider_id -> BaseMetadataProvider."""

    _instance: ProviderRegistry | None = None

    def __init__(self) -> None:
        self._providers: dict[str, BaseMetadataProvider] = {}

    @classmethod
    def get_instance(cls) -> ProviderRegistry:
        if cls._instance is None:
            cls._instance = cls()
        return cls._instance

    def register(self, provider: BaseMetadataProvider) -> None:
        self._providers[provider.provider_id] = provider
        logger.info("Registered metadata provider: %s", provider.provider_id)

    def get(self, provider_id: str) -> BaseMetadataProvider | None:
        return self._providers.get(provider_id)

    def list_providers(self) -> list[str]:
        return list(self._providers.keys())


def register_provider(provider: BaseMetadataProvider) -> None:
    """Convenience function to register a provider with the global registry."""
    ProviderRegistry.get_instance().register(provider)


def get_provider(provider_id: str) -> BaseMetadataProvider | None:
    """Convenience function to look up a provider by ID."""
    return ProviderRegistry.get_instance().get(provider_id)
