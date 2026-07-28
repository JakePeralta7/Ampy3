"""Logic operation node handler."""

from __future__ import annotations

from src.app.core.models import TrackMetadata
from src.app.core.nodes.base import NodeHandlerBase, NodeInputs, NodeOutputs
from src.app.core.nodes.registry import register_node


@register_node("logic_op")
class LogicOpNode(NodeHandlerBase):
    async def execute(self, track: TrackMetadata, inputs: NodeInputs) -> NodeOutputs:
        operation = self._config.get("operation", "and")
        a = inputs.get("a", inputs.get("in"))
        b = inputs.get("b", self._config.get("value"))

        if operation == "and":
            return {"out": bool(a) and bool(b)}
        if operation == "or":
            return {"out": bool(a) or bool(b)}
        if operation == "not":
            return {"out": not bool(inputs.get("in", False))}
        if operation == "if_else":
            condition = inputs.get("condition", False)
            true_val = inputs.get("true", inputs.get("in"))
            false_val = inputs.get("false", inputs.get("in"))
            return {
                "true": true_val if condition else None,
                "false": false_val if not condition else None,
            }
        return {"out": False}
