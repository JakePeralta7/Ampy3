"""Node handler registry."""

from __future__ import annotations

import contextvars
from collections.abc import Callable, Coroutine
from typing import TYPE_CHECKING, Any

from src.app.core.models import TrackMetadata
from src.app.core.nodes.base import NodeConfig, NodeHandlerBase, NodeInputs, NodeOutputs

if TYPE_CHECKING:
    from src.app.core.targets.base import BaseTarget

# Callable form for simple function-based handlers.
NodeHandler = Callable[
    [NodeConfig, TrackMetadata, NodeInputs],
    Coroutine[Any, Any, NodeOutputs],
]

_handlers: dict[str, NodeHandler | NodeHandlerBase] = {}


def register_node(node_type: str, handler: NodeHandler | NodeHandlerBase | None = None):
    """Decorator or direct call to register a node handler by type.

    Usage as decorator::

        @register_node("search")
        async def _handle_search(config, track, inputs): ...

    Usage with a :class:`NodeHandlerBase` instance::

        register_node("search", MySearchHandler())
    """
    if handler is not None:
        _handlers[node_type] = handler
        return handler

    def decorator(fn: NodeHandler | NodeHandlerBase) -> NodeHandler | NodeHandlerBase:
        _handlers[node_type] = fn
        return fn

    return decorator


def get_handler(node_type: str) -> NodeHandler | NodeHandlerBase | None:
    return _handlers.get(node_type)


def get_registered_types() -> list[str]:
    """Return sorted list of all registered node type strings."""
    return sorted(_handlers.keys())


def build_node_type_literal() -> type:
    """Build a ``Literal`` type from all registered node types.

    Must be called **after** all handler submodules have been imported.
    Returns a ``Literal["type_a", "type_b", ...]`` union.
    """
    from typing import Literal

    types = get_registered_types()
    if not types:
        # Fallback so Pydantic doesn't choke on an empty Literal.
        return str  # type: ignore[return-value]
    return Literal[tuple(types)]  # type: ignore[valid-type]


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
