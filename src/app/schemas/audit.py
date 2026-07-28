"""Audit log schemas."""

from typing import Any

from pydantic import BaseModel


class AuditLogOut(BaseModel):
    """Single audit log entry."""

    id: int
    event_type: str
    resource_type: str | None = None
    resource_id: str | None = None
    summary: str | None = None
    details: dict[str, Any] | None = None
    created_at: str | None = None


class AuditLogListResponse(BaseModel):
    """Paginated audit log list."""

    logs: list[AuditLogOut]
    total: int
    limit: int
    offset: int
