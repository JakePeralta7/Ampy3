"""Base class for application services with lifecycle management."""
from __future__ import annotations

import logging
from abc import ABC, abstractmethod
from typing import Any

logger = logging.getLogger(__name__)


class ServiceBase(ABC):
    """Abstract base class for singleton application services.

    Provides lazy initialization, singleton lifecycle, and reset capability.
    Subclasses implement ``create()`` (sync) for simple services, or override
    ``get_instance()`` for async initialization.
    """

    _instance: Any = None

    @classmethod
    @abstractmethod
    def create(cls) -> Any:
        """Create and return a new service instance (sync)."""
        ...

    @classmethod
    def get_instance(cls) -> Any:
        """Get or lazily create the singleton service instance."""
        if cls._instance is None:
            cls._instance = cls.create()
            logger.info("Initialized %s", cls.__name__)
        return cls._instance

    @classmethod
    async def get_instance_async(cls) -> Any:
        """Async variant of ``get_instance``.

        Override this in subclasses that need async initialization
        (e.g. fetching tokens from the database).
        """
        if cls._instance is None:
            cls._instance = await cls.create_async()
            logger.info("Initialized %s (async)", cls.__name__)
        return cls._instance

    @classmethod
    @abstractmethod
    async def create_async(cls) -> Any:
        """Create a new service instance asynchronously.

        Override this instead of ``create`` when initialization requires
        ``await`` (e.g. database lookups).  By default raises
        ``NotImplementedError`` so sync-only services can ignore it.
        """
        raise NotImplementedError

    @classmethod
    def reset(cls) -> None:
        """Reset the singleton instance (useful for testing)."""
        cls._instance = None
        logger.info("Reset %s", cls.__name__)
