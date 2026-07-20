from __future__ import annotations

from typing import Annotated, Any, Optional, TypedDict

from langchain_core.messages import BaseMessage
from langgraph.graph.message import add_messages

from src.app.llm.agents.base import AgentPhase


class AgentState(TypedDict):
    """Workflow state for LangGraph agents.
    
    Tracks messages, routing decision, phase transitions, and context threading
    between sequential agents in a workflow.
    """
    messages: Annotated[list[BaseMessage], add_messages]
    """Accumulated conversation messages"""

    session_id: str
    """User session ID for history persistence"""

    context: dict
    """Structured context dict {research_results, matched_tracks, created_playlist_id, error_state}
    for threading data between workflow phases.
    See AgentContext in base.py for field definitions."""

    phase: str
    """Current workflow phase for routing and debugging (AgentPhase value)"""

    flow: str
    """Top-level flow classification from router: 'general', 'playlist_create', 'artist_suggestion'"""

    iteration_count: int
    """Iteration counter to detect infinite loops within a phase"""

    max_iterations: int
    """Maximum allowed iterations per phase (default 5)"""

    workflow_stack: list[str]
    """Trace of visited phases for debugging (e.g., ['routing', 'research', 'match', 'create'])"""
