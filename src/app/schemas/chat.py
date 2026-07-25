"""Chat request/response schemas."""

import uuid
from datetime import datetime

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


class ChatFlowItem(BaseModel):
    """A tool call item within an assistant message.

    Classification: BACKEND PERSISTED
    - Tool calls are persisted to Valkey for audit, replay, and debugging
    - Includes execution traces and results
    """
    name: str | None = None
    args: dict | None = None
    result: str | None = None
    status: str | None = None


class ChatMessage(BaseModel):
    """Single chat message.

    Message Types (backend-managed classification):

    "user" → Persisted to Valkey
    "assistant" → Persisted to Valkey (backend skips ephemeral thinking)

    Frontend receives all messages in real-time, but only non-thinking responses
    are persisted to backend history via Valkey.
    """
    role: str  # "user" | "assistant"
    content: str
    flow_items: list[ChatFlowItem] | None = None  # Tool calls within this message


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


class ChatSessionEntry(BaseModel):
    """A chat session entry."""
    id: str
    preview: str
    title: str | None = None
    created_at: datetime
    updated_at: datetime


class ChatSessionsListResponse(BaseModel):
    """Response for listing chat sessions."""
    sessions: list[ChatSessionEntry]


class ChatSessionCreateRequest(BaseModel):
    """Request to create a chat session."""
    id: str
    preview: str


class ChatSessionCreateResponse(BaseModel):
    """Response after creating a chat session."""
    id: str
    preview: str
    created_at: datetime
    updated_at: datetime
