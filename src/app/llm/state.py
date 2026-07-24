from __future__ import annotations

from typing import Annotated, Any, NotRequired, TypedDict

from langchain_core.messages import BaseMessage
from langgraph.graph.message import add_messages


class AgentState(TypedDict):
    """Workflow state for the LangGraph investigator agent.
    
    The state tracks both conversation history and structured phase-specific outputs.
    Each phase populates its own state fields as the workflow progresses through:
    gather_context → diagnose → group_patterns → verify → create → test_verify
    """

    messages: Annotated[list[BaseMessage], add_messages]
    """Accumulated conversation messages."""

    session_id: str
    """User session ID for history persistence."""

    # Phase tracking
    current_phase: NotRequired[str]
    """Current workflow phase: gather_context|diagnose|group_patterns|verify|create|test_verify|end"""

    # Phase outputs - populated as workflow progresses
    context: NotRequired[dict[str, Any]]
    """Results from gather_context phase.
    
    Structure:
    {
        "syncs": [...],              # List of scheduled syncs
        "total_unmatched": int,      # Total unmatched tracks across all syncs
        "sample_size": int,          # Number of tracks to diagnose
        "selected_sync_id": int      # Focus sync ID
    }
    """

    diagnosed_tracks: NotRequired[list[dict[str, Any]]]
    """Results from diagnose phase.
    
    Structure: List of:
    {
        "track_id": int,
        "original_title": str,
        "original_artist": str,
        "rules_tested": int,
        "reason_failed": str,        # Why it didn't match
        "trace": dict or list        # Detailed execution trace
    }
    """

    grouped_patterns: NotRequired[dict[str, Any]]
    """Results from group_patterns phase.
    
    Structure:
    {
        "missing_from_plex": [...],           # Tracks not in Plex
        "title_needs_cleaning": [...],        # Title formatting issues
        "artist_fuzzy_match": [...],          # Artist similarity issues
        "album_mismatch": [...],              # Album-related issues
        ...
    }
    """

    verified_fixes: NotRequired[dict[str, Any]]
    """Results from verify phase.
    
    Structure:
    {
        "pattern_1": {
            "pattern": str,                   # Pattern description
            "verified": bool,
            "verified_tracks": [...],         # Representative tracks that work
            "fix_type": str                   # title_clean|artist_fuzzy|album_search etc
        },
        ...
    }
    """

    created_rules: NotRequired[dict[str, Any]]
    """Results from create phase.
    
    Structure:
    {
        "rule_1": {
            "id": int,
            "name": str,
            "created_at": str,
            "pattern_fixed": str,
            "yaml_preview": str
        },
        ...
    }
    """

    test_results: NotRequired[dict[str, Any]]
    """Results from test_verify phase.
    
    Structure:
    {
        "rule_1": {
            "affected_tracks": int,
            "now_match": int,
            "still_fail": int,
            "trace": dict                     # Sample traces of re-tested tracks
        },
        ...
    }
    """

