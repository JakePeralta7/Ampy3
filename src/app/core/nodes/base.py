"""Protocol and base class for node-graph node handlers."""

from __future__ import annotations

from abc import ABC, abstractmethod
from typing import Any, Protocol, runtime_checkable

from src.app.core.models import TrackMetadata

NodeConfig = dict[str, Any]
NodeInputs = dict[str, Any]
NodeOutputs = dict[str, Any]


@runtime_checkable
class NodeHandlerProtocol(Protocol):
    """Structural type for anything that can execute a node."""

    async def __call__(
        self,
        config: NodeConfig,
        track: TrackMetadata,
        inputs: NodeInputs,
    ) -> NodeOutputs: ...


class NodeHandlerBase(ABC):
    """Base class for stateful or complex node handlers.

    Subclasses implement :meth:`execute`.  The ``__call__`` method is
    provided so instances satisfy :class:`NodeHandlerProtocol` and can
    be used with the ``@register_node`` decorator via
    ``register_node("my_type", MyHandler())``.
    """

    node_type: str
    """Machine-readable type string, e.g. ``"search"`` or ``"compare"``."""

    @abstractmethod
    async def execute(
        self,
        config: NodeConfig,
        track: TrackMetadata,
        inputs: NodeInputs,
    ) -> NodeOutputs:
        """Run the node logic and return outputs keyed by source handle."""
        ...

    async def __call__(
        self,
        config: NodeConfig,
        track: TrackMetadata,
        inputs: NodeInputs,
    ) -> NodeOutputs:
        return await self.execute(config, track, inputs)
