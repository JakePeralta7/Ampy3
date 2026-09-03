"""Match rules endpoints."""

import logging
from typing import Any

from fastapi import APIRouter, Depends, HTTPException

from src.app.auth.dependencies import get_current_user
from src.app.core.models import TrackMetadata
from src.app.core.services.matcher import MatchEngine
from src.app.db import AsyncSessionLocal
from src.app.match_rules import ValidationError, validate_rule_yaml
from src.app.models import MatchRule
from src.app.schemas.match_rules import (
    MatchRuleClone,
    MatchRuleCreate,
    MatchRuleDeleteResponse,
    MatchRuleOut,
    MatchRuleTestResponse,
    MatchRuleTestResult,
    MatchRuleUpdate,
    ReorderInput,
    TestRequest,
    _model_to_out,
)
from src.app.services import get_sync_target
from src.app.services.audit import log_event

logger = logging.getLogger(__name__)

router = APIRouter(prefix="/api/v1/match-rules", tags=["match-rules"])


@router.get("", response_model=list[MatchRuleOut])
async def list_rules(
    _user: dict[str, Any] = Depends(get_current_user),  # noqa: B008
):
    """List all match rules ordered by priority."""
    from sqlalchemy import select

    try:
        async with AsyncSessionLocal() as session:
            stmt = select(MatchRule).order_by(MatchRule.priority)
            result = await session.execute(stmt)
            rules = result.scalars().all()
            return [_model_to_out(r) for r in rules]
    except HTTPException:
        raise
    except Exception as e:
        logger.error(f"Error listing rules: {e}", exc_info=True)
        raise HTTPException(status_code=500, detail=f"Failed to list rules: {str(e)}") from e


@router.get("/{rule_id}", response_model=MatchRuleOut)
async def get_rule(
    rule_id: int,
    _user: dict[str, Any] = Depends(get_current_user),  # noqa: B008
):
    """Get a specific match rule by ID."""
    from sqlalchemy import select

    try:
        async with AsyncSessionLocal() as session:
            stmt = select(MatchRule).where(MatchRule.id == rule_id)
            result = await session.execute(stmt)
            rule = result.scalars().first()
            if not rule:
                raise HTTPException(status_code=404, detail="Rule not found")
            return _model_to_out(rule)
    except HTTPException:
        raise
    except Exception as e:
        logger.error(f"Error getting rule {rule_id}: {e}", exc_info=True)
        raise HTTPException(status_code=500, detail=f"Failed to get rule: {str(e)}") from e


@router.post("", response_model=MatchRuleOut, status_code=201)
async def create_rule(
    body: MatchRuleCreate,
    _user: dict[str, Any] = Depends(get_current_user),  # noqa: B008
):
    """Create a new user-defined match rule from a YAML definition."""
    from sqlalchemy import func, select

    # Validate YAML before touching the DB
    try:
        validate_rule_yaml(body.yaml_content)
    except ValidationError as exc:
        raise HTTPException(status_code=422, detail={"yaml_errors": exc.errors}) from exc

    try:
        async with AsyncSessionLocal() as session:
            max_priority = await session.execute(
                select(func.coalesce(func.max(MatchRule.priority), -1))
            )
            next_priority = max_priority.scalar() + 1

            rule = MatchRule(
                name=body.name,
                priority=next_priority,
                is_active=True,
                is_default=False,
                yaml_content=body.yaml_content,
            )
            session.add(rule)
            await session.commit()
            await session.refresh(rule)

            await log_event(
                event_type="match_rule.created",
                summary=f"Match rule created: {body.name}",
                resource_type="match_rule",
                resource_id=str(rule.id),
            )

            return _model_to_out(rule)
    except Exception as e:
        logger.error(f"Error creating rule: {e}", exc_info=True)
        raise HTTPException(status_code=500, detail=f"Failed to create rule: {str(e)}") from e


@router.post("/{rule_id}/clone", response_model=MatchRuleOut, status_code=201)
async def clone_rule(
    rule_id: int,
    body: MatchRuleClone,
    _user: dict[str, Any] = Depends(get_current_user),  # noqa: B008
):
    """Clone any rule (especially useful for immutable default rules).

    The clone is a new user-owned rule with the same YAML definition.
    """
    from sqlalchemy import func, select

    try:
        async with AsyncSessionLocal() as session:
            stmt = select(MatchRule).where(MatchRule.id == rule_id)
            result = await session.execute(stmt)
            source = result.scalars().first()
            if not source:
                raise HTTPException(status_code=404, detail="Rule not found")

            new_name = body.name or f"{source.name} (copy)"
            max_priority = await session.execute(
                select(func.coalesce(func.max(MatchRule.priority), -1))
            )
            next_priority = max_priority.scalar() + 1

            clone = MatchRule(
                name=new_name,
                priority=next_priority,
                is_active=True,
                is_default=False,
                yaml_content=source.yaml_content,
            )
            session.add(clone)
            await session.commit()
            await session.refresh(clone)

            await log_event(
                event_type="match_rule.cloned",
                summary=f"Match rule cloned: {source.name} → {new_name}",
                resource_type="match_rule",
                resource_id=str(clone.id),
                details={"source_rule_id": rule_id},
            )

            return _model_to_out(clone)
    except HTTPException:
        raise
    except Exception as e:
        logger.error(f"Error cloning rule {rule_id}: {e}", exc_info=True)
        raise HTTPException(status_code=500, detail=f"Failed to clone rule: {str(e)}") from e


@router.put("/reorder", response_model=list[MatchRuleOut])
async def reorder_rules(
    body: list[ReorderInput],
    _user: dict[str, Any] = Depends(get_current_user),  # noqa: B008
):
    """Reorder match rules by updating their priorities.

    Default rules keep their original priorities. Non-default rules are assigned
    sequential priorities starting after the highest default priority, in the
    order they appear in the request.
    """
    from sqlalchemy import select

    try:
        async with AsyncSessionLocal() as session:
            all_rules_result = await session.execute(select(MatchRule))
            all_rules = {r.id: r for r in all_rules_result.scalars().all()}

            default_max = -1
            for r in all_rules.values():
                if r.is_default and r.priority > default_max:
                    default_max = r.priority

            requested_ids = [item.id for item in body if item.id in all_rules]
            next_priority = default_max + 1

            for rule_id in requested_ids:
                rule = all_rules[rule_id]
                if not rule.is_default:
                    rule.priority = next_priority
                    next_priority += 1

            await session.commit()

            await log_event(
                event_type="match_rule.reordered",
                summary=f"Match rules reordered: {len(requested_ids)} rules",
                resource_type="match_rule",
                details={"rule_ids": requested_ids},
            )

            stmt = select(MatchRule).order_by(MatchRule.priority)
            result = await session.execute(stmt)
            rules = result.scalars().all()
            return [_model_to_out(r) for r in rules]
    except HTTPException:
        raise
    except Exception as e:
        logger.error(f"Error reordering rules: {e}", exc_info=True)
        raise HTTPException(status_code=500, detail=f"Failed to reorder rules: {str(e)}") from e


@router.post("/test", response_model=MatchRuleTestResponse)
async def test_rules(
    body: TestRequest,
    _user: dict[str, Any] = Depends(get_current_user),  # noqa: B008
):
    """Test match rules against a track to preview matching behavior."""
    try:
        track = TrackMetadata(
            title=body.track.title or "",
            artist_name=body.track.artist_name or "",
            album_name=body.track.album_name or "",
            duration_ms=body.track.duration_ms,
            source_id=body.track.source_id,
            mbid=body.track.mbid,
            artist_mbid=body.track.artist_mbid,
            album_mbid=body.track.album_mbid,
        )

        target = await get_sync_target(body.target_id or "Plex")
        engine = MatchEngine(target)

        traces = await engine.trace(track, rule_ids=body.rule_ids)

        matches = []
        for t in traces:
            match_step = None
            for step in t.get("steps") or []:
                if isinstance(step, dict) and step.get("outputs"):
                    match_step = step
            result = match_step.get("outputs", {}).get("out") if match_step else None
            matches.append(
                MatchRuleTestResult(
                    rule_id=t["rule_id"],
                    rule_name=t["rule_name"],
                    rule_priority=t["rule_priority"],
                    matched=result is not None,
                    result=result,
                    error=t.get("error"),
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
    except HTTPException:
        raise
    except Exception as e:
        logger.error(f"Error testing rules: {e}", exc_info=True)
        raise HTTPException(status_code=500, detail=f"Failed to test rules: {str(e)}") from e


@router.put("/{rule_id}", response_model=MatchRuleOut)
async def update_rule(
    rule_id: int,
    body: MatchRuleUpdate,
    _user: dict[str, Any] = Depends(get_current_user),  # noqa: B008
):
    """Update a match rule's name, active state, or YAML definition.

    Default rules are immutable — only ``is_active`` can be toggled.
    Clone them to create an editable copy.
    """
    from sqlalchemy import select

    try:
        async with AsyncSessionLocal() as session:
            stmt = select(MatchRule).where(MatchRule.id == rule_id)
            result = await session.execute(stmt)
            rule = result.scalars().first()
            if not rule:
                raise HTTPException(status_code=404, detail="Rule not found")

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

            # Validate YAML before persisting
            if body.yaml_content is not None:
                try:
                    validate_rule_yaml(body.yaml_content)
                except ValidationError as exc:
                    raise HTTPException(
                        status_code=422,
                        detail={"yaml_errors": exc.errors},
                    ) from exc

            old_name = rule.name
            old_active = rule.is_active

            if body.name is not None:
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

            if changes:
                summary = f"Match rule {', '.join(changes)}: {rule.name}"
            else:
                summary = f"Match rule updated: {rule.name}"

            await log_event(
                event_type="match_rule.updated",
                summary=summary,
                resource_type="match_rule",
                resource_id=str(rule_id),
                details={"fields_updated": list(body.model_dump(exclude_unset=True).keys())},
            )

            return _model_to_out(rule)
    except HTTPException:
        raise
    except Exception as e:
        logger.error(f"Error updating rule {rule_id}: {e}", exc_info=True)
        raise HTTPException(status_code=500, detail=f"Failed to update rule: {str(e)}") from e


@router.delete("/{rule_id}", response_model=MatchRuleDeleteResponse)
async def delete_rule(
    rule_id: int,
    _user: dict[str, Any] = Depends(get_current_user),  # noqa: B008
):
    """Delete a match rule (default rules cannot be deleted)."""
    from sqlalchemy import select

    try:
        async with AsyncSessionLocal() as session:
            stmt = select(MatchRule).where(MatchRule.id == rule_id)
            result = await session.execute(stmt)
            rule = result.scalars().first()
            if not rule:
                raise HTTPException(status_code=404, detail="Rule not found")

            if rule.is_default:
                raise HTTPException(
                    status_code=409,
                    detail="Default rules cannot be deleted. Disable or clone them instead.",
                )

            rule_name = rule.name
            rule_id_str = str(rule.id)

            await session.delete(rule)
            await session.commit()

            await log_event(
                event_type="match_rule.deleted",
                summary=f"Match rule deleted: {rule_name}",
                resource_type="match_rule",
                resource_id=rule_id_str,
            )

            return MatchRuleDeleteResponse(success=True)
    except HTTPException:
        raise
    except Exception as e:
        logger.error(f"Error deleting rule {rule_id}: {e}", exc_info=True)
        raise HTTPException(status_code=500, detail=f"Failed to delete rule: {str(e)}") from e
