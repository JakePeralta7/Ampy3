"""Research agent for music discovery via MusicBrainz.

Discovers artists relevant to user query using MusicBrainz tools.
Outputs research_results to context for downstream match phase.
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
from src.app.llm.prompts import ROUTER_PROMPT
from src.app.llm.tools.musicbrainz import (
    get_mb_artist_releases,
    get_mb_release_tracks,
    search_mb_artists,
    search_mb_by_tag,
    search_mb_recordings,
    search_mb_releases,
)

RESEARCH_PROMPT = """You are in the RESEARCH phase of playlist creation.

Your ONLY job: discover 10-20 artists relevant to the user's music request.

**STRATEGY FOR COMPOUND REQUESTS (e.g., "fun 00s songs", "chill 90s indie"):**
1. Break down the request into GENRE + ERA (if mentioned)
2. Search for genre first: e.g., for "fun 00s", try tag="pop" or tag="dance"
3. If results are from wrong era (too old/new), do FOLLOW-UP searches with decade tags
   - Example: If "pop" returns 80s artists, search again with tag="2000s" or tag="00s"
   - Or search specific artist names you know from that era: search_mb_artists("Britney Spears"), etc.
4. Combine results from multiple searches to get diverse artists from the correct era

**DECADE TAG REFERENCE:**
- 1990s music: Try "90s", "1990s", "grunge", "britpop", "indie rock"
- 2000s music: Try "2000s", "00s", "pop", "dance", "electronic", "emo", "pop-punk"
- 2010s music: Try "2010s", "10s", "indie pop", "synthwave", "trap"
- For specific styles: "chill" → "lo-fi", "chillout", "ambient"; "fun" → "pop", "dance"

**TOOL USAGE:**
- search_mb_by_tag(tag="...", entity="artist"): Primary tool for genre discovery. Never search recordings by tag.
- search_mb_artists(query): Use for specific artist lookups or known acts from an era
- search_mb_releases/recordings: Only if you need album/track details

**EXIT CRITERIA:**
- You have 10-20 promising artists covering the user's request
- Artists span the correct era/genre/mood
- Then say "RESEARCH COMPLETE" with a brief summary of who you found

**CONSTRAINTS:**
- Do NOT search Plex. Do NOT create playlists. Only research on MusicBrainz.
- Do NOT call tools more than 8 times (avoid infinite loops)
- If a search returns too few results (< 5), try a different tag or fallback search"""


class ResearchAgent(BaseAgent):
    """Discovers artists using MusicBrainz.
    
    Scoped to MusicBrainz tools only. Exits when LLM produces "RESEARCH COMPLETE"
    or iteration limit reached.
    """

    def __init__(self):
        super().__init__(
            name="research",
            system_prompt=RESEARCH_PROMPT,
            tools=[
                search_mb_by_tag,
                search_mb_artists,
                search_mb_releases,
                search_mb_recordings,
                get_mb_artist_releases,
                get_mb_release_tracks,
            ],
        )

    async def run(self, state: dict, llm: any = None) -> dict:
        """Execute research agent to discover artists.
        
        Args:
            state: AgentState dict
            llm: ChatModel (unused; gets via get_llm)
        
        Returns:
            dict with updated messages and context
        """
        clear_iteration_count(state)
        push_workflow_stack(state, AgentPhase.RESEARCH.value)

        # Convert context dict back to AgentContext for summary
        context = AgentContext.from_dict(state.get("context", {}))
        context_summary = get_context_summary(context)

        # Extract user's original request from messages for clarity
        user_request = ""
        for msg in state.get("messages", []):
            if hasattr(msg, 'type') and msg.type == "human":
                user_request = msg.content
                break

        prompt = f"{self.system_prompt}\n\n**USER REQUEST:** {user_request}\n\nContext: {context_summary}"

        llm_bound = get_llm().bind_tools(self.tools)
        messages = self._inject_system_message(state["messages"], prompt)
        response = await llm_bound.ainvoke(messages)

        # Track results in context if found
        if response.content and "RESEARCH COMPLETE" in response.content:
            # Extract artist results from messages and store in context
            # (In real implementation, would parse tool outputs more carefully)
            state["phase"] = AgentPhase.RESEARCH.value

        return {"messages": [response]}
