"""Validation for YAML match rule definitions.

Checks performed (in order):
  1. YAML is parseable and matches the RuleDefinition schema.
  2. Exactly one ``track_source`` node exists.
  3. At least one ``match_output`` node exists.
  4. Edge endpoints reference existing nodes (enforced by schema).
  5. No cycles (graph must be a DAG).
  6. No orphaned nodes — every node is reachable from a ``track_source``
     AND every node can reach a ``match_output``.

Rules that fail any check are rejected at the API boundary; they are never
persisted to the database.
"""

from __future__ import annotations

from collections import deque

import yaml

from src.app.match_rules.schema import RuleDefinition


class ValidationError(Exception):
    """Raised when a rule YAML fails validation.

    ``errors`` is a list of human-readable problem descriptions.
    """

    def __init__(self, errors: list[str]) -> None:
        self.errors = errors
        super().__init__("; ".join(errors))


def validate_rule_yaml(yaml_content: str) -> RuleDefinition:
    """Parse, schema-validate, and graph-validate a rule YAML string.

    Returns the parsed :class:`RuleDefinition` on success.
    Raises :class:`ValidationError` with a list of errors on failure.
    """
    errors: list[str] = []

    # ── 1. Parse YAML ──────────────────────────────────────────────────────
    try:
        raw = yaml.safe_load(yaml_content)
    except yaml.YAMLError as exc:
        raise ValidationError([f"YAML parse error: {exc}"]) from exc

    if not isinstance(raw, dict):
        raise ValidationError(["YAML must be a mapping (dict) at the top level."])

    # ── 2. Schema validation ────────────────────────────────────────────────
    try:
        rule = RuleDefinition.model_validate(raw)
    except Exception as exc:
        raise ValidationError([f"Schema error: {exc}"]) from exc

    node_ids = list(rule.nodes.keys())
    node_types = {nid: ndef.type for nid, ndef in rule.nodes.items()}

    # ── 3. Structural checks ───────────────────────────────────────────────
    sources = [n for n, t in node_types.items() if t == "track_source"]
    outputs = [n for n, t in node_types.items() if t == "match_output"]

    if len(sources) != 1:
        errors.append(
            f"A rule must have exactly one 'track_source' node "
            f"(found {len(sources)}: {sources or 'none'})."
        )
    if not outputs:
        errors.append("A rule must have at least one 'match_output' node.")

    # ── 4. Build adjacency for graph checks ───────────────────────────────
    children: dict[str, list[str]] = {n: [] for n in node_ids}
    parents: dict[str, list[str]] = {n: [] for n in node_ids}

    for edge in rule.edges:
        children[edge.from_node].append(edge.to_node)
        parents[edge.to_node].append(edge.from_node)

    # ── 5. Cycle detection (DFS) ───────────────────────────────────────────
    visited: set[str] = set()
    in_stack: set[str] = set()

    def _has_cycle(node: str) -> bool:
        visited.add(node)
        in_stack.add(node)
        for child in children.get(node, []):
            if child not in visited:
                if _has_cycle(child):
                    return True
            elif child in in_stack:
                return True
        in_stack.discard(node)
        return False

    for n in node_ids:
        if n not in visited and _has_cycle(n):
            errors.append(
                "Rule contains a cycle. Match rules must be directed acyclic graphs (DAGs)."
            )
            break

    # ── 6. Orphan detection ────────────────────────────────────────────────
    # Forward reachability: nodes reachable from any track_source
    forward_reachable: set[str] = set()
    q: deque[str] = deque(sources)
    while q:
        cur = q.popleft()
        if cur in forward_reachable:
            continue
        forward_reachable.add(cur)
        for child in children.get(cur, []):
            q.append(child)

    # Backward reachability: nodes that can reach any match_output
    backward_reachable: set[str] = set()
    q = deque(outputs)
    while q:
        cur = q.popleft()
        if cur in backward_reachable:
            continue
        backward_reachable.add(cur)
        for parent in parents.get(cur, []):
            q.append(parent)

    orphaned = [n for n in node_ids if n not in forward_reachable or n not in backward_reachable]
    if orphaned:
        errors.append(
            f"Orphaned node(s) detected (not connected to both a source and an output): "
            f"{orphaned}. Remove them or wire them into the graph."
        )

    if errors:
        raise ValidationError(errors)

    return rule
