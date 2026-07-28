"""Common API response schemas."""

from pydantic import BaseModel


class DeleteResponse(BaseModel):
    """Standard response after a successful delete."""

    id: int | str
    success: bool = True
