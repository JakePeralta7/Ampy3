"""Audit log endpoints."""

import logging
from typing import Any

from fastapi import APIRouter, Depends, HTTPException, Query

from src.app.auth.dependencies import get_current_user
from src.app.db import AsyncSessionLocal
from src.app.models import AuditLog
from src.app.schemas.audit import AuditLogListResponse, AuditLogOut

logger = logging.getLogger(__name__)

router = APIRouter(prefix="/api/v1/audit", tags=["audit"])


@router.get("/logs", response_model=AuditLogListResponse)
async def list_audit_logs(
    limit: int = Query(50, ge=1, le=200, description="Number of logs to return"),
    offset: int = Query(0, ge=0, description="Number of logs to skip"),
    event_type: str | None = Query(None, description="Filter by event type"),
    _user: dict[str, Any] = Depends(get_current_user),  # noqa: B008
):
    """List audit log entries with optional filtering and pagination."""
    from sqlalchemy import desc, select

    try:
        async with AsyncSessionLocal() as session:
            stmt = select(AuditLog).order_by(desc(AuditLog.created_at))

            if event_type:
                stmt = stmt.where(AuditLog.event_type == event_type)

            count_stmt = select(AuditLog.id).order_by(desc(AuditLog.created_at))
            if event_type:
                count_stmt = count_stmt.where(AuditLog.event_type == event_type)

            total = len((await session.execute(count_stmt)).scalars().all())

            stmt = stmt.offset(offset).limit(limit)
            result = await session.execute(stmt)
            logs = result.scalars().all()

            return AuditLogListResponse(
                logs=[
                    AuditLogOut(
                        id=log.id,
                        event_type=log.event_type,
                        resource_type=log.resource_type,
                        resource_id=log.resource_id,
                        summary=log.summary,
                        details=log.details,
                        created_at=log.created_at.isoformat() if log.created_at else None,
                    )
                    for log in logs
                ],
                total=total,
                limit=limit,
                offset=offset,
            )
    except HTTPException:
        raise
    except Exception as e:
        logger.error(f"Error listing audit logs: {e}", exc_info=True)
        raise HTTPException(status_code=500, detail=f"Failed to list audit logs: {str(e)}") from e
