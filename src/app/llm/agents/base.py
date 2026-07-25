"""Base abstractions for LangGraph sub-agents architecture.

Provides BaseAgent class, AgentContext for structured state passing,
and AgentPhase enum for workflow phase tracking.
"""
from __future__ import annotations

from abc import ABC, abstractmethod
from dataclasses import dataclass, field
from enum import Enum, StrEnum
from typing import Any, Optional

from langchain_core.messages import BaseMessage, SystemMessage


class AgentPhase(StrEnum):
    """Workflow phases for agent execution tracking."""
    ROUTING = "routing"
    RESEARCH = "research"
    MATCH = "match"
    CREATE = "create"
    SUGGEST = "suggest"
    CHAT = "chat"


@dataclass
class AgentContext:
    """Structured context passed between agents in a workflow.

    Enables clean data threading from research → match → create phases
    without implicit state management.
    """
    research_results: list[dict] = field(default_factory=list)
    """List of discovered artists: [{artist, mbid, genres}]"""

    matched_tracks: list[dict] = field(default_factory=list)
    """List of matched tracks from Plex: [{track, artist, plex_id}]"""

    created_playlist_id: str | None = None
    """ID of created Plex playlist"""

    error_state: dict = field(default_factory=dict)
    """Error tracking: {error_type, message, agent_phase, attempted_retry}"""

    def to_dict(self) -> dict:
        """Convert context to dict for JSON serialization."""
        return {
            "research_results": self.research_results,
            "matched_tracks": self.matched_tracks,
            "created_playlist_id": self.created_playlist_id,
            "error_state": self.error_state,
        }

    @classmethod
    def from_dict(cls, data: dict) -> AgentContext:
        """Create AgentContext from dict."""
        return cls(
            research_results=data.get("research_results", []),
            matched_tracks=data.get("matched_tracks", []),
            created_playlist_id=data.get("created_playlist_id"),
            error_state=data.get("error_state", {}),
        )


class BaseAgent(ABC):
    """Base class for all LangGraph agents.

    Defines the contract that all agents must fulfill:
    - name: Unique agent identifier
    - system_prompt: Phase-specific prompt
    - tools: Available tools (can be empty for analysis-only agents)
    - run: Execute agent with LLM (async)
    """

    def __init__(
        self,
        name: str,
        system_prompt: str,
        tools: list[Any] = None,
    ):
        self.name = name
        self.system_prompt = system_prompt
        self.tools = tools or []

    @abstractmethod
    async def run(self, state: dict, llm: Any) -> dict:
        """Execute agent logic with given LLM and state.

        Args:
            state: AgentState dict containing messages, context, phase, etc.
            llm: ChatModel instance to use for generation

        Returns:
            dict with updated fields (messages, context, phase, etc.)
        """
        pass

    def _inject_system_message(
        self,
        messages: list[BaseMessage],
        system_prompt: str
    ) -> list[BaseMessage]:
        """Replace existing system message with phase-specific one,
        or prepend if none exists.

        Args:
            messages: List of messages to modify
            system_prompt: System prompt content to inject/replace

        Returns:
            Updated messages list
        """
        result = []
        replaced = False
        for m in messages:
            if isinstance(m, SystemMessage):
                if not replaced:
                    result.append(SystemMessage(content=system_prompt))
                    replaced = True
            else:
                result.append(m)
        if not replaced:
            result.insert(0, SystemMessage(content=system_prompt))
        return result


def get_context_summary(context: AgentContext) -> str:
    """Format AgentContext for prompt injection into agent messages.

    Args:
        context: AgentContext to summarize

    Returns:
        Formatted string describing context state
    """
    parts = []

    if context.research_results:
        artists = [r.get("artist", "Unknown") for r in context.research_results]
        parts.append(f"Previously researched artists: {', '.join(artists[:5])}")
        if len(artists) > 5:
            parts.append(f"(+{len(artists) - 5} more)")

    if context.matched_tracks:
        count = len(context.matched_tracks)
        parts.append(f"Matched {count} tracks from Plex library")

    if context.created_playlist_id:
        parts.append(f"Created playlist: {context.created_playlist_id}")

    if context.error_state:
        error_msg = context.error_state.get("message", "Unknown error")
        phase = context.error_state.get("agent_phase", "unknown")
        parts.append(f"Previous error in {phase}: {error_msg}")

    return " | ".join(parts) if parts else "(No context)"


def increment_iteration_count(state: dict, max_iterations: int = 5) -> None:
    """Increment iteration counter and raise if exceeded.

    Args:
        state: AgentState dict
        max_iterations: Maximum allowed iterations

    Raises:
        RuntimeError: If iteration count exceeds max
    """
    count = state.get("iteration_count", 0) + 1
    state["iteration_count"] = count

    if count > max_iterations:
        raise RuntimeError(
            f"Agent exceeded max iterations ({max_iterations}). "
            f"Possible infinite loop detected."
        )


def push_workflow_stack(state: dict, phase: str) -> None:
    """Record phase transition for debugging.

    Args:
        state: AgentState dict
        phase: AgentPhase or phase name
    """
    stack = state.get("workflow_stack", [])
    stack.append(phase)
    state["workflow_stack"] = stack


def clear_iteration_count(state: dict) -> None:
    """Reset iteration count for a new phase.

    Args:
        state: AgentState dict
    """
    state["iteration_count"] = 0
