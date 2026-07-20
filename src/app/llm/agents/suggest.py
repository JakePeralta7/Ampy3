"""Suggest agent for artist recommendations.

Analyzes research + match results to recommend new artists for user's library.
No tools; pure LLM analysis.
"""
from __future__ import annotations

from src.app.llm.agents.base import (
    AgentContext,
    AgentPhase,
    BaseAgent,
    clear_iteration_count,
    get_context_summary,
    push_workflow_stack,
)
from src.app.llm.ollama import get_llm
from src.app.llm.prompts import SUGGEST_PROMPT


class SuggestAgent(BaseAgent):
    """Recommends artists based on research and Plex matching.
    
    No tools; pure LLM analysis of discovered artists and library matches.
    Terminal node in workflow.
    """

    def __init__(self):
        super().__init__(
            name="suggest",
            system_prompt=SUGGEST_PROMPT,
            tools=[],
        )

    async def run(self, state: dict, llm: any = None) -> dict:
        """Execute suggest agent for artist recommendations.
        
        Args:
            state: AgentState dict
            llm: ChatModel (unused; gets via get_llm)
        
        Returns:
            dict with updated messages
        """
        clear_iteration_count(state)
        push_workflow_stack(state, AgentPhase.SUGGEST.value)

        # Convert context dict back to AgentContext for summary
        context = AgentContext.from_dict(state.get("context", {}))
        context_summary = get_context_summary(context)
        prompt = f"{self.system_prompt}\n\nContext: {context_summary}"

        llm_model = get_llm()
        messages = self._inject_system_message(state["messages"], prompt)
        response = await llm_model.ainvoke(messages)

        # Track phase
        state["phase"] = AgentPhase.SUGGEST.value

        return {"messages": [response]}
