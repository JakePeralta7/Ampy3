"""Target service — singleton lifecycle for sync targets."""

from __future__ import annotations

import logging
from typing import Any

from src.app.services.base import ServiceBase

logger = logging.getLogger(__name__)


class TargetService(ServiceBase):
    """Service for managing sync target instances (async initialization)."""

    @classmethod
    def create(cls) -> Any:
        raise NotImplementedError("Use get_target_async() for TargetService")

    @classmethod
    async def create_async(cls) -> Any:
        raise NotImplementedError("Use get_target_async() for TargetService")

    @classmethod
    async def get_target_async(cls, target_id: str) -> Any:
        """Get or create a sync target instance by ID.

        Uses the target registry's factory to construct the target from DB config.
        Returns a :class:`BaseTarget` implementation (e.g. ``PlexTarget``).
        """
        import src.app.core.targets  # noqa: F401 — trigger registrations
        from src.app.core.targets.registry import TargetRegistry

        TargetRegistry.get(target_id)  # validate target_id exists
        factory = TargetRegistry.get_factory(target_id)
        return await factory()
