"""Chat endpoints — agent invocation and history management."""

from __future__ import annotations

import json
import logging
from collections.abc import AsyncGenerator
from datetime import datetime

from fastapi import APIRouter, Depends, HTTPException, Query
from fastapi.responses import StreamingResponse
from langchain_core.messages import AIMessage, HumanMessage, SystemMessage
from sqlalchemy import desc, select
from sqlalchemy.ext.asyncio import AsyncSession

from src.app.auth.dependencies import get_current_user
from src.app.db import get_async_session
from src.app.llm.agents.workflows import workflow
from src.app.llm.history import (
    append_message,
    clear_history,
    get_history,
    get_title,
    set_title,
)
from src.app.llm.history import clear_history as clear_history_fn
from src.app.llm.ollama import get_llm
from src.app.llm.state import AgentState
from src.app.models import ChatSession
from src.app.schemas.chat import (
    ChatClearResponse,
    ChatHistoryResponse,
    ChatInvokeResponse,
    ChatMessage,
    ChatRequest,
    ChatSessionCreateRequest,
    ChatSessionCreateResponse,
    ChatSessionEntry,
    ChatSessionsListResponse,
)
from src.app.services.audit import log_event

logger = logging.getLogger(__name__)

router = APIRouter(prefix="/api/v1/chat", tags=["chat"])


# ─── Helpers ─────────────────────────────────────────────────────


async def _load_state_from_history(
    session_id: str,
    new_messages: list[dict],
) -> AgentState:
    """Load agent state from Valkey history and append new messages."""
    history = await get_history(session_id)

    messages = []
    for msg in history:
        if msg["role"] == "user":
            messages.append(HumanMessage(content=msg["content"]))
        elif msg["role"] == "assistant":
            messages.append(AIMessage(content=msg["content"]))

    for msg in new_messages:
        role = msg.get("role", "user")
        content = msg.get("content", "")
        if role == "user":
            messages.append(HumanMessage(content=content))
            await append_message(session_id, "user", content)
        elif role == "assistant":
            messages.append(AIMessage(content=content))

    state: AgentState = {
        "messages": messages,
        "session_id": session_id,
        # Phase tracking and structured outputs (initialized for new workflow)
        "current_phase": "gather_context",
        "context": {},
        "diagnosed_tracks": [],
        "grouped_patterns": {},
        "verified_fixes": {},
        "created_rules": {},
        "test_results": {},
    }
    return state


async def _generate_title(session_id: str, history: list[dict]) -> str | None:
    """Generate a short title for the conversation."""
    try:
        existing = await get_title(session_id)
        if existing:
            return existing

        llm = get_llm(temperature=0.3, max_tokens=30)
        summary_messages = []
        for msg in history[-4:]:
            if msg["role"] == "user":
                summary_messages.append(HumanMessage(content=msg["content"]))
            elif msg["role"] == "assistant":
                summary_messages.append(AIMessage(content=msg["content"]))

        if not summary_messages:
            return None

        response = await llm.ainvoke([
            SystemMessage(
                content=(
                    "Generate a very short title (max 5 words) for this conversation. "
                    "Reply with only the title, no quotes, no punctuation, no explanation."
                )
            ),
            *summary_messages,
        ])
        title = response.content.strip().strip('"').strip("'")
        if title:
            await set_title(session_id, title)
        return title
    except Exception as e:
        logger.warning("Title generation failed: %s", e)
        return None





async def _stream_agent_events(
    state: AgentState,
    config: dict,
) -> AsyncGenerator[str, None]:
    """Stream events from the agent as JSON lines.
    
    All messages are persisted to Valkey (thinking, responses, tool results).
    Persistence Strategy:
    - Eager: Persist on first 50+ chars (survive page refresh during streaming)
    - Final: Update on chain end with complete content
    - Fallback: Persist if never persisted during streaming
    """
    session_id = state["session_id"]
    persisted_contents: set[str] = {
        msg.content
        for msg in state.get("messages", [])
        if hasattr(msg, "content") and isinstance(msg.content, str) and msg.content.strip()
    }
    pending_flow_items: dict[str, dict] = {}
    completed_flow_items: list[dict] = []
    
    # Track streamed content for persistence
    current_ai_content = ""
    ai_message_persisted = False
    last_persisted_content = ""
    
    try:
        async for event in workflow.astream_events(
            input=state,
            config=config,
            version="v2",
        ):
            try:
                def serialize_event(obj):
                    if hasattr(obj, "type"):
                        result = {"type": getattr(obj, "type", None)}
                        if hasattr(obj, "content"):
                            result["content"] = obj.content
                        if hasattr(obj, "tool_calls"):
                            result["tool_calls"] = str(obj.tool_calls)
                        return result
                    if hasattr(obj, "__dict__"):
                        return obj.__dict__
                    return str(obj)

                event_json = json.dumps(event, default=serialize_event)
                yield event_json + "\n"
            except Exception as e:
                try:
                    event_dict = {
                        "event": event.get("event"),
                        "error": f"Serialization failed: {str(e)}",
                    }
                    yield json.dumps(event_dict) + "\n"
                except Exception:
                    yield '{"error": "Critical serialization failure"}\n'

            ev_name = event.get("event")

            if ev_name == "on_tool_start":
                run_id = event.get("run_id", "")
                data = event.get("data", {})
                name = event.get("name", "unknown")
                args = {}
                if isinstance(data, dict) and isinstance(data.get("input"), dict):
                    args = data["input"]
                pending_flow_items[run_id] = {
                    "name": name,
                    "args": args,
                    "result": None,
                    "status": "pending",
                }

            elif ev_name == "on_tool_end":
                run_id = event.get("run_id", "")
                data = event.get("data", {})
                output = data.get("output") if isinstance(data, dict) else None
                if run_id in pending_flow_items:
                    pending_flow_items[run_id]["status"] = "completed"
                    pending_flow_items[run_id]["result"] = (
                        str(output) if output is not None else None
                    )
                    completed_flow_items.append(pending_flow_items.pop(run_id))

            elif ev_name == "on_tool_error":
                run_id = event.get("run_id", "")
                if run_id in pending_flow_items:
                    pending_flow_items[run_id]["status"] = "failed"
                    completed_flow_items.append(pending_flow_items.pop(run_id))

            # Track AI model streaming content - persist all messages
            if ev_name == "on_chat_model_stream":
                try:
                    data = event.get("data", {})
                    chunk = data.get("chunk")
                    
                    # Extract content from chunk
                    chunk_content = ""
                    if isinstance(chunk, str):
                        chunk_content = chunk
                    elif isinstance(chunk, dict) and "content" in chunk:
                        chunk_content = chunk.get("content", "")
                    elif hasattr(chunk, "content"):
                        chunk_content = str(chunk.content)
                    
                    if chunk_content:
                        current_ai_content += chunk_content
                        
                        # Persist eagerly on first meaningful content (>50 chars)
                        if (
                            not ai_message_persisted
                            and current_ai_content.strip()
                            and len(current_ai_content) >= 50
                            and current_ai_content not in persisted_contents
                        ):
                            persisted_contents.add(current_ai_content)
                            last_persisted_content = current_ai_content
                            flow = completed_flow_items if completed_flow_items else None
                            await append_message(
                                session_id, "assistant", current_ai_content, flow_items=flow
                            )
                            ai_message_persisted = True
                            logger.debug(
                                f"Early-persisted assistant message ({len(current_ai_content)} chars)"
                            )
                except Exception as e:
                    logger.warning(f"Failed to process stream chunk: {e}")

            # On chain end, finalize message persistence
            if ev_name == "on_chain_end":
                try:
                    data = event.get("data", {})
                    output = data.get("output")
                    
                    if output and isinstance(output, dict):
                        msgs = output.get("messages", [])
                        
                        # Find the final AI message
                        for msg in reversed(msgs):
                            content = None
                            
                            if hasattr(msg, "type") and msg.type == "ai":
                                content = msg.content if hasattr(msg, "content") else ""
                            elif isinstance(msg, dict) and msg.get("type") == "ai":
                                content = msg.get("content", "")
                            
                            if content and content.strip():
                                # If this is different from what we streamed, update it
                                if content != last_persisted_content and content not in persisted_contents:
                                    persisted_contents.add(content)
                                    flow = completed_flow_items if completed_flow_items else None
                                    await append_message(
                                        session_id, "assistant", content, flow_items=flow
                                    )
                                    logger.debug(f"Final-persisted assistant message ({len(content)} chars)")
                                elif not ai_message_persisted and content not in persisted_contents:
                                    # Never persisted during streaming, do it now
                                    persisted_contents.add(content)
                                    flow = completed_flow_items if completed_flow_items else None
                                    await append_message(
                                        session_id, "assistant", content, flow_items=flow
                                    )
                                    logger.debug(f"Fallback-persisted assistant message ({len(content)} chars)")
                                break
                    
                    # Generate and emit title
                    title = await _generate_title(session_id, await get_history(session_id))
                    if title:
                        title_event = json.dumps({"event": "on_title", "data": {"title": title}})
                        yield title_event + "\n"
                        
                except Exception as e:
                    logger.warning("Error during chain end: %s", e)
                    
    except Exception as e:
        error_event = json.dumps({"error": str(e), "event": "error"})
        yield f"{error_event}\n"


# ─── Endpoints ───────────────────────────────────────────────────


@router.post("/invoke", response_model=ChatInvokeResponse)
async def chat_invoke(
    request: ChatRequest,
    _user: dict = Depends(get_current_user),  # noqa: B008
):
    """Synchronously invoke the agent (single turn, no streaming)."""
    session_id = request.session_id or request.thread_id
    try:
        state = await _load_state_from_history(session_id, request.messages)
        config = {"configurable": {"thread_id": session_id}}
        result = await workflow.ainvoke(input=state, config=config)
        messages = result.get("messages", [])
        if messages:
            final_msg = messages[-1]
            if hasattr(final_msg, "content"):
                content = final_msg.content
            elif isinstance(final_msg, dict):
                content = final_msg.get("content", "")
            else:
                content = str(final_msg)
            await append_message(session_id, "assistant", content)
            await log_event(
                event_type="chat.invoked",
                summary=f"Chat invoked for session {session_id}",
                resource_type="chat_session",
                resource_id=session_id,
                details={"message_count": len(request.messages)},
            )
            return ChatInvokeResponse(
                role="assistant",
                content=content,
                thread_id=session_id,
                session_id=session_id,
            )
        raise HTTPException(status_code=500, detail="No response from agent")
    except HTTPException:
        raise
    except Exception as e:
        raise HTTPException(status_code=500, detail=f"Agent execution failed: {str(e)}") from e


@router.post("/stream_events")
async def chat_stream_events(
    request: ChatRequest,
    _user: dict = Depends(get_current_user),  # noqa: B008
):
    """Stream agent events in real-time (SSE response).

    Returns a `text/event-stream` response with JSON lines for each agent event.
    """
    session_id = request.session_id or request.thread_id

    async def event_generator():
        try:
            state = await _load_state_from_history(session_id, request.messages)
            config = {"configurable": {"thread_id": session_id}}
            async for event_line in _stream_agent_events(state, config):
                yield f"data: {event_line}"
        except Exception as e:
            error_data = json.dumps({"error": str(e), "type": "error"})
            yield f"data: {error_data}\n"

    return StreamingResponse(
        event_generator(),
        media_type="text/event-stream",
        headers={
            "Cache-Control": "no-cache",
            "X-Accel-Buffering": "no",
            "Connection": "keep-alive",
        },
    )


@router.get("/history/{session_id}", response_model=ChatHistoryResponse)
async def chat_history(
    session_id: str,
    limit: int = Query(50, ge=1, le=1000),
    _user: dict = Depends(get_current_user),  # noqa: B008
):
    """Retrieve chat history for a session."""
    try:
        history = await get_history(session_id, limit=limit)
        title = await get_title(session_id)
        messages = [
            ChatMessage(
                role=msg["role"],
                content=msg["content"],
                flow_items=msg.get("flow_items"),
            )
            for msg in history
        ]
        return ChatHistoryResponse(
            messages=messages,
            thread_id=session_id,
            session_id=session_id,
            title=title,
        )
    except Exception as e:
        raise HTTPException(
            status_code=500,
            detail=f"Failed to retrieve history: {str(e)}",
        ) from e


@router.delete("/history/{session_id}", response_model=ChatClearResponse)
async def clear_chat_history(
    session_id: str,
    _user: dict = Depends(get_current_user),  # noqa: B008
):
    """Clear chat history for a session."""
    try:
        await clear_history_fn(session_id)
        await log_event(
            event_type="chat.history_cleared",
            summary=f"Chat history cleared for session {session_id}",
            resource_type="chat_session",
            resource_id=session_id,
        )
        return ChatClearResponse(status="cleared", session_id=session_id)
    except Exception as e:
        raise HTTPException(
            status_code=500,
            detail=f"Failed to clear history: {str(e)}",
        ) from e


# ─── Chat Session Management ─────────────────────────────────


@router.get("/sessions", response_model=ChatSessionsListResponse)
async def list_chat_sessions(
    user: dict = Depends(get_current_user),  # noqa: B008
    session: AsyncSession = Depends(get_async_session),  # noqa: B008
):
    """List all chat sessions for the current user."""
    try:
        plex_user_id = user.get("plex_user_id")
        stmt = (
            select(ChatSession)
            .where(ChatSession.plex_user_id == plex_user_id)
            .order_by(desc(ChatSession.updated_at))
            .limit(100)
        )
        result = await session.execute(stmt)
        sessions = result.scalars().all()

        entries = [
            ChatSessionEntry(
                id=s.id,
                preview=s.preview,
                title=s.title,
                created_at=s.created_at,
                updated_at=s.updated_at,
            )
            for s in sessions
        ]
        return ChatSessionsListResponse(sessions=entries)
    except Exception as e:
        raise HTTPException(
            status_code=500,
            detail=f"Failed to list sessions: {str(e)}",
        ) from e


@router.post("/sessions", response_model=ChatSessionCreateResponse)
async def create_chat_session(
    request: ChatSessionCreateRequest,
    user: dict = Depends(get_current_user),  # noqa: B008
    session: AsyncSession = Depends(get_async_session),  # noqa: B008
):
    """Create a new chat session."""
    try:
        plex_user_id = user.get("plex_user_id")
        now = datetime.utcnow()

        # Check if session already exists
        stmt = select(ChatSession).where(ChatSession.id == request.id)
        existing = await session.execute(stmt)
        if existing.scalars().first():
            raise HTTPException(
                status_code=409,
                detail="Session already exists",
            )

        # Create new session
        chat_session = ChatSession(
            id=request.id,
            plex_user_id=plex_user_id,
            preview=request.preview,
            created_at=now,
            updated_at=now,
        )
        session.add(chat_session)
        await session.commit()
        await session.refresh(chat_session)

        await log_event(
            event_type="chat.session_created",
            summary=f"Chat session created: {request.id}",
            resource_type="chat_session",
            resource_id=request.id,
        )

        return ChatSessionCreateResponse(
            id=chat_session.id,
            preview=chat_session.preview,
            created_at=chat_session.created_at,
            updated_at=chat_session.updated_at,
        )
    except HTTPException:
        raise
    except Exception as e:
        raise HTTPException(
            status_code=500,
            detail=f"Failed to create session: {str(e)}",
        ) from e


@router.delete("/sessions/{session_id}", response_model=dict)
async def delete_chat_session(
    session_id: str,
    user: dict = Depends(get_current_user),  # noqa: B008
    db_session: AsyncSession = Depends(get_async_session),  # noqa: B008
):
    """Delete a chat session and its history."""
    try:
        plex_user_id = user.get("plex_user_id")

        # Find and verify ownership
        stmt = select(ChatSession).where(
            ChatSession.id == session_id,
            ChatSession.plex_user_id == plex_user_id,
        )
        result = await db_session.execute(stmt)
        chat_session = result.scalars().first()

        if not chat_session:
            raise HTTPException(status_code=404, detail="Session not found")

        # Delete session from DB
        await db_session.delete(chat_session)
        await db_session.commit()

        # Clear history from Valkey
        await clear_history_fn(session_id)

        await log_event(
            event_type="chat.session_deleted",
            summary=f"Chat session deleted: {session_id}",
            resource_type="chat_session",
            resource_id=session_id,
        )

        return {"status": "deleted", "session_id": session_id}
    except HTTPException:
        raise
    except Exception as e:
        raise HTTPException(
            status_code=500,
            detail=f"Failed to delete session: {str(e)}",
        ) from e
