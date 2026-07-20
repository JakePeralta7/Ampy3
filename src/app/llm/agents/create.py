"""Create agent for Plex playlist creation.

Creates playlist from matched tracks. Outputs created_playlist_id to context.
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
from src.app.llm.tools.plex import (
    add_tracks_to_plex_playlist,
    create_plex_playlist,
    delete_plex_playlist,
    get_plex_playlist_tracks,
    list_plex_playlists,
    search_plex_playlists,
)

CREATE_PROMPT = """You are in the CREATE phase of playlist creation.

Your ONLY job: create the playlist from the tracks matched in Plex.

Rules:
- Use create_plex_playlist(title="...", track_descriptions=[...]) with the matched tracks.
- Each track description should include title and artist.
- When done, summarize what was created and which artists/tracks are included.
- If no tracks were matched, inform the user."""


class CreateAgent(BaseAgent):
    """Creates Plex playlists from matched tracks.
    
    Scoped to Plex playlist creation tools. Exits when creation completes
    or iteration limit reached.
    """

    def __init__(self):
        super().__init__(
            name="create",
            system_prompt=CREATE_PROMPT,
            tools=[
                create_plex_playlist,
                add_tracks_to_plex_playlist,
                list_plex_playlists,
                search_plex_playlists,
                get_plex_playlist_tracks,
                delete_plex_playlist,
            ],
        )

    async def run(self, state: dict, llm: any = None) -> dict:
        """Execute create agent to build Plex playlist.
        
        Args:
            state: AgentState dict
            llm: ChatModel (unused; gets via get_llm)
        
        Returns:
            dict with updated messages and context
        """
        clear_iteration_count(state)
        push_workflow_stack(state, AgentPhase.CREATE.value)

        # Convert context dict back to AgentContext for summary
        context = AgentContext.from_dict(state.get("context", {}))
        context_summary = get_context_summary(context)
        prompt = f"{self.system_prompt}\n\nContext: {context_summary}"

        llm_bound = get_llm().bind_tools(self.tools)
        messages = self._inject_system_message(state["messages"], prompt)
        response = await llm_bound.ainvoke(messages)

        # Track phase
        state["phase"] = AgentPhase.CREATE.value

        return {"messages": [response]}
