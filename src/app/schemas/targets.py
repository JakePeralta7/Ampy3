"""Target connection test schemas."""

from pydantic import BaseModel


class TargetTestRequest(BaseModel):
    target_id: str
    config: dict[str, str]


class TargetTestResponse(BaseModel):
    ok: bool
    error: str | None = None
