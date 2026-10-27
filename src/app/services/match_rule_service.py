"""MatchRuleService — business logic for user-defined match rules.

All DB access, uniqueness/priority bookkeeping, YAML validation and rule
testing live here so the API layer only translates results into HTTP.
"""

from __future__ import annotations

import logging
from dataclasses import dataclass, field
from typing import Any

from fastapi import HTTPException
from sqlalchemy import func, select
from sqlalchemy.ext.asyncio import AsyncSession

from src.app.core.models import TrackMetadata
from src.app.core.services.matcher import MatchEngine
from src.app.db import AsyncSessionLocal
from src.app.match_rules import ValidationError, validate_rule_yaml
from src.app.models import MatchRule
from src.app.schemas.match_rules import (
    MatchRuleOut,
    MatchRuleTestResponse,
    MatchRuleTestResult,
    MatchRuleUpdate,
    ReorderInput,
    TestRequest,
    _model_to_out,
)
from src.app.services import get_sync_target

logger = logging.getLogger(__name__)


@dataclass
class CloneResult:
    """A cloned rule plus the name of the rule it was cloned from."""

    rule: MatchRuleOut
    source_name: str


@dataclass
class UpdateResult:
    """An updated rule plus a human-readable list of what changed."""

    rule: MatchRuleOut
    changes: list[str] = field(default_factory=list)


@dataclass
class ReorderResult:
    """Every rule in the new order, plus the ids that were actually moved."""

    rules: list[MatchRuleOut]
    requested_ids: list[int] = field(default_factory=list)


# ─── Validation helpers ─────────────────────────────────────────


def _validate_yaml(yaml_content: str) -> None:
    """Validate a rule definition, mapping errors to HTTP 422."""
    try:
        validate_rule_yaml(yaml_content)
    except ValidationError as exc:
        raise HTTPException(status_code=422, detail={"yaml_errors": exc.errors}) from exc


async def _get_rule_or_404(session: AsyncSession, rule_id: int) -> MatchRule:
    result = await session.execute(select(MatchRule).where(MatchRule.id == rule_id))
    rule = result.scalars().first()
    if not rule:
        raise HTTPException(status_code=404, detail="Rule not found")
    return rule


async def _next_priority(session: AsyncSession) -> int:
    result = await session.execute(select(func.coalesce(func.max(MatchRule.priority), -1)))
    return result.scalar() + 1


async def _ensure_name_available(session: AsyncSession, name: str) -> None:
    existing = await session.execute(select(MatchRule.id).where(MatchRule.name == name))
    if existing.scalars().first() is not None:
        raise HTTPException(
            status_code=409,
            detail=f"A rule named '{name}' already exists.",
        )


async def _unique_copy_name(session: AsyncSession, base_name: str) -> str:
    """Return ``"<name> (copy)"``, suffixing a counter until it is unique."""
    new_name = f"{base_name} (copy)"
    suffix = 2
    while (
        await session.execute(select(MatchRule.id).where(MatchRule.name == new_name))
    ).scalars().first() is not None:
        new_name = f"{base_name} (copy {suffix})"
        suffix += 1
    return new_name


# ─── CRUD ───────────────────────────────────────────────────────


async def list_rules() -> list[MatchRuleOut]:
    """Return every rule ordered by priority."""
    async with AsyncSessionLocal() as session:
        result = await session.execute(select(MatchRule).order_by(MatchRule.priority))
        return [_model_to_out(rule) for rule in result.scalars().all()]


async def get_rule(rule_id: int) -> MatchRuleOut:
    """Return one rule or raise 404."""
    async with AsyncSessionLocal() as session:
        return _model_to_out(await _get_rule_or_404(session, rule_id))


async def create_rule(name: str, yaml_content: str) -> MatchRuleOut:
    """Create a new user-defined rule appended after every existing rule."""
    _validate_yaml(yaml_content)

    async with AsyncSessionLocal() as session:
        await _ensure_name_available(session, name)
        rule = MatchRule(
            name=name,
            priority=await _next_priority(session),
            is_active=True,
            is_default=False,
            yaml_content=yaml_content,
        )
        session.add(rule)
        await session.commit()
        await session.refresh(rule)
        return _model_to_out(rule)


async def clone_rule(rule_id: int, name: str | None = None) -> CloneResult:
    """Clone a rule (especially an immutable default) into a user-owned copy."""
    async with AsyncSessionLocal() as session:
        source = await _get_rule_or_404(session, rule_id)
        if name:
            new_name = name
            await _ensure_name_available(session, new_name)
        else:
            new_name = await _unique_copy_name(session, source.name)

        clone = MatchRule(
            name=new_name,
            priority=await _next_priority(session),
            is_active=True,
            is_default=False,
            yaml_content=source.yaml_content,
        )
        session.add(clone)
        await session.commit()
        await session.refresh(clone)
        return CloneResult(rule=_model_to_out(clone), source_name=source.name)


async def reorder_rules(body: list[ReorderInput]) -> ReorderResult:
    """Assign sequential priorities to non-default rules in request order."""
    async with AsyncSessionLocal() as session:
        all_rules_result = await session.execute(select(MatchRule))
        all_rules = {rule.id: rule for rule in all_rules_result.scalars().all()}

        default_max = -1
        for rule in all_rules.values():
            if rule.is_default and rule.priority > default_max:
                default_max = rule.priority

        requested_ids = [item.id for item in body if item.id in all_rules]
        next_priority = default_max + 1
        for rule_id in requested_ids:
            rule = all_rules[rule_id]
            if not rule.is_default:
                rule.priority = next_priority
                next_priority += 1

        await session.commit()

        result = await session.execute(select(MatchRule).order_by(MatchRule.priority))
        rules = [_model_to_out(rule) for rule in result.scalars().all()]
        return ReorderResult(rules=rules, requested_ids=requested_ids)


async def update_rule(rule_id: int, body: MatchRuleUpdate) -> UpdateResult:
    """Update a rule, enforcing default-rule immutability and unique names."""
    async with AsyncSessionLocal() as session:
        rule = await _get_rule_or_404(session, rule_id)

        if rule.is_default:
            blocked = []
            if body.name is not None and body.name != rule.name:
                blocked.append("name")
            if body.yaml_content is not None:
                blocked.append("yaml_content")
            if blocked:
                raise HTTPException(
                    status_code=409,
                    detail=(
                        f"Default rules are immutable — cannot modify: {', '.join(blocked)}. "
                        "Clone this rule to create an editable copy."
                    ),
                )

        if body.yaml_content is not None:
            _validate_yaml(body.yaml_content)

        old_name = rule.name
        old_active = rule.is_active

        if body.name is not None and body.name != rule.name:
            conflicting = await session.execute(
                select(MatchRule.id).where(MatchRule.name == body.name)
            )
            if conflicting.scalars().first() is not None:
                raise HTTPException(
                    status_code=409,
                    detail=f"A rule named '{body.name}' already exists.",
                )
            rule.name = body.name
        if body.is_active is not None:
            rule.is_active = body.is_active
        if body.yaml_content is not None:
            rule.yaml_content = body.yaml_content

        await session.commit()
        await session.refresh(rule)

        changes = []
        if body.is_active is not None and body.is_active != old_active:
            changes.append("activated" if body.is_active else "deactivated")
        if body.name is not None and body.name != old_name:
            changes.append(f"renamed to {body.name}")
        if body.yaml_content is not None:
            changes.append("YAML updated")

        return UpdateResult(rule=_model_to_out(rule), changes=changes)


async def delete_rule(rule_id: int) -> str:
    """Delete a non-default rule and return its name (for audit logging)."""
    async with AsyncSessionLocal() as session:
        rule = await _get_rule_or_404(session, rule_id)
        if rule.is_default:
            raise HTTPException(
                status_code=409,
                detail="Default rules cannot be deleted. Disable or clone them instead.",
            )

        rule_name = rule.name
        await session.delete(rule)
        await session.commit()
        return rule_name


# ─── Testing ────────────────────────────────────────────────────


def _track_from_request(body: TestRequest) -> TrackMetadata:
    track = body.track
    return TrackMetadata(
        title=track.title or "",
        artist_name=track.artist_name or "",
        album_name=track.album_name or "",
        duration_ms=track.duration_ms,
        source_id=track.source_id,
        mbid=track.mbid,
        artist_mbid=track.artist_mbid,
        album_mbid=track.album_mbid,
    )


def _match_step(trace: dict[str, Any]) -> dict[str, Any] | None:
    match_step = None
    for step in trace.get("steps") or []:
        if isinstance(step, dict) and step.get("outputs"):
            match_step = step
    return match_step


async def test_rules(body: TestRequest) -> MatchRuleTestResponse:
    """Trace the selected rules and (when none are given) run the engine."""
    track = _track_from_request(body)

    if body.rule_ids:
        async with AsyncSessionLocal() as session:
            result = await session.execute(
                select(MatchRule.id).where(MatchRule.id.in_(body.rule_ids))
            )
            found = set(result.scalars().all())
        missing = [rule_id for rule_id in body.rule_ids if rule_id not in found]
        if missing:
            raise HTTPException(status_code=404, detail=f"Rule(s) not found: {missing}")

    target = await get_sync_target(body.target_id or "Plex")
    engine = MatchEngine(target)

    traces = await engine.trace(track, rule_ids=body.rule_ids)

    matches = []
    for trace in traces:
        step = _match_step(trace)
        match_result = step.get("outputs", {}).get("out") if step else None
        matches.append(
            MatchRuleTestResult(
                rule_id=trace["rule_id"],
                rule_name=trace["rule_name"],
                rule_priority=trace["rule_priority"],
                matched=match_result is not None,
                result=match_result,
                error=trace.get("error"),
            )
        )

    match_results = []
    if not body.rule_ids:
        match_results = await engine.run(track)

    return MatchRuleTestResponse(
        traces=traces,
        matches=matches,
        match_results=match_results,
    )
