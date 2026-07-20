"""Coordinator agent for playlist workflows.

Parent agent that orchestrates sequential sub-agents for playlist creation
and artist suggestion workflows. Manages context threading and workflow state.

Not an LLM agent; a control-flow agent that delegates to specialized sub-agents.
"""
from __future__ import annotations

from src.app.llm.agents.base import AgentContext, AgentPhase


class CoordinatorAgent:
    """Orchestrates playlist workflow phases.
    
    Manages the routing and state threading between research, match, and
    create/suggest sub-agents. Tracks workflow progression and context updates.
    
    This is a control-flow agent, not an LLM agent. All actual language
    generation happens in the specialized sub-agents (research, match, create, suggest).
    """

    def __init__(self):
        self.name = "coordinator"

    def route_from_match(self, state: dict) -> str:
        """Decide whether to route to suggest or create after match phase.
        
        Args:
            state: AgentState dict
        
        Returns:
            "suggest_agent" if flow is artist_suggestion, else "create_agent"
        """
        flow = state.get("flow", "general")
        return "suggest_agent" if flow == "artist_suggestion" else "create_agent"

    def should_continue_research(self, state: dict) -> str:
        """Check if research phase should continue or move to match.
        
        Args:
            state: AgentState dict
        
        Returns:
            "research_tools" to continue looping, "match_agent" to exit
        """
        last = state["messages"][-1]
        if getattr(last, "tool_calls", None):
            return "research_tools"
        return "match_agent"

    def should_continue_match(self, state: dict) -> str:
        """Check if match phase should continue or move to next phase.
        
        Args:
            state: AgentState dict
        
        Returns:
            "match_tools" to continue looping, or route_from_match() result
        """
        last = state["messages"][-1]
        if getattr(last, "tool_calls", None):
            return "match_tools"
        return self.route_from_match(state)

    def should_continue_create(self, state: dict) -> str:
        """Check if create phase should continue or finish.
        
        Args:
            state: AgentState dict
        
        Returns:
            "create_tools" to continue looping, "END" to finish
        """
        last = state["messages"][-1]
        if getattr(last, "tool_calls", None):
            return "create_tools"
        return "END"
