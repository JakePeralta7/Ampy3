"""Router agent for initial flow classification.

LLM-based classifier that examines user intent and routes to appropriate workflow:
- playlist_create: User wants to create a new playlist from Plex library
- artist_suggestion: User wants artist recommendations
- general: Free chat with all tools
"""
from __future__ import annotations

from langchain_core.tools import tool

from src.app.llm.agents.base import AgentPhase, BaseAgent, push_workflow_stack
from src.app.llm.ollama import get_llm
from src.app.llm.prompts import ROUTER_PROMPT


@tool
def route_to_flow(flow: str) -> str:
    """Route the user's request to the most appropriate workflow.

    Args:
        flow: The best-matching flow for the request.
            - "playlist_create": User wants to curate/make/create a new playlist from Plex library.
            - "artist_suggestion": User wants artist recommendations or suggestions for new artists to add.
            - "general": Everything else — general chat, syncing playlists, Plex management, questions.
    """
    return flow


class RouterAgent(BaseAgent):
    """LLM-based flow classifier.
    
    Examines user intent and decides which workflow to invoke:
    - playlist_create or artist_suggestion flow
    - general chat
    """

    def __init__(self):
        super().__init__(
            name="router",
            system_prompt=ROUTER_PROMPT,
            tools=[route_to_flow],
        )

    async def run(self, state: dict, llm: any = None) -> dict:
        """Execute router logic to classify user intent.
        
        Args:
            state: AgentState dict
            llm: ChatModel (unused; gets llm via get_llm)
        
        Returns:
            dict with updated 'flow' field
        """
        llm = get_llm().bind_tools([route_to_flow])
        messages = self._inject_system_message(state["messages"], self.system_prompt)
        response = await llm.ainvoke(messages)

        # Extract flow from tool call
        flow = "general"
        for tc in (getattr(response, "tool_calls", None) or []):
            if tc.get("name") == "route_to_flow":
                flow = tc.get("args", {}).get("flow", "general")
                break

        # Record phase transition
        push_workflow_stack(state, AgentPhase.ROUTING.value)

        return {"flow": flow}
