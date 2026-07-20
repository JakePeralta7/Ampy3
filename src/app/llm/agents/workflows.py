"""LangGraph workflow orchestration for music research, discovery, and Plex playlist management.

Replaces sync.py with a hierarchical sub-agents architecture:
- Router: Flow classification (playlist_create, artist_suggestion, general)
- Coordinator: Parent agent managing playlist workflow sequencing
- Specialized sub-agents: Research (MusicBrainz), Match (Plex search), Create (Plex playlist), Suggest (analysis)
- Chat: Free-form conversation with all tools

Two main paths:
  - Playlist workflow: research → match → create (sequential with scoped tools)
  - Free chat: ReAct loop with all tools
"""
from __future__ import annotations

from langgraph.graph import END, StateGraph
from langgraph.prebuilt import ToolNode

from src.app.llm.agents.base import AgentContext, AgentPhase
from src.app.llm.agents.chat import ALL_TOOLS, ChatAgent
from src.app.llm.agents.coordinator import CoordinatorAgent
from src.app.llm.agents.create import CreateAgent
from src.app.llm.agents.match import MatchAgent
from src.app.llm.agents.research import ResearchAgent
from src.app.llm.agents.router import RouterAgent, route_to_flow
from src.app.llm.agents.suggest import SuggestAgent
from src.app.llm.state import AgentState
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
    list_plex_playlists,
    search_plex_library,
    search_plex_playlists,
)

# Tool sets by workflow phase
RESEARCH_TOOLS = [
    search_mb_by_tag,
    search_mb_artists,
    search_mb_releases,
    search_mb_recordings,
    get_mb_artist_releases,
    get_mb_release_tracks,
]

MATCH_TOOLS = [
    search_plex_library,
]

CREATE_TOOLS = [
    create_plex_playlist,
    add_tracks_to_plex_playlist,
    list_plex_playlists,
    search_plex_playlists,
    get_plex_playlist_tracks,
    delete_plex_playlist,
]


# ── Initialize agent instances ───────────────────────────────────────────────

router_agent = RouterAgent()
coordinator = CoordinatorAgent()
research_agent = ResearchAgent()
match_agent = MatchAgent()
create_agent = CreateAgent()
suggest_agent = SuggestAgent()
chat_agent = ChatAgent()

# Create tool nodes
research_tools = ToolNode(RESEARCH_TOOLS)
match_tools = ToolNode(MATCH_TOOLS)
create_tools = ToolNode(CREATE_TOOLS)
chat_tools = ToolNode(ALL_TOOLS)


# ── Async node wrappers ──────────────────────────────────────────────────────

async def router_node(state: AgentState) -> dict:
    """Execute router agent."""
    return await router_agent.run(state)


async def research_node(state: AgentState) -> dict:
    """Execute research agent."""
    return await research_agent.run(state)


async def match_node(state: AgentState) -> dict:
    """Execute match agent."""
    return await match_agent.run(state)


async def create_node(state: AgentState) -> dict:
    """Execute create agent."""
    return await create_agent.run(state)


async def suggest_node(state: AgentState) -> dict:
    """Execute suggest agent."""
    return await suggest_agent.run(state)


async def chat_node(state: AgentState) -> dict:
    """Execute chat agent."""
    return await chat_agent.run(state)


# ── Routing functions ────────────────────────────────────────────────────────

def route_entry(state: AgentState) -> str:
    """Entry point: always route to router agent."""
    return "router_agent"


def route_from_router(state: AgentState) -> str:
    """Route based on router's flow classification.
    
    Args:
        state: AgentState with 'flow' field set by router
    
    Returns:
        "research_agent" for playlist workflows, "chat_agent" for general
    """
    flow = state.get("flow", "general")
    if flow in ("playlist_create", "artist_suggestion"):
        return "research_agent"
    return "chat_agent"


def should_continue_chat(state: AgentState) -> str:
    """Check if chat agent should loop or exit.
    
    Continues if last message has tool calls, else exits.
    """
    last = state["messages"][-1]
    return "chat_tools" if getattr(last, "tool_calls", None) else END


def should_continue_research(state: AgentState) -> str:
    """Check if research phase should continue or move to match."""
    return coordinator.should_continue_research(state)


def should_continue_match(state: AgentState) -> str:
    """Check if match phase should continue or move to next phase."""
    return coordinator.should_continue_match(state)


def should_continue_create(state: AgentState) -> str:
    """Check if create phase should continue or exit."""
    return coordinator.should_continue_create(state)


def should_always_end(state: AgentState) -> str:
    """Suggest agent always terminates (terminal node)."""
    return END


# ── Graph construction ───────────────────────────────────────────────────────

def build_graph() -> StateGraph:
    """Build LangGraph workflow with sub-agents architecture.
    
    Graph structure:
    
    entry (conditional)
        ↓
    router_agent
        ↓
    route_from_router (conditional)
        ├─ "general" → chat_agent ⇄ chat_tools (ReAct loop) → END
        └─ "playlist_create"/"artist_suggestion" → research_agent
            ↓
        research_tools ⇄ research_agent (ReAct loop)
            ↓
        match_agent
            ↓
        match_tools ⇄ match_agent (ReAct loop)
            ↓
        should_continue_match (conditional)
            ├─ "suggest_agent" → suggest_agent → END
            └─ "create_agent" → create_agent
                ↓
            create_tools ⇄ create_agent (ReAct loop)
                ↓
            END
    
    Returns:
        Compiled LangGraph StateGraph
    """
    graph = StateGraph(AgentState)

    # Add all nodes
    graph.add_node("router_agent", router_node)
    graph.add_node("chat_agent", chat_node)
    graph.add_node("chat_tools", chat_tools)
    graph.add_node("research_agent", research_node)
    graph.add_node("research_tools", research_tools)
    graph.add_node("match_agent", match_node)
    graph.add_node("match_tools", match_tools)
    graph.add_node("create_agent", create_node)
    graph.add_node("create_tools", create_tools)
    graph.add_node("suggest_agent", suggest_node)

    # Set entry point
    graph.set_conditional_entry_point(route_entry)

    # Router → flow routing
    graph.add_conditional_edges("router_agent", route_from_router)

    # Free chat path: ReAct loop
    graph.add_conditional_edges("chat_agent", should_continue_chat)
    graph.add_edge("chat_tools", "chat_agent")

    # Playlist workflow path: research → match → create/suggest
    graph.add_conditional_edges("research_agent", should_continue_research)
    graph.add_edge("research_tools", "research_agent")

    graph.add_conditional_edges("match_agent", should_continue_match)
    graph.add_edge("match_tools", "match_agent")

    graph.add_conditional_edges("create_agent", should_continue_create)
    graph.add_edge("create_tools", "create_agent")

    # Suggest is terminal
    graph.add_conditional_edges("suggest_agent", should_always_end)

    return graph


# ── Compiled agent ───────────────────────────────────────────────────────────

_graph = build_graph()
workflow = _graph.compile()
