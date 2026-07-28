"""Abstract base class for node-graph node handlers."""

from __future__ import annotations

from abc import ABC, abstractmethod
from typing import Any, ClassVar

from src.app.core.models import TrackMetadata

NodeConfig = dict[str, Any]
NodeInputs = dict[str, Any]
NodeOutputs = dict[str, Any]


class NodeHandlerBase(ABC):
    """Base class for all node handlers.

    Each concrete handler stores its YAML config at construction time
    and implements :meth:`execute` with only ``track`` and ``inputs``.
    """

    node_type: ClassVar[str]
    """Machine-readable type string, e.g. ``"search"`` or ``"compare"``."""

    def __init__(self, config: NodeConfig) -> None:
        self._config = config

    @abstractmethod
    async def execute(
        self,
        track: TrackMetadata,
        inputs: NodeInputs,
    ) -> NodeOutputs:
        """Run the node logic and return outputs keyed by source handle."""
        ...

    async def __call__(
        self,
        track: TrackMetadata,
        inputs: NodeInputs,
    ) -> NodeOutputs:
        return await self.execute(track, inputs)
