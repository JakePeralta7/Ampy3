"""Chat request/response schemas."""

import uuid

from pydantic import BaseModel, Field


class ChatRequest(BaseModel):
    """Request payload for chat endpoint."""
    messages: list[dict] = Field(..., description="List of chat messages")
    thread_id: str = Field(
        default_factory=lambda: str(uuid.uuid4()),
        description="Thread ID for conversation persistence",
    )
    session_id: str | None = Field(
        default=None,
        description="Session ID (defaults to thread_id if not provided)",
    )


class ChatMessage(BaseModel):
    """Single chat message."""
    role: str
    content: str


class ChatHistoryResponse(BaseModel):
    """Response for history endpoint."""
    messages: list[ChatMessage]
    thread_id: str
    session_id: str
    title: str | None = None


class ChatInvokeResponse(BaseModel):
    """Response from synchronous agent invocation."""
    role: str
    content: str
    thread_id: str
    session_id: str


class ChatClearResponse(BaseModel):
    """Response after clearing chat history."""
    status: str
    session_id: str
