"""Pydantic schema for YAML-based match rule definitions.

A rule YAML looks like:

    name: "Quick Start"
    description: "Simple search and compare"
    nodes:
      source:
        type: track_source
      search:
        type: search
        config:
          fields_to_search: [title, artist, album]
          max_results: 50
      compare:
        type: compare
        config:
          fields_to_match: [title, artist_name, album_name]
          threshold: 0.75
          weights: {title: 50, artist_name: 25, album_name: 25}
      output:
        type: match_output
    edges:
      - from: source
        to: search
      - from: search
        to: compare
        source_handle: out
        target_handle: candidates
      - from: compare
        to: output

Node keys are semantic (user-chosen) identifiers. Positions are never
stored in YAML — the auto-layout algorithm generates them at render time.
"""
from __future__ import annotations

from typing import Any, Literal

from pydantic import BaseModel, Field, field_validator, model_validator

# All registered node types.
NodeType = Literal[
    "track_source",
    "constant",
    "transform",
    "search",
    "compare",
    "filter",
    "pick_best",
    "sort_by_score",
    "similarity",
    "threshold",
    "logic_op",
    "match_output",
    "search_musicbrainz",
]


class NodeDef(BaseModel):
    """A single node inside a rule canvas."""

    type: NodeType
    config: dict[str, Any] = Field(default_factory=dict)


class EdgeDef(BaseModel):
    """A directed edge connecting two nodes."""

    from_node: str = Field(alias="from")
    to_node: str = Field(alias="to")
    source_handle: str = "out"
    target_handle: str = "in"

    model_config = {"populate_by_name": True}


class RuleDefinition(BaseModel):
    """Complete YAML rule definition (no positions)."""

    name: str = Field(min_length=1, max_length=100)
    description: str | None = None
    nodes: dict[str, NodeDef]
    edges: list[EdgeDef]

    @field_validator("nodes")
    @classmethod
    def nodes_not_empty(cls, v: dict) -> dict:
        if not v:
            raise ValueError("A rule must define at least one node.")
        return v

    @model_validator(mode="after")
    def edge_endpoints_exist(self) -> RuleDefinition:
        node_ids = set(self.nodes.keys())
        for edge in self.edges:
            if edge.from_node not in node_ids:
                raise ValueError(
                    f"Edge references unknown source node '{edge.from_node}'. "
                    f"Available nodes: {sorted(node_ids)}"
                )
            if edge.to_node not in node_ids:
                raise ValueError(
                    f"Edge references unknown target node '{edge.to_node}'. "
                    f"Available nodes: {sorted(node_ids)}"
                )
        return self
