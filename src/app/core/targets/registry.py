"""Sync target registry with plugin-style registration."""

from __future__ import annotations

import logging
from collections.abc import Callable
from typing import TYPE_CHECKING, Any

if TYPE_CHECKING:
    from src.app.core.targets.base import BaseTarget

logger = logging.getLogger(__name__)


class TargetRegistry:
    """Central registry of sync target adapters.

    Targets self-register via the ``@register_target`` decorator.
    An optional async factory callable can be registered to construct
    a fully-initialised target instance from DB config.
    """

    _targets: dict[str, type[BaseTarget]] = {}
    _factories: dict[str, Callable[..., Any]] = {}

    @classmethod
    def register(
        cls,
        target_id: str,
        target_class: type[BaseTarget],
        factory: Callable[..., Any] | None = None,
    ) -> None:
        """Register a target adapter class under *target_id*."""
        if target_id in cls._targets:
            logger.warning(
                "Overwriting existing target registration for '%s': %s -> %s",
                target_id,
                cls._targets[target_id].__name__,
                target_class.__name__,
            )
        cls._targets[target_id] = target_class
        if factory is not None:
            cls._factories[target_id] = factory
        logger.debug("Registered target '%s' -> %s", target_id, target_class.__name__)

    @classmethod
    def get(cls, target_id: str) -> type[BaseTarget]:
        """Return the target adapter class for *target_id*.

        Raises ``KeyError`` if the target is not registered.
        """
        try:
            return cls._targets[target_id]
        except KeyError:
            available = ", ".join(sorted(cls._targets)) or "(none)"
            raise KeyError(f"Unknown target '{target_id}'. Available: {available}") from None

    @classmethod
    def get_factory(cls, target_id: str) -> Callable[..., Any]:
        """Return the async factory callable for *target_id*.

        Raises ``KeyError`` if no factory is registered.
        """
        try:
            return cls._factories[target_id]
        except KeyError:
            available = ", ".join(sorted(cls._factories)) or "(none)"
            raise KeyError(f"No factory for target '{target_id}'. Available: {available}") from None

    @classmethod
    def list_targets(cls) -> list[dict[str, str]]:
        """Return metadata for all registered targets."""
        return [
            {
                "id": target_class.target_id,
                "name": target_class.display_name,
            }
            for target_class in cls._targets.values()
        ]


def register_target(
    target_id: str,
    factory: Callable[..., Any] | None = None,
) -> Callable[[type[BaseTarget]], type[BaseTarget]]:
    """Decorator to register a sync target adapter class.

    Usage::

        @register_target("plex", factory=create_plex_target)
        class PlexTarget(BaseTarget):
            target_id = "plex"
            display_name = "Plex Media Server"
            ...
    """

    def decorator(cls: type[BaseTarget]) -> type[BaseTarget]:
        cls.target_id = target_id
        TargetRegistry.register(target_id, cls, factory=factory)
        return cls

    return decorator
