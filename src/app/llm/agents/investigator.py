"""Investigator agent tools and utilities for diagnosing sync track mismatches.

Tools are organized by workflow phase. The multi-phase LangGraph workflow in workflows.py
orchestrates these tools across phases: gather_context → diagnose → group_patterns → 
verify → create → test_verify.

Each phase has access only to its scoped tool set, enforced via ToolNode composition.
"""
from __future__ import annotations

from langchain_core.tools import BaseTool

from src.app.llm.tools.match_rules import (
    create_match_rule,
    get_match_rule,
    list_match_rules,
    test_match_rule,
    update_match_rule,
)
from src.app.llm.tools.plex import search_plex_library
from src.app.llm.tools.sync_db import (
    get_sync_run_unmatched,
    get_sync_summary,
    get_unmatched_tracks,
    list_scheduled_syncs,
    list_sync_runs,
)

# ─── Phase-Scoped Tool Sets ───────────────────────────────────────────────────

GATHER_CONTEXT_TOOLS: list[BaseTool] = [
    # Context gathering phase — understand scope and formulate strategy
    list_scheduled_syncs,
    get_sync_summary,
    get_unmatched_tracks,
    list_sync_runs,
    get_sync_run_unmatched,
]
"""Tools for gather_context phase: list syncs, get unmatched counts, understand scope."""

DIAGNOSE_TOOLS: list[BaseTool] = [
    # Diagnosis phase — test tracks against rules, extract failure reasons
    test_match_rule,
]
"""Tools for diagnose phase: run test_match_rule to get detailed traces and failure reasons."""

GROUP_PATTERNS_TOOLS: list[BaseTool] = []
"""Tools for group_patterns phase: pure LLM analysis, no tools needed."""

VERIFY_TOOLS: list[BaseTool] = [
    # Verification phase — confirm fixes exist in Plex library
    search_plex_library,
]
"""Tools for verify phase: search Plex to confirm pattern fixes would work."""

CREATE_TOOLS: list[BaseTool] = [
    # Rule creation phase — create and update match rules
    list_match_rules,
    get_match_rule,
    create_match_rule,
    update_match_rule,
]
"""Tools for create phase: template lookup, rule creation, rule updates."""

TEST_VERIFY_TOOLS: list[BaseTool] = [
    # Re-verification phase — test rules on affected tracks
    test_match_rule,
]
"""Tools for test_verify phase: re-test with newly created rules, confirm effectiveness."""

# ─── Convenience Aggregates ───────────────────────────────────────────────────

ALL_TOOLS: list[BaseTool] = [
    # All tools for backward compatibility (e.g., if used elsewhere)
    *GATHER_CONTEXT_TOOLS,
    *DIAGNOSE_TOOLS,
    *VERIFY_TOOLS,
    *CREATE_TOOLS,
    *TEST_VERIFY_TOOLS,
]
"""All tools across all phases (backward compatibility)."""

