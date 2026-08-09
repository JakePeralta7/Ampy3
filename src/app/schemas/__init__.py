"""Pydantic schemas for API request/response serialization."""

from src.app.schemas.audit import AuditLogListResponse, AuditLogOut
from src.app.schemas.chat import (
    ChatClearResponse,
    ChatHistoryResponse,
    ChatInvokeResponse,
    ChatMessage,
    ChatRequest,
)
from src.app.schemas.common import DeleteResponse
from src.app.schemas.explore import (
    ChartsBundleOut,
    ExploreHomeOut,
    ExploreItemOut,
    ExploreProviderOut,
    ExploreSectionOut,
    MoodCategoryOut,
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
    TrackDetail,
    TrackSource,
    TrackTarget,
)
from src.app.schemas.schedules import (
    CreateScheduledSyncInput,
    ScheduledSyncOut,
    SchedulerReloadResponse,
    SyncNowResponse,
    UpdateScheduledSyncInput,
)
from src.app.schemas.settings import SettingsOut, SettingsUpdate
from src.app.schemas.syncs import (
    MatchTrackInput,
    MatchTrackResponse,
    SyncDiffItem,
    SyncDiffResponse,
    SyncRunOut,
    SyncTracksResponse,
    SyncTriggerRequest,
    SyncTriggerResponse,
    UnmatchedTrackOut,
)
from src.app.schemas.targets import TargetTestRequest, TargetTestResponse

__all__ = [
    # Common
    "DeleteResponse",
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
    "PlaylistSearchResponse",
    "TrackSource",
    "TrackTarget",
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
    # Syncs
    "SyncTriggerRequest",
    "SyncTriggerResponse",
    "SyncTracksResponse",
    "MatchTrackInput",
    "MatchTrackResponse",
    "SyncRunOut",
    "SyncDiffItem",
    "SyncDiffResponse",
    "UnmatchedTrackOut",
    # Targets
    "TargetTestRequest",
    "TargetTestResponse",
    # Explore
    "ExploreItemOut",
    "ExploreSectionOut",
    "ExploreHomeOut",
    "ChartsBundleOut",
    "MoodCategoryOut",
    "ExploreProviderOut",
]
