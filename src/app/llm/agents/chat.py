"""Chat agent for free-form conversation.

General chat agent with access to all tools. Runs ReAct-style tool loop
until no more tool calls are generated.
"""
from __future__ import annotations

from src.app.llm.agents.base import (
    AgentPhase,
    BaseAgent,
    clear_iteration_count,
    push_workflow_stack,
)
from src.app.llm.ollama import get_llm
from src.app.llm.prompts import SYSTEM_PROMPT
from src.app.llm.tools.musicbrainz import (
    get_mb_artist_releases,
    get_mb_release_tracks,
    search_mb_artists,
    search_mb_by_tag,
    search_mb_recordings,
    search_mb_releases,
)
from src.app.llm.tools.plex import (
    add_tracks_to_plex_playlist,
    create_plex_playlist,
    delete_plex_playlist,
    get_plex_playlist_tracks,
    get_sync_status,
    list_plex_playlists,
    search_plex_library,
    search_plex_playlists,
    sync_playlist_to_plex,
)
from src.app.llm.tools.ytmusic import (
    get_ytmusic_playlist,
    search_youtube_music,
)

ALL_TOOLS = [
    get_sync_status,
    list_plex_playlists,
    search_plex_playlists,
    search_plex_library,
    search_youtube_music,
    get_ytmusic_playlist,
    sync_playlist_to_plex,
    create_plex_playlist,
    add_tracks_to_plex_playlist,
    get_plex_playlist_tracks,
    delete_plex_playlist,
    search_mb_artists,
    search_mb_by_tag,
    search_mb_releases,
    search_mb_recordings,
    get_mb_artist_releases,
    get_mb_release_tracks,
]


class ChatAgent(BaseAgent):
    """Free-form conversation agent with all tools.
    
    Independent of workflow routing. Uses ReAct-style tool loop
    for general music queries, library management, etc.
    """

    def __init__(self):
        super().__init__(
            name="chat",
            system_prompt=SYSTEM_PROMPT,
            tools=ALL_TOOLS,
        )

    async def run(self, state: dict, llm: any = None) -> dict:
        """Execute chat agent for free conversation.
        
        Args:
            state: AgentState dict
            llm: ChatModel (unused; gets via get_llm)
        
        Returns:
            dict with updated messages
        """
        clear_iteration_count(state)
        push_workflow_stack(state, AgentPhase.CHAT.value)

        llm_bound = get_llm().bind_tools(self.tools)
        messages = self._inject_system_message(state["messages"], self.system_prompt)
        response = await llm_bound.ainvoke(messages)

        # Track phase
        state["phase"] = AgentPhase.CHAT.value

        return {"messages": [response]}
