"""LangGraph agent tools for reading, creating, editing, and testing match rules.

All database operations use the async SQLAlchemy session.
`test_match_rule` wires into the same MatchEngine used by the REST API.
"""

from __future__ import annotations

import logging

from langchain_core.tools import tool
from sqlalchemy import func, select

from src.app.db import AsyncSessionLocal
from src.app.match_rules import ValidationError, validate_rule_yaml
from src.app.models import MatchRule
from src.app.services.audit import log_event

logger = logging.getLogger(__name__)


@tool
async def list_match_rules() -> list[dict]:
    """List all match rules ordered by priority.

    Returns id, name, priority, is_active, is_default, and a short yaml_content
    preview (first 200 chars) for each rule.
    """
    async with AsyncSessionLocal() as session:
        result = await session.execute(select(MatchRule).order_by(MatchRule.priority))
        rules = result.scalars().all()

    return [
        {
            "id": r.id,
            "name": r.name,
            "priority": r.priority,
            "is_active": r.is_active,
            "is_default": r.is_default,
            "yaml_preview": (r.yaml_content or "")[:200],
        }
        for r in rules
    ]


@tool
async def get_match_rule(rule_id: int) -> dict:
    """Get the full details of a single match rule, including its complete YAML.

    Args:
        rule_id: The integer ID of the match rule.
    """
    async with AsyncSessionLocal() as session:
        result = await session.execute(select(MatchRule).where(MatchRule.id == rule_id))
        rule = result.scalar_one_or_none()

    if not rule:
        return {"error": f"Match rule {rule_id} not found"}

    return {
        "id": rule.id,
        "name": rule.name,
        "priority": rule.priority,
        "is_active": rule.is_active,
        "is_default": rule.is_default,
        "yaml_content": rule.yaml_content or "",
        "created_at": rule.created_at.isoformat() if rule.created_at else None,
        "updated_at": rule.updated_at.isoformat() if rule.updated_at else None,
    }


@tool
async def create_match_rule(name: str, yaml_content: str) -> dict:
    """Create a new user-defined match rule from a YAML definition.

    The YAML is validated before being persisted. Returns the new rule's id on
    success, or a list of validation errors on failure.

    A minimal rule YAML looks like:
        name: "My Rule"
        description: "Simple title+artist match"
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
              fields_to_match: [title, artist_name]
              threshold: 0.70
              weights: {title: 60, artist_name: 40}
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

    Args:
        name: Human-readable name for the rule (max 100 chars).
        yaml_content: Full YAML rule definition string.
    """
    try:
        validate_rule_yaml(yaml_content)
    except ValidationError as exc:
        return {"error": "YAML validation failed", "yaml_errors": exc.errors}

    async with AsyncSessionLocal() as session:
        max_priority_result = await session.execute(
            select(func.coalesce(func.max(MatchRule.priority), -1))
        )
        next_priority = max_priority_result.scalar() + 1

        rule = MatchRule(
            name=name,
            priority=next_priority,
            is_active=True,
            is_default=False,
            yaml_content=yaml_content,
        )
        session.add(rule)
        await session.commit()
        await session.refresh(rule)

    await log_event(
        event_type="match_rule.created",
        summary=f"Match rule created by agent: {name}",
        resource_type="match_rule",
        resource_id=str(rule.id),
    )

    return {
        "id": rule.id,
        "name": rule.name,
        "priority": rule.priority,
        "is_active": rule.is_active,
        "message": f"Rule '{name}' created successfully with id {rule.id}.",
    }


@tool
async def update_match_rule(
    rule_id: int,
    name: str | None = None,
    is_active: bool | None = None,
    yaml_content: str | None = None,
) -> dict:
    """Update an existing match rule.

    Default rules (is_default=True) are immutable — only is_active can be toggled.
    To edit a default rule's YAML, use create_match_rule to create a new one based
    on its YAML.

    Args:
        rule_id: The integer ID of the match rule to update.
        name: New name for the rule (optional, blocked for default rules).
        is_active: Enable or disable the rule (optional).
        yaml_content: Replacement YAML definition (optional, validated before saving,
                      blocked for default rules).
    """
    async with AsyncSessionLocal() as session:
        result = await session.execute(select(MatchRule).where(MatchRule.id == rule_id))
        rule = result.scalar_one_or_none()

        if not rule:
            return {"error": f"Match rule {rule_id} not found"}

        if rule.is_default:
            blocked = []
            if name is not None and name != rule.name:
                blocked.append("name")
            if yaml_content is not None:
                blocked.append("yaml_content")
            if blocked:
                return {
                    "error": (
                        f"Default rules are immutable — cannot modify: {', '.join(blocked)}. "
                        "Use create_match_rule to make a new editable copy."
                    )
                }

        if yaml_content is not None:
            try:
                validate_rule_yaml(yaml_content)
            except ValidationError as exc:
                return {"error": "YAML validation failed", "yaml_errors": exc.errors}

        changes = []
        if name is not None and name != rule.name:
            rule.name = name
            changes.append("name")
        if is_active is not None and is_active != rule.is_active:
            rule.is_active = is_active
            changes.append("is_active")
        if yaml_content is not None:
            rule.yaml_content = yaml_content
            changes.append("yaml_content")

        await session.commit()
        await session.refresh(rule)

    if changes:
        await log_event(
            event_type="match_rule.updated",
            summary=f"Match rule updated by agent ({', '.join(changes)}): {rule.name}",
            resource_type="match_rule",
            resource_id=str(rule_id),
        )

    return {
        "id": rule.id,
        "name": rule.name,
        "priority": rule.priority,
        "is_active": rule.is_active,
        "changes_applied": changes,
        "message": f"Rule updated. Changes: {', '.join(changes) or 'none'}.",
    }


@tool
async def test_match_rule(
    title: str,
    artist_name: str,
    album_name: str = "",
    duration_ms: int | None = None,
    rule_ids: list[int] | None = None,
    trace_detail: bool = True,
) -> dict:
    """Test match rules against a track to diagnose why it may have failed to match.

    Runs the MatchEngine against the provided track metadata and returns per-rule
    trace results showing exactly which steps passed or failed, with detailed node-by-node
    execution traces.

    Use this to:
    - Understand why an unmatched track wasn't found (pass its source metadata)
    - Verify that a rule change would now correctly match a track
    - Compare results across multiple rules at once
    - Inspect detailed step-by-step traces to debug rule behavior

    Args:
        title: Track title (e.g. "Bohemian Rhapsody").
        artist_name: Artist name (e.g. "Queen").
        album_name: Album name (optional, helps narrow results).
        duration_ms: Track duration in milliseconds (optional).
        rule_ids: List of specific rule IDs to test (optional). If omitted, all
                  active rules are tested and the first match is returned.
        trace_detail: Include full step-by-step execution traces (default: True).
                     If False, returns summary results only.

    Returns:
        dict containing:
        - track_tested: Input track metadata
        - per_rule_results: List of results per rule, each including:
          - rule_id, rule_name, rule_priority
          - matched: bool indicating if rule matched
          - match_result: Matched Plex track (if any)
          - steps_trace: List of node execution details (when trace_detail=True)
          - failure_reason: Diagnostic reason if matched=False
          - error: Exception message if rule failed
        - overall_matched: True if any rule matched
        - winning_match: First matched track (when rule_ids is None)
    """
    from src.app.core.models import TrackMetadata
    from src.app.core.services.matcher import MatchEngine
    from src.app.services import get_sync_target

    track = TrackMetadata(
        title=title,
        artist_name=artist_name,
        album_name=album_name or None,
        duration_ms=duration_ms,
    )

    def _extract_failure_reason(trace_data: dict) -> str:
        """Extract human-readable failure reason from trace data."""
        steps = trace_data.get("steps") or []

        # Find first failed step or last step
        for step in steps:
            if not isinstance(step, dict):
                continue
            step_name = step.get("name", "unknown")
            error = step.get("error")
            outputs = step.get("outputs", {})

            # Check if this step failed
            if error:
                return f"{step_name} step failed: {error}"

            # For outputs, check for "false" or empty results
            if outputs:
                if outputs.get("out") is False:
                    return f"{step_name} step returned false (no match)"
                if outputs.get("results") == [] or outputs.get("results") is None:
                    return f"{step_name} step returned no results"
                if outputs.get("match") is False:
                    return f"{step_name} step did not match"

        if trace_data.get("error"):
            return f"Rule execution error: {trace_data['error']}"

        return "Unknown failure reason"

    def _build_steps_trace(steps_list: list) -> list[dict]:
        """Build a clean, readable steps trace for output."""
        trace = []
        for step in steps_list or []:
            if not isinstance(step, dict):
                continue

            step_item = {
                "node": step.get("name", "unknown"),
                "inputs": step.get("inputs", {}),
                "outputs": step.get("outputs", {}),
            }
            if step.get("error"):
                step_item["error"] = step["error"]

            trace.append(step_item)

        return trace

    try:
        plex_target = await get_sync_target()
        engine = MatchEngine(plex_target)

        traces = await engine.trace(track, rule_ids=rule_ids)

        per_rule = []
        for t in traces:
            match_step = None
            for step in t.get("steps") or []:
                if isinstance(step, dict) and step.get("outputs"):
                    match_step = step

            result = match_step.get("outputs", {}).get("out") if match_step else None
            matched = result is not None

            rule_result = {
                "rule_id": t["rule_id"],
                "rule_name": t["rule_name"],
                "rule_priority": t["rule_priority"],
                "matched": matched,
            }

            # Include detailed trace if requested
            if trace_detail:
                rule_result["steps_trace"] = _build_steps_trace(t.get("steps", []))

            # Add match result if found
            if matched:
                rule_result["match_result"] = result
            else:
                # Extract failure reason
                rule_result["failure_reason"] = _extract_failure_reason(t)

            # Include error if rule execution failed
            if t.get("error"):
                rule_result["error"] = t["error"]

            per_rule.append(rule_result)

        # If no specific rule_ids, also run the full engine to get the winning match
        winning_match = None
        if not rule_ids:
            match_results = await engine.run(track)
            if match_results:
                winning_match = match_results[0]

        return {
            "track_tested": {
                "title": title,
                "artist_name": artist_name,
                "album_name": album_name,
                "duration_ms": duration_ms,
            },
            "per_rule_results": per_rule,
            "overall_matched": any(r["matched"] for r in per_rule),
            "winning_match": winning_match,
        }
    except Exception as exc:
        logger.error("test_match_rule failed: %s", exc, exc_info=True)
        return {"error": str(exc)}
