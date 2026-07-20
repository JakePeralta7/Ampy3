"""Match agent for finding tracks in Plex library.

Searches user's Plex library for artists discovered in research phase.
Outputs matched_tracks to context for create phase.
"""
from __future__ import annotations

from src.app.llm.agents.base import (
    AgentContext,
    AgentPhase,
    BaseAgent,
    clear_iteration_count,
    get_context_summary,
    increment_iteration_count,
    push_workflow_stack,
)
from src.app.llm.ollama import get_llm
from src.app.llm.tools.plex import search_plex_library

MATCH_PROMPT = """You are in the MATCH phase of playlist creation.

Your ONLY job: search the user's Plex library by artist name to find tracks.

Rules:
- For each artist discovered in the research phase, use search_plex_library(artist="...") to find their tracks.
- If you find tracks by other relevant artists, include them too.
- Collect all matching tracks.
- When you have searched all relevant artists, say "MATCH COMPLETE" with a summary of how many tracks were found.
- Do NOT create playlists yet. Only search Plex."""


class MatchAgent(BaseAgent):
    """Matches researched artists to user's Plex library.
    
    Scoped to Plex search tool only. Exits when LLM produces "MATCH COMPLETE"
    or iteration limit reached.
    """

    def __init__(self):
        super().__init__(
            name="match",
            system_prompt=MATCH_PROMPT,
            tools=[search_plex_library],
        )

    async def run(self, state: dict, llm: any = None) -> dict:
        """Execute match agent to find tracks in Plex.
        
        Args:
            state: AgentState dict
            llm: ChatModel (unused; gets via get_llm)
        
        Returns:
            dict with updated messages and context
        """
        clear_iteration_count(state)
        push_workflow_stack(state, AgentPhase.MATCH.value)

        # Convert context dict back to AgentContext for summary
        context = AgentContext.from_dict(state.get("context", {}))
        context_summary = get_context_summary(context)
        prompt = f"{self.system_prompt}\n\nContext: {context_summary}"

        llm_bound = get_llm().bind_tools(self.tools)
        messages = self._inject_system_message(state["messages"], prompt)
        response = await llm_bound.ainvoke(messages)

        # Track phase
        if response.content and "MATCH COMPLETE" in response.content:
            state["phase"] = AgentPhase.MATCH.value

        return {"messages": [response]}
