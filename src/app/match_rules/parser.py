"""YAML ↔ canvas conversion for match rules.

``yaml_to_canvas`` parses a YAML string into the internal canvas dict
(with auto-generated positions) that the NodeGraphExecutor consumes.

``canvas_to_yaml`` serialises a canvas dict back to a clean YAML string
(positions are stripped — they are never stored).
"""

from __future__ import annotations

from typing import Any

import yaml

from src.app.match_rules.layout import auto_layout
from src.app.match_rules.schema import RuleDefinition


def yaml_to_canvas(rule: RuleDefinition) -> dict[str, Any]:
    """Convert a validated :class:`RuleDefinition` into a canvas dict.

    The canvas is the format consumed by :class:`NodeGraphExecutor`:
    ``{"nodes": [...], "edges": [...]}`` where every node has a
    ``position`` field computed by :func:`auto_layout`.

    This function is called on every GET — positions are never stored.
    """
    node_ids = list(rule.nodes.keys())

    # Build the edge list in the format expected by auto_layout
    raw_edges = [{"from": e.from_node, "to": e.to_node} for e in rule.edges]

    positions = auto_layout(node_ids, raw_edges)

    canvas_nodes = [
        {
            "id": node_id,
            "type": node_def.type,
            "position": positions.get(node_id, {"x": 0.0, "y": 0.0}),
            "config": node_def.config,
        }
        for node_id, node_def in rule.nodes.items()
    ]

    canvas_edges = [
        {
            "id": f"e_{e.from_node}_{e.to_node}",
            "source": e.from_node,
            "target": e.to_node,
            "sourceHandle": e.source_handle,
            "targetHandle": e.target_handle,
        }
        for e in rule.edges
    ]

    return {"nodes": canvas_nodes, "edges": canvas_edges}


def canvas_to_yaml(
    canvas: dict[str, Any],
    *,
    name: str = "",
    description: str | None = None,
) -> str:
    """Serialise a canvas dict (React Flow format) back to a YAML string.

    Positions are stripped; only node type and config are preserved.
    Edges are converted to the ``from`` / ``to`` convention.
    """
    nodes_yaml: dict[str, Any] = {}
    for node in canvas.get("nodes", []):
        node_id = node.get("id") or node.get("data", {}).get("id", "unknown")
        nodes_yaml[node_id] = {
            "type": node.get("type") or node.get("data", {}).get("type", ""),
        }
        config = node.get("config") or node.get("data", {}).get("config", {})
        if config:
            nodes_yaml[node_id]["config"] = config

    edges_yaml = []
    for edge in canvas.get("edges", []):
        entry: dict[str, Any] = {
            "from": edge.get("source") or edge.get("from_node") or edge.get("from", ""),
            "to": edge.get("target") or edge.get("to_node") or edge.get("to", ""),
        }
        src_handle = edge.get("sourceHandle") or edge.get("source_handle", "out")
        tgt_handle = edge.get("targetHandle") or edge.get("target_handle", "in")
        # Only include handles if non-default to keep YAML tidy
        if src_handle != "out":
            entry["source_handle"] = src_handle
        if tgt_handle != "in":
            entry["target_handle"] = tgt_handle
        edges_yaml.append(entry)

    rule: dict[str, Any] = {}
    if name:
        rule["name"] = name
    if description:
        rule["description"] = description
    rule["nodes"] = nodes_yaml
    rule["edges"] = edges_yaml

    return yaml.dump(rule, allow_unicode=True, sort_keys=False, default_flow_style=False)
