"""Audit logging service for tracking important operations."""

import logging
from contextvars import ContextVar
from typing import Any

from src.app.db import AsyncSessionLocal, SessionLocal
from src.app.models import AuditLog

logger = logging.getLogger(__name__)

_actor_user_id: ContextVar[str | None] = ContextVar("actor_user_id", default=None)


def set_audit_actor(user: dict[str, Any] | None) -> None:
    """Record the acting user for the current request context.

    Captured by the session middleware in ``main.py`` so ``log_event`` can
    attribute entries without threading an actor parameter through callers.
    """
    _actor_user_id.set((user or {}).get("plex_user_id"))


def get_audit_actor() -> str | None:
    """Return the user id attributed to the current request, if any."""
    return _actor_user_id.get()


async def log_event(
    event_type: str,
    summary: str,
    resource_type: str | None = None,
    resource_id: str | None = None,
    details: dict[str, Any] | None = None,
    actor_user_id: str | None = None,
) -> None:
    if actor_user_id is None:
        actor_user_id = get_audit_actor()
    try:
        async with AsyncSessionLocal() as session:
            entry = AuditLog(
                event_type=event_type,
                resource_type=resource_type,
                resource_id=resource_id,
                actor_user_id=actor_user_id,
                summary=summary,
                details=details,
            )
            session.add(entry)
            await session.commit()
    except Exception as e:
        logger.error("Failed to write audit log: %s", e)


def log_event_sync(
    event_type: str,
    summary: str,
    resource_type: str | None = None,
    resource_id: str | None = None,
    details: dict[str, Any] | None = None,
    actor_user_id: str | None = None,
) -> None:
    if actor_user_id is None:
        actor_user_id = get_audit_actor()
    try:
        db = SessionLocal()
        try:
            entry = AuditLog(
                event_type=event_type,
                resource_type=resource_type,
                resource_id=resource_id,
                actor_user_id=actor_user_id,
                summary=summary,
                details=details,
            )
            db.add(entry)
            db.commit()
        finally:
            db.close()
    except Exception as e:
        logger.error("Failed to write audit log: %s", e)
