"""Pydantic schemas for API request/response serialization."""

from src.app.schemas.audit import AuditLogListResponse, AuditLogOut
from src.app.schemas.chat import (
    ChatClearResponse,
    ChatHistoryResponse,
    ChatInvokeResponse,
    ChatMessage,
    ChatRequest,
)
from src.app.schemas.match_rules import (
    MatchRuleCreate,
    MatchRuleDeleteResponse,
    MatchRuleOut,
    MatchRuleTestResponse,
    MatchRuleTestResult,
    MatchRuleUpdate,
    ReorderInput,
    TestRequest,
    TrackTestInput,
)
from src.app.schemas.playlists import (
    PlaylistSearchResponse,
    PlaylistSyncRequest,
    PlaylistSyncResponse,
    PlaylistTracksResponse,
    RematchTrackInput,
    RematchTrackResponse,
    TrackDetail,
    TrackMatch,
    TrackSource,
)
from src.app.schemas.schedules import (
    CreateScheduledSyncInput,
    ScheduledSyncOut,
    SchedulerReloadResponse,
    SyncNowResponse,
    UpdateScheduledSyncInput,
)
from src.app.schemas.settings import SettingsOut, SettingsUpdate

__all__ = [
    # Audit
    "AuditLogOut",
    "AuditLogListResponse",
    # Chat
    "ChatRequest",
    "ChatMessage",
    "ChatHistoryResponse",
    "ChatInvokeResponse",
    "ChatClearResponse",
    # Match rules
    "MatchRuleOut",
    "MatchRuleCreate",
    "MatchRuleUpdate",
    "MatchRuleDeleteResponse",
    "MatchRuleTestResult",
    "MatchRuleTestResponse",
    "ReorderInput",
    "TrackTestInput",
    "TestRequest",
    # Playlists
    "PlaylistSyncRequest",
    "PlaylistSyncResponse",
    "PlaylistSearchResponse",
    "PlaylistTracksResponse",
    "RematchTrackInput",
    "RematchTrackResponse",
    "TrackSource",
    "TrackMatch",
    "TrackDetail",
    # Schedules
    "CreateScheduledSyncInput",
    "UpdateScheduledSyncInput",
    "ScheduledSyncOut",
    "SyncNowResponse",
    "SchedulerReloadResponse",
    # Settings
    "SettingsOut",
    "SettingsUpdate",
]
