"""Match rule request/response schemas."""

from pydantic import BaseModel


class MatchRuleOut(BaseModel):
    """Output schema for a match rule."""
    id: int
    name: str
    priority: int
    is_active: bool
    is_default: bool
    canvas: dict
    created_at: str
    updated_at: str

    model_config = {"from_attributes": True}


class MatchRuleCreate(BaseModel):
    """Input schema for creating a match rule."""
    name: str


class MatchRuleUpdate(BaseModel):
    """Input schema for updating a match rule."""
    name: str | None = None
    is_active: bool | None = None
    canvas: dict | None = None


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


def _model_to_out(rule) -> MatchRuleOut:
    """Convert a MatchRule ORM model to MatchRuleOut schema."""
    from src.app.models import MatchRule

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

    return MatchRuleOut(
        id=rule.id,
        name=rule.name,
        priority=rule.priority,
        is_active=rule.is_active,
        is_default=rule.is_default,
        canvas=rule.canvas or {},
        created_at=created_at_str,
        updated_at=updated_at_str,
    )
