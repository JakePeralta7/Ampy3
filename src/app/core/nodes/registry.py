"""Node handler registry with OOP registration pattern."""

from __future__ import annotations

import contextvars
import logging
from collections.abc import Callable
from typing import TYPE_CHECKING, Any

from src.app.core.nodes.base import NodeConfig, NodeHandlerBase, NodeInputs, NodeOutputs

if TYPE_CHECKING:
    from src.app.core.models import TrackMetadata
    from src.app.core.targets.base import BaseTarget

logger = logging.getLogger(__name__)


class NodeRegistry:
    """Central registry of node handler classes.

    Node types self-register via the ``@register_node`` decorator.
    """

    _nodes: dict[str, type[NodeHandlerBase]] = {}

    @classmethod
    def register(cls, node_type: str, node_class: type[NodeHandlerBase]) -> None:
        """Register a node handler class under *node_type*."""
        if node_type in cls._nodes:
            logger.warning(
                "Overwriting existing node registration for '%s': %s -> %s",
                node_type,
                cls._nodes[node_type].__name__,
                node_class.__name__,
            )
        cls._nodes[node_type] = node_class
        logger.debug("Registered node '%s' -> %s", node_type, node_class.__name__)

    @classmethod
    def get(cls, node_type: str) -> type[NodeHandlerBase]:
        """Return the node handler class for *node_type*.

        Raises ``KeyError`` if the node type is not registered.
        """
        try:
            return cls._nodes[node_type]
        except KeyError:
            available = ", ".join(sorted(cls._nodes)) or "(none)"
            raise KeyError(f"Unknown node type '{node_type}'. Available: {available}") from None

    @classmethod
    def create(cls, node_type: str, config: NodeConfig) -> NodeHandlerBase:
        """Create a handler instance for *node_type* with the given config."""
        return cls.get(node_type)(config)

    @classmethod
    def list_nodes(cls) -> list[dict[str, str]]:
        """Return metadata for all registered node types."""
        return [
            {"type": node_type, "name": node_class.__name__}
            for node_type, node_class in cls._nodes.items()
        ]


def register_node(
    node_type: str,
    node_class: type[NodeHandlerBase] | None = None,
) -> type[NodeHandlerBase] | Callable[[type[NodeHandlerBase]], type[NodeHandlerBase]]:
    """Decorator or direct call to register a node handler class.

    Usage as decorator::

        @register_node("search")
        class SearchNode(NodeHandlerBase):
            ...

    Usage as direct call::

        register_node("search", SearchNode)
    """
    if node_class is not None:
        node_class.node_type = node_type  # type: ignore[misc]
        NodeRegistry.register(node_type, node_class)
        return node_class

    def decorator(cls: type[NodeHandlerBase]) -> type[NodeHandlerBase]:
        cls.node_type = node_type  # type: ignore[misc]
        NodeRegistry.register(node_type, cls)
        return cls

    return decorator


def get_registered_types() -> list[str]:
    """Return sorted list of all registered node type strings."""
    return sorted(NodeRegistry._nodes.keys())


def build_node_type_literal() -> type:
    """Build a ``Literal`` type from all registered node types.

    Must be called **after** all handler submodules have been imported.
    Returns a ``Literal["type_a", "type_b", ...]`` union.
    """
    from typing import Literal

    types = get_registered_types()
    if not types:
        return str  # type: ignore[return-value]
    return Literal[tuple(types)]  # type: ignore[misc]


# ─── Target Context ───────────────────────────────────────────

current_target: contextvars.ContextVar[BaseTarget | None] = contextvars.ContextVar(
    "current_target",
    default=None,
)


def get_current_target() -> BaseTarget:
    """Get the sync target for the current execution context.

    Node handlers call this instead of importing a specific target client.
    Raises ``RuntimeError`` if no target is set.
    """
    target = current_target.get()
    if target is None:
        raise RuntimeError(
            "No sync target available. Ensure NodeGraphExecutor receives a BaseTarget."
        )
    return target
