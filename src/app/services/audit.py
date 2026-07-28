"""Audit logging service for tracking important operations."""

import logging
from typing import Any

from src.app.db import AsyncSessionLocal, SessionLocal
from src.app.models import AuditLog

logger = logging.getLogger(__name__)


async def log_event(
    event_type: str,
    summary: str,
    resource_type: str | None = None,
    resource_id: str | None = None,
    details: dict[str, Any] | None = None,
) -> None:
    try:
        async with AsyncSessionLocal() as session:
            entry = AuditLog(
                event_type=event_type,
                resource_type=resource_type,
                resource_id=resource_id,
                summary=summary,
                details=details,
            )
            session.add(entry)
            await session.commit()
    except Exception as e:
        logger.error(f"Failed to write audit log: {e}")


def log_event_sync(
    event_type: str,
    summary: str,
    resource_type: str | None = None,
    resource_id: str | None = None,
    details: dict[str, Any] | None = None,
) -> None:
    try:
        db = SessionLocal()
        try:
            entry = AuditLog(
                event_type=event_type,
                resource_type=resource_type,
                resource_id=resource_id,
                summary=summary,
                details=details,
            )
            db.add(entry)
            db.commit()
        finally:
            db.close()
    except Exception as e:
        logger.error(f"Failed to write audit log: {e}")
