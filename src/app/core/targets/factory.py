"""Target factory base class and registration decorator."""

from __future__ import annotations

from abc import ABC
from collections.abc import Callable
from typing import TYPE_CHECKING, Any, ClassVar

if TYPE_CHECKING:
    from src.app.core.targets.base import BaseTarget
    from src.app.models import Config

from src.app.core.targets.registry import TargetRegistry
from src.app.db import AsyncSessionLocal
from src.app.services.crypto import decrypt_token


class TargetFactory(ABC):
    """Base class for sync target factories.

    Encapsulates the pattern of loading configuration from the database,
    decrypting sensitive values, and constructing a fully-initialized
    target instance. Subclasses declare required config keys and how
    to map them to target constructor arguments.
    """

    REQUIRED_KEYS: ClassVar[list[str]] = []
    """Config keys required to construct this target."""

    SENSITIVE_KEYS: ClassVar[set[str]] = set()
    """Subset of REQUIRED_KEYS that are encrypted in the database."""

    target_class: ClassVar[type[BaseTarget]]
    """The BaseTarget subclass this factory produces."""

    target_id: ClassVar[str]
    """Unique target identifier (e.g., 'Plex', 'Jellyfin')."""

    display_name: ClassVar[str]
    """Human-readable target name."""

    @classmethod
    async def create(cls) -> BaseTarget:
        """Create a fully-initialized target instance from DB config.

        Returns:
            An instance of target_class ready for use.

        Raises:
            RuntimeError: If required config is missing.
        """
        config = await cls._load_config()
        return cls.target_class(**cls._build_kwargs(config))

    @classmethod
    async def _load_config(cls) -> dict[str, str]:
        """Load and decrypt required config from the database."""
        async with AsyncSessionLocal() as session:
            from sqlalchemy import select

            from src.app.models import Config

            stmt = select(Config).where(Config.key.in_(cls.REQUIRED_KEYS))
            result = await session.execute(stmt)
            config = {}
            for row in result.scalars().all():
                if row.key in cls.SENSITIVE_KEYS:
                    config[row.key] = decrypt_token(row.value)
                else:
                    config[row.key] = row.value
            return config

    @classmethod
    def _build_kwargs(cls, config: dict[str, str]) -> dict[str, Any]:
        """Map config dict to target constructor keyword arguments.

        Override in subclasses to customize the mapping.
        """
        return config

    @classmethod
    def _validate_config(cls, config: dict[str, str]) -> None:
        """Validate that all required config is present.

        Raises:
            RuntimeError: If any required key is missing or empty.
        """
        missing = [k for k in cls.REQUIRED_KEYS if not config.get(k, "").strip()]
        if missing:
            raise RuntimeError(
                f"{cls.display_name} target not configured. "
                f"Missing: {', '.join(missing)}. Set up in Settings."
            )


def target_factory(
    target_id: str, display_name: str | None = None
) -> Callable[[type[TargetFactory]], type[TargetFactory]]:
    """Decorator to register a target factory.

    Usage:
        @target_factory("plex", "Plex Media Server")
        class PlexTargetFactory(TargetFactory):
            REQUIRED_KEYS = ["plex_host", "plex_token"]
            SENSITIVE_KEYS = {"plex_token"}
            target_class = PlexTarget
            ...
    """

    def decorator(cls: type[TargetFactory]) -> type[TargetFactory]:
        cls.target_id = target_id
        cls.display_name = display_name or target_id
        TargetRegistry.register(target_id, cls.target_class, factory=cls.create)
        return cls

    return decorator
