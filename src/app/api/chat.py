"""Chat endpoints — agent invocation and history management."""

from __future__ import annotations

import json
import logging
from collections.abc import AsyncGenerator

from fastapi import APIRouter, HTTPException, Query
from fastapi.responses import StreamingResponse
from langchain_core.messages import AIMessage, HumanMessage, SystemMessage

from src.app.llm.agents.base import AgentContext, AgentPhase
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
from src.app.schemas.chat import (
    ChatClearResponse,
    ChatHistoryResponse,
    ChatInvokeResponse,
    ChatMessage,
    ChatRequest,
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
        "context": AgentContext().to_dict(),
        "phase": AgentPhase.ROUTING.value,
        "flow": "general",
        "iteration_count": 0,
        "max_iterations": 5,
        "workflow_stack": [],
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
            SystemMessage(content="Generate a very short title (max 5 words) for this conversation. Reply with only the title, no quotes, no punctuation, no explanation."),
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
    """Stream events from the agent as JSON lines."""
    session_id = state["session_id"]
    persisted_contents: set[str] = set()
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

            if event.get("event") == "on_chain_end":
                try:
                    data = event.get("data", {})
                    output = data.get("output")
                    if output and isinstance(output, dict):
                        msgs = output.get("messages", [])
                        for msg in msgs:
                            content = None
                            if hasattr(msg, "type") and msg.type == "ai":
                                content = msg.content if hasattr(msg, "content") else ""
                            elif isinstance(msg, dict) and msg.get("type") == "ai":
                                content = msg.get("content", "")
                            if content and content.strip() and content not in persisted_contents:
                                persisted_contents.add(content)
                                await append_message(session_id, "assistant", content)

                    title = await _generate_title(session_id, await get_history(session_id))
                    if title:
                        title_event = json.dumps({"event": "on_title", "data": {"title": title}})
                        yield title_event + "\n"
                except Exception as e:
                    logger.warning("Could not persist message: %s", e)
    except Exception as e:
        error_event = json.dumps({"error": str(e), "event": "error"})
        yield f"{error_event}\n"


# ─── Endpoints ───────────────────────────────────────────────────


@router.post("/invoke", response_model=ChatInvokeResponse)
async def chat_invoke(request: ChatRequest):
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
        raise HTTPException(status_code=500, detail=f"Agent execution failed: {str(e)}")


@router.post("/stream_events")
async def chat_stream_events(request: ChatRequest):
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
async def chat_history(session_id: str, limit: int = Query(50, ge=1, le=1000)):
    """Retrieve chat history for a session."""
    try:
        history = await get_history(session_id, limit=limit)
        title = await get_title(session_id)
        messages = [
            ChatMessage(role=msg["role"], content=msg["content"])
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
        )


@router.delete("/history/{session_id}", response_model=ChatClearResponse)
async def clear_chat_history(session_id: str):
    """Clear chat history for a session."""
    try:
        await clear_history_fn(session_id)
        return ChatClearResponse(status="cleared", session_id=session_id)
    except Exception as e:
        raise HTTPException(
            status_code=500,
            detail=f"Failed to clear history: {str(e)}",
        )
