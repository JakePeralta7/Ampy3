"""Match rule request/response schemas."""
from __future__ import annotations

from typing import Any

from pydantic import BaseModel


class MatchRuleOut(BaseModel):
    """Output schema for a match rule."""

    id: int
    name: str
    priority: int
    is_active: bool
    is_default: bool
    yaml_content: str
    canvas: dict[str, Any]  # Auto-generated from yaml_content on load
    created_at: str
    updated_at: str

    model_config = {"from_attributes": True}


class MatchRuleCreate(BaseModel):
    """Input schema for creating a new user-defined match rule."""

    name: str
    yaml_content: str


class MatchRuleUpdate(BaseModel):
    """Input schema for updating a match rule.

    Default rules can only toggle ``is_active``; all other fields
    are blocked for default rules.
    """

    name: str | None = None
    is_active: bool | None = None
    yaml_content: str | None = None


class MatchRuleClone(BaseModel):
    """Input schema for cloning a default rule."""

    name: str | None = None  # Override name; defaults to "<original> (copy)"


class ReorderInput(BaseModel):
    """Input schema for reordering match rules."""

    id: int
    priority: int


class TrackTestInput(BaseModel):
    """Input schema for a track to test against rules."""

    title: str | None = None
    artist_name: str | None = None
    album_name: str | None = None
    duration_ms: int | None = None
    source_id: str | None = None


class TestRequest(BaseModel):
    """Input schema for testing match rules."""

    track: TrackTestInput
    rule_ids: list[int] | None = None


class MatchRuleTestResult(BaseModel):
    """Result of testing a track against match rules."""

    rule_id: int
    rule_name: str
    rule_priority: int
    matched: bool
    result: dict | None = None
    error: str | None = None


class MatchRuleTestResponse(BaseModel):
    """Response from testing match rules."""

    traces: list[dict]
    matches: list[MatchRuleTestResult]
    match_results: list[dict]


class MatchRuleDeleteResponse(BaseModel):
    """Response after deleting a match rule."""

    success: bool


def _model_to_out(rule: Any) -> MatchRuleOut:
    """Convert a MatchRule ORM model to MatchRuleOut schema.

    The canvas dict is computed on-the-fly from the stored yaml_content
    using auto-layout — positions are never persisted.
    """
    from src.app.match_rules.parser import yaml_to_canvas
    from src.app.match_rules.validator import validate_rule_yaml

    created_at_str = ""
    updated_at_str = ""

    if hasattr(rule, "created_at") and rule.created_at:
        try:
            created_at_str = rule.created_at.isoformat()
        except (AttributeError, ValueError):
            created_at_str = str(rule.created_at)

    if hasattr(rule, "updated_at") and rule.updated_at:
        try:
            updated_at_str = rule.updated_at.isoformat()
        except (AttributeError, ValueError):
            updated_at_str = str(rule.updated_at)

    # Compute canvas from YAML; fall back to empty canvas on error
    canvas: dict[str, Any] = {"nodes": [], "edges": []}
    if rule.yaml_content:
        try:
            rule_def = validate_rule_yaml(rule.yaml_content)
            canvas = yaml_to_canvas(rule_def)
        except Exception:
            pass  # Malformed rule — canvas stays empty

    return MatchRuleOut(
        id=rule.id,
        name=rule.name,
        priority=rule.priority,
        is_active=rule.is_active,
        is_default=rule.is_default,
        yaml_content=rule.yaml_content or "",
        canvas=canvas,
        created_at=created_at_str,
        updated_at=updated_at_str,
    )
