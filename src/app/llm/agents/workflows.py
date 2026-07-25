"""LangGraph workflow for the Ampy3 sync investigator agent.

Multi-phase task-specific workflow:
    gather_context → diagnose → group_patterns → verify → create → test_verify → END

Each phase has:
  - A dedicated system prompt (scoped to its task)
  - A restricted tool set (only tools needed for that phase)
  - Structured state outputs (populate phase-specific state fields)
  - Clear exit conditions (LLM decides when phase is complete)

The exported ``workflow`` object is consumed by api/chat.py via
``workflow.astream_events`` and ``workflow.ainvoke``.
"""
from __future__ import annotations

from langchain_core.messages import SystemMessage
from langgraph.graph import END, StateGraph
from langgraph.prebuilt import ToolNode

from src.app.llm.agents.investigator import (
    CREATE_TOOLS,
    DIAGNOSE_TOOLS,
    GATHER_CONTEXT_TOOLS,
    GROUP_PATTERNS_TOOLS,
    TEST_VERIFY_TOOLS,
    VERIFY_TOOLS,
)
from src.app.llm.prompts import (
    CREATE_PROMPT,
    DIAGNOSE_PROMPT,
    GATHER_CONTEXT_PROMPT,
    GROUP_PATTERNS_PROMPT,
    TEST_VERIFY_PROMPT,
    VERIFY_PROMPT,
)
from src.app.llm.state import AgentState

# ─── Tool Nodes (one per phase) ───────────────────────────────────────────────

_gather_context_tools = ToolNode(GATHER_CONTEXT_TOOLS)
_diagnose_tools = ToolNode(DIAGNOSE_TOOLS)
_group_patterns_tools = ToolNode(GROUP_PATTERNS_TOOLS)  # No tools, but included for consistency
_verify_tools = ToolNode(VERIFY_TOOLS)
_create_tools = ToolNode(CREATE_TOOLS)
_test_verify_tools = ToolNode(TEST_VERIFY_TOOLS)


# ─── Phase Node Functions ─────────────────────────────────────────────────────

async def _gather_context_node(state: AgentState) -> dict:
    """Phase 1: Gather context about syncs and unmatched tracks."""
    from src.app.llm.ollama import get_llm

    llm_bound = get_llm().bind_tools(GATHER_CONTEXT_TOOLS)

    messages = list(state["messages"])
    if messages and not isinstance(messages[0], SystemMessage):
        messages.insert(0, SystemMessage(content=GATHER_CONTEXT_PROMPT))
    else:
        messages[0] = SystemMessage(content=GATHER_CONTEXT_PROMPT)

    response = await llm_bound.ainvoke(messages)

    return {
        "messages": [response],
        "current_phase": "gather_context",
    }


async def _diagnose_node(state: AgentState) -> dict:
    """Phase 2: Diagnose unmatched tracks by testing them against rules."""
    from src.app.llm.ollama import get_llm

    llm_bound = get_llm().bind_tools(DIAGNOSE_TOOLS)

    messages = list(state["messages"])
    if messages and isinstance(messages[0], SystemMessage):
        messages[0] = SystemMessage(content=DIAGNOSE_PROMPT)
    else:
        messages.insert(0, SystemMessage(content=DIAGNOSE_PROMPT))

    response = await llm_bound.ainvoke(messages)

    return {
        "messages": [response],
        "current_phase": "diagnose",
    }


async def _group_patterns_node(state: AgentState) -> dict:
    """Phase 3: Analyze and group diagnosed patterns by root cause (analysis only, no tools)."""
    from src.app.llm.ollama import get_llm

    llm = get_llm()  # No tool binding needed

    messages = list(state["messages"])
    if messages and isinstance(messages[0], SystemMessage):
        messages[0] = SystemMessage(content=GROUP_PATTERNS_PROMPT)
    else:
        messages.insert(0, SystemMessage(content=GROUP_PATTERNS_PROMPT))

    response = await llm.ainvoke(messages)

    return {
        "messages": [response],
        "current_phase": "group_patterns",
    }


async def _verify_node(state: AgentState) -> dict:
    """Phase 4: Verify that identified patterns can actually be fixed in Plex."""
    from src.app.llm.ollama import get_llm

    llm_bound = get_llm().bind_tools(VERIFY_TOOLS)

    messages = list(state["messages"])
    if messages and isinstance(messages[0], SystemMessage):
        messages[0] = SystemMessage(content=VERIFY_PROMPT)
    else:
        messages.insert(0, SystemMessage(content=VERIFY_PROMPT))

    response = await llm_bound.ainvoke(messages)

    return {
        "messages": [response],
        "current_phase": "verify",
    }


async def _create_node(state: AgentState) -> dict:
    """Phase 5: Create match rules for verified patterns."""
    from src.app.llm.ollama import get_llm

    llm_bound = get_llm().bind_tools(CREATE_TOOLS)

    messages = list(state["messages"])
    if messages and isinstance(messages[0], SystemMessage):
        messages[0] = SystemMessage(content=CREATE_PROMPT)
    else:
        messages.insert(0, SystemMessage(content=CREATE_PROMPT))

    response = await llm_bound.ainvoke(messages)

    return {
        "messages": [response],
        "current_phase": "create",
    }


async def _test_verify_node(state: AgentState) -> dict:
    """Phase 6: Re-test created rules to confirm they fix the matched tracks."""
    from src.app.llm.ollama import get_llm

    llm_bound = get_llm().bind_tools(TEST_VERIFY_TOOLS)

    messages = list(state["messages"])
    if messages and isinstance(messages[0], SystemMessage):
        messages[0] = SystemMessage(content=TEST_VERIFY_PROMPT)
    else:
        messages.insert(0, SystemMessage(content=TEST_VERIFY_PROMPT))

    response = await llm_bound.ainvoke(messages)

    return {
        "messages": [response],
        "current_phase": "test_verify",
    }


# ─── Conditional Edge Functions ───────────────────────────────────────────────

def _should_continue_gather_context(state: AgentState) -> str:
    """After gather_context, check if LLM made tool calls.

    If no tool calls, assume context gathering failed; otherwise proceed to diagnose.
    """
    last = state["messages"][-1]
    if getattr(last, "tool_calls", None):
        return "gather_context_tools"
    return "diagnose"


def _should_gather_context_to_diagnose(state: AgentState) -> str:
    """After gather_context tools, return to gather_context node or proceed to diagnose.

    For now, always proceed to diagnose (no looping within phase).
    """
    return "diagnose"


def _should_continue_diagnose(state: AgentState) -> str:
    """After diagnose, check if LLM made tool calls for testing."""
    last = state["messages"][-1]
    if getattr(last, "tool_calls", None):
        return "diagnose_tools"
    return "group_patterns"


def _should_diagnose_to_group(state: AgentState) -> str:
    """After diagnose tools, return to diagnose node or proceed to group_patterns.

    For now, always proceed to group_patterns (no looping within phase).
    """
    return "group_patterns"


def _should_continue_verify(state: AgentState) -> str:
    """After verify, check if LLM made tool calls for searching Plex."""
    last = state["messages"][-1]
    if getattr(last, "tool_calls", None):
        return "verify_tools"
    return "create"


def _should_verify_to_create(state: AgentState) -> str:
    """After verify tools, return to verify node or proceed to create.

    For now, always proceed to create (no looping within phase).
    """
    return "create"


def _should_continue_create(state: AgentState) -> str:
    """After create, check if LLM made tool calls for rule creation."""
    last = state["messages"][-1]
    if getattr(last, "tool_calls", None):
        return "create_tools"
    return "test_verify"


def _should_create_to_test(state: AgentState) -> str:
    """After create tools, return to create node or proceed to test_verify.

    For now, always proceed to test_verify (no looping within phase).
    """
    return "test_verify"


def _should_continue_test_verify(state: AgentState) -> str:
    """After test_verify, check if LLM made tool calls for re-testing."""
    last = state["messages"][-1]
    if getattr(last, "tool_calls", None):
        return "test_verify_tools"
    return END


def _should_test_verify_to_end(state: AgentState) -> str:
    """After test_verify tools, return to test_verify node or end.

    For now, always end (no looping within phase).
    """
    return END


# ─── Graph Construction ──────────────────────────────────────────────────────

def _build_graph() -> StateGraph:
    """Build the 6-phase task-specific workflow graph."""
    graph = StateGraph(AgentState)

    # Add all phase nodes
    graph.add_node("gather_context", _gather_context_node)
    graph.add_node("gather_context_tools", _gather_context_tools)
    graph.add_node("diagnose", _diagnose_node)
    graph.add_node("diagnose_tools", _diagnose_tools)
    graph.add_node("group_patterns", _group_patterns_node)
    graph.add_node("verify", _verify_node)
    graph.add_node("verify_tools", _verify_tools)
    graph.add_node("create", _create_node)
    graph.add_node("create_tools", _create_tools)
    graph.add_node("test_verify", _test_verify_node)
    graph.add_node("test_verify_tools", _test_verify_tools)

    # Entry point: gather context
    graph.set_entry_point("gather_context")

    # Phase 1: gather_context → gather_context_tools (if tool calls) → back to gather_context
    graph.add_conditional_edges("gather_context", _should_continue_gather_context)
    graph.add_edge("gather_context_tools", "gather_context")

    # Phase 2: diagnose → diagnose_tools (if tool calls) → back to diagnose
    # Note: When gather_context completes (no more tool calls), _should_continue_gather_context
    # returns "diagnose" directly (no edge needed; conditional routing handles it)
    graph.add_conditional_edges("diagnose", _should_continue_diagnose)
    graph.add_edge("diagnose_tools", "diagnose")

    # Phase 3: group_patterns → verify (no tools, direct progression via conditional return)
    # Note: When diagnose completes, _should_continue_diagnose returns "group_patterns"
    # Add conditional edge to group_patterns to move to next phase
    graph.add_edge("group_patterns", "verify")

    # Phase 4: verify → verify_tools (if tool calls) → back to verify
    graph.add_conditional_edges("verify", _should_continue_verify)
    graph.add_edge("verify_tools", "verify")

    # Phase 5: create → create_tools (if tool calls) → back to create
    # When verify completes, _should_continue_verify returns "create" (conditional routing)
    graph.add_conditional_edges("create", _should_continue_create)
    graph.add_edge("create_tools", "create")

    # Phase 6: test_verify → test_verify_tools (if tool calls) → back to test_verify
    # When create completes, _should_continue_create returns "test_verify" (conditional routing)
    graph.add_conditional_edges("test_verify", _should_continue_test_verify)
    graph.add_edge("test_verify_tools", "test_verify")

    return graph


workflow = _build_graph().compile()

