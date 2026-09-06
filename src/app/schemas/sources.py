"""Source metadata and connection test schemas."""

from pydantic import BaseModel


class SourceTestRequest(BaseModel):
    source_id: str
    auth: str | None = None


class SourceTestResponse(BaseModel):
    ok: bool
    error: str | None = None
