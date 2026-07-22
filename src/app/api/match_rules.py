"""Match rules endpoints."""

import logging

from fastapi import APIRouter, Depends, HTTPException

from src.app.auth.dependencies import get_current_user

from src.app.core.models import TrackMetadata
from src.app.core.services.matcher import MatchEngine, get_active_rules
from src.app.db import AsyncSessionLocal
from src.app.models import MatchRule
from src.app.schemas.match_rules import (
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

logger = logging.getLogger(__name__)

router = APIRouter(prefix="/api/v1/match-rules", tags=["match-rules"])


@router.get("", response_model=list[MatchRuleOut])
async def list_rules(
    _user: dict = Depends(get_current_user),  # noqa: B008
):
    """List all match rules ordered by priority."""
    from sqlalchemy import select

    try:
        async with AsyncSessionLocal() as session:
            stmt = select(MatchRule).order_by(MatchRule.priority)
            result = await session.execute(stmt)
            rules = result.scalars().all()
            return [_model_to_out(r) for r in rules]
    except Exception as e:
        logger.error(f"Error listing rules: {e}", exc_info=True)
        raise HTTPException(status_code=500, detail=f"Failed to list rules: {str(e)}")


@router.get("/{rule_id}", response_model=MatchRuleOut)
async def get_rule(
    rule_id: int,
    _user: dict = Depends(get_current_user),  # noqa: B008
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
        raise HTTPException(status_code=500, detail=f"Failed to get rule: {str(e)}")


@router.post("", response_model=MatchRuleOut, status_code=201)
async def create_rule(
    body: MatchRuleCreate,
    _user: dict = Depends(get_current_user),  # noqa: B008
):
    """Create a new match rule with auto-assigned priority."""
    from sqlalchemy import func, select

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
                canvas={"nodes": [], "edges": []},
            )
            session.add(rule)
            await session.commit()
            await session.refresh(rule)
            return _model_to_out(rule)
    except Exception as e:
        logger.error(f"Error creating rule: {e}", exc_info=True)
        raise HTTPException(status_code=500, detail=f"Failed to create rule: {str(e)}")


@router.put("/reorder", response_model=list[MatchRuleOut])
async def reorder_rules(
    body: list[ReorderInput],
    _user: dict = Depends(get_current_user),  # noqa: B008
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

            stmt = select(MatchRule).order_by(MatchRule.priority)
            result = await session.execute(stmt)
            rules = result.scalars().all()
            return [_model_to_out(r) for r in rules]
    except Exception as e:
        logger.error(f"Error reordering rules: {e}", exc_info=True)
        raise HTTPException(status_code=500, detail=f"Failed to reorder rules: {str(e)}")


@router.post("/test", response_model=MatchRuleTestResponse)
async def test_rules(
    body: TestRequest,
    _user: dict = Depends(get_current_user),  # noqa: B008
):
    """Test match rules against a track to preview matching behavior."""
    try:
        track = TrackMetadata(
            title=body.track.title or "",
            artist_name=body.track.artist_name or "",
            album_name=body.track.album_name or "",
            duration_ms=body.track.duration_ms,
            source_id=body.track.source_id,
        )

        plex_client = await get_sync_target()
        engine = MatchEngine(plex_client)

        traces = await engine.trace(track, rule_ids=body.rule_ids)

        matches = []
        for t in traces:
            match_step = None
            for step in (t.get("steps") or []):
                if isinstance(step, dict) and step.get("outputs"):
                    match_step = step
            result = match_step.get("outputs", {}).get("out") if match_step else None
            matches.append(MatchRuleTestResult(
                rule_id=t["rule_id"],
                rule_name=t["rule_name"],
                rule_priority=t["rule_priority"],
                matched=result is not None,
                result=result,
                error=t.get("error"),
            ))

        match_results = []
        if not body.rule_ids:
            match_results = await engine.run(track)

        return MatchRuleTestResponse(
            traces=traces,
            matches=matches,
            match_results=match_results,
        )
    except Exception as e:
        logger.error(f"Error testing rules: {e}", exc_info=True)
        raise HTTPException(status_code=500, detail=f"Failed to test rules: {str(e)}")


@router.put("/{rule_id}", response_model=MatchRuleOut)
async def update_rule(
    rule_id: int,
    body: MatchRuleUpdate,
    _user: dict = Depends(get_current_user),  # noqa: B008
):
    """Update a match rule's name, active state, or canvas."""
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
                if body.canvas is not None:
                    blocked.append("canvas")
                if blocked:
                    raise HTTPException(
                        status_code=409,
                        detail=f"Default rules cannot modify: {', '.join(blocked)}. You can only pause/resume them.",
                    )

            if body.name is not None:
                rule.name = body.name
            if body.is_active is not None:
                rule.is_active = body.is_active
            if body.canvas is not None:
                rule.canvas = body.canvas

            await session.commit()
            await session.refresh(rule)
            return _model_to_out(rule)
    except HTTPException:
        raise
    except Exception as e:
        logger.error(f"Error updating rule {rule_id}: {e}", exc_info=True)
        raise HTTPException(status_code=500, detail=f"Failed to update rule: {str(e)}")


@router.delete("/{rule_id}", response_model=MatchRuleDeleteResponse)
async def delete_rule(
    rule_id: int,
    _user: dict = Depends(get_current_user),  # noqa: B008
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
                    detail="Default rules cannot be deleted. Disable them instead.",
                )

            await session.delete(rule)
            await session.commit()
            return MatchRuleDeleteResponse(success=True)
    except HTTPException:
        raise
    except Exception as e:
        logger.error(f"Error deleting rule {rule_id}: {e}", exc_info=True)
        raise HTTPException(status_code=500, detail=f"Failed to delete rule: {str(e)}")
