"""Hierarchical left-to-right auto-layout for rule node graphs.

Implements a simplified Sugiyama-style layered layout:

  1. BFS from source nodes (track_source) to assign each node a layer.
  2. Within each layer, nodes are ordered by the order they were defined.
  3. X = layer_index * H_SPACING
  4. Y = node_index_in_layer * V_SPACING  (centred vertically)

The result is a dict mapping node_id -> {"x": float, "y": float}.
No manual coordinates are ever stored — this is computed fresh whenever
a canvas is needed (e.g. GET /api/v1/match-rules/:id).
"""

from __future__ import annotations

from collections import deque

# Pixels between layer columns (horizontal)
H_SPACING = 220
# Pixels between nodes in the same column (vertical)
V_SPACING = 120
# Left / top margin
MARGIN_X = 80
MARGIN_Y = 80


def auto_layout(
    node_ids: list[str],
    edges: list[dict],
) -> dict[str, dict[str, float]]:
    """Compute {node_id: {x, y}} for every node.

    Parameters
    ----------
    node_ids:
        Ordered list of node identifiers (order used as tiebreaker within a layer).
    edges:
        List of edge dicts with keys ``from`` / ``source`` and
        ``to`` / ``target`` (either convention works).
    """
    if not node_ids:
        return {}

    # Normalise edge representation — accept both "from"/"to" and "source"/"target"
    def _src(e: dict) -> str:
        return e.get("from") or e.get("from_node") or e.get("source", "")

    def _tgt(e: dict) -> str:
        return e.get("to") or e.get("to_node") or e.get("target", "")

    # Build adjacency structures
    children: dict[str, list[str]] = {n: [] for n in node_ids}
    in_degree: dict[str, int] = {n: 0 for n in node_ids}

    for edge in edges:
        src, tgt = _src(edge), _tgt(edge)
        if src in children and tgt in children:
            children[src].append(tgt)
            in_degree[tgt] = in_degree.get(tgt, 0) + 1

    # BFS layer assignment starting from all source nodes (in_degree == 0)
    layer: dict[str, int] = {}
    queue: deque[str] = deque()

    # Seed with nodes that have no incoming edges
    for node_id in node_ids:
        if in_degree.get(node_id, 0) == 0:
            layer[node_id] = 0
            queue.append(node_id)

    # If there are no source nodes (shouldn't happen in valid rules) fall back
    if not queue:
        for node_id in node_ids:
            layer[node_id] = 0
            queue.append(node_id)

    while queue:
        current = queue.popleft()
        current_layer = layer[current]
        for child in children.get(current, []):
            # Assign the deepest layer seen (longest path from source)
            new_layer = current_layer + 1
            if child not in layer or layer[child] < new_layer:
                layer[child] = new_layer
                queue.append(child)

    # Any nodes still unassigned (disconnected — should be caught by validator)
    for node_id in node_ids:
        if node_id not in layer:
            layer[node_id] = 0

    # Group nodes by layer, preserving original definition order within each layer
    layers: dict[int, list[str]] = {}
    for node_id in node_ids:  # iterate in definition order for stable positions
        layer_idx = layer[node_id]
        layers.setdefault(layer_idx, []).append(node_id)

    # Assign pixel positions
    max_layer = max(layers.keys()) if layers else 0
    positions: dict[str, dict[str, float]] = {}

    for layer_idx in range(max_layer + 1):
        nodes_in_layer = layers.get(layer_idx, [])

        for node_idx, node_id in enumerate(nodes_in_layer):
            positions[node_id] = {
                "x": float(MARGIN_X + layer_idx * H_SPACING),
                "y": float(MARGIN_Y + node_idx * V_SPACING),
            }

    return positions
