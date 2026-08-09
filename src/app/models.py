from datetime import datetime
from enum import StrEnum
from typing import Any

from sqlalchemy import (
    JSON,
    Boolean,
    DateTime,
    ForeignKey,
    Integer,
    String,
    Text,
    UniqueConstraint,
    func,
)
from sqlalchemy.orm import Mapped, mapped_column, relationship

from src.app.db import Base

# ─── Column Mixins ───────────────────────────────────────────────


class CreatedAtMixin:
    """Adds a ``created_at`` timestamp column (no index)."""

    created_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), server_default=func.now(), nullable=False
    )


class TimestampMixin(CreatedAtMixin):
    """Adds ``created_at`` and ``updated_at`` timestamp columns."""

    updated_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), server_default=func.now(), onupdate=func.now(), nullable=False
    )


class TrackColumns:
    """Shared source columns for any table tracking a YouTube Music track."""

    position: Mapped[int] = mapped_column(Integer, default=0, nullable=False)

    # Source (YouTube Music) metadata
    source_title: Mapped[str | None] = mapped_column(String(255), nullable=True)
    source_artist: Mapped[str | None] = mapped_column(String(255), nullable=True)
    source_album: Mapped[str | None] = mapped_column(String(255), nullable=True)
    source_duration_ms: Mapped[int | None] = mapped_column(Integer, nullable=True)
    item_id: Mapped[str | None] = mapped_column(String(255), nullable=True)


class MatchRule(TimestampMixin, Base):
    __tablename__ = "match_rules"

    id: Mapped[int] = mapped_column(primary_key=True)
    name: Mapped[str] = mapped_column(String(100), nullable=False)
    priority: Mapped[int] = mapped_column(Integer, default=0, nullable=False)
    is_active: Mapped[bool] = mapped_column(Boolean, default=True, nullable=False)
    is_default: Mapped[bool] = mapped_column(Boolean, default=False, nullable=False)
    yaml_content: Mapped[str] = mapped_column(Text, nullable=False, default="")

    def __repr__(self) -> str:
        return f"<MatchRule(id={self.id}, name={self.name}, priority={self.priority})>"


class ScheduleIntervalEnum(StrEnum):
    EVERY_6H = "every_6h"
    EVERY_12H = "every_12h"
    DAILY = "daily"
    WEEKLY = "weekly"
    EVERY_24H = "every_24h"


class PlaylistSourceEnum(StrEnum):
    YOUTUBE_MUSIC = "youtube_music"
    DEEZER = "deezer"


class ScheduledPlaylistSync(TimestampMixin, Base):
    __tablename__ = "scheduled_playlist_syncs"

    id: Mapped[int] = mapped_column(primary_key=True)
    source: Mapped[str] = mapped_column(
        String(50), default=PlaylistSourceEnum.YOUTUBE_MUSIC, nullable=False
    )
    source_url: Mapped[str] = mapped_column(String(2048), nullable=False)
    target_playlist_name: Mapped[str] = mapped_column(String(255), nullable=False)

    schedule_interval: Mapped[str] = mapped_column(
        String(50), default=ScheduleIntervalEnum.DAILY, nullable=False
    )
    is_active: Mapped[bool] = mapped_column(Boolean, default=True, nullable=False)

    last_synced_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True), nullable=True)
    next_sync_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), nullable=False)
    matched_count: Mapped[int] = mapped_column(Integer, default=0, nullable=False)
    failed_count: Mapped[int] = mapped_column(Integer, default=0, nullable=False)
    error_message: Mapped[str | None] = mapped_column(Text, nullable=True)

    tracks: Mapped[list[PlaylistTrack]] = relationship(
        back_populates="sync", cascade="all, delete-orphan", order_by="PlaylistTrack.position"
    )
    schedule_targets: Mapped[list[ScheduleTarget]] = relationship(
        back_populates="sync", cascade="all, delete-orphan"
    )

    def __repr__(self) -> str:
        return f"<ScheduledPlaylistSync(id={self.id}, playlist={self.target_playlist_name})>"

    @property
    def target_ids(self) -> list[str]:
        """Computed from junction table — replaces former JSON column."""
        return [t.target_id for t in self.schedule_targets]

    @property
    def target_playlist_id(self) -> str | None:
        """Backward-compat: first target's playlist_id."""
        for t in self.schedule_targets:
            if t.playlist_id:
                return t.playlist_id
        return None


class ScheduleTarget(Base):
    """Junction table linking schedules to their target platforms with persisted playlist IDs."""

    __tablename__ = "schedule_targets"

    id: Mapped[int] = mapped_column(primary_key=True)
    sync_id: Mapped[int] = mapped_column(
        ForeignKey("scheduled_playlist_syncs.id", ondelete="CASCADE"),
        nullable=False,
        index=True,
    )
    target_id: Mapped[str] = mapped_column(String(50), nullable=False)
    playlist_id: Mapped[str | None] = mapped_column(String(255), nullable=True)

    sync: Mapped[ScheduledPlaylistSync] = relationship(back_populates="schedule_targets")

    __table_args__ = (UniqueConstraint("sync_id", "target_id", name="uq_schedule_target"),)

    def __repr__(self) -> str:
        return (
            f"<ScheduleTarget(id={self.id}, sync_id={self.sync_id}, "
            f"target_id='{self.target_id}', playlist_id='{self.playlist_id}')>"
        )


class PlaylistTrack(TrackColumns, CreatedAtMixin, Base):
    __tablename__ = "playlist_tracks"

    id: Mapped[int] = mapped_column(primary_key=True)
    sync_id: Mapped[int] = mapped_column(
        ForeignKey("scheduled_playlist_syncs.id", ondelete="CASCADE"),
        nullable=False,
        index=True,
    )

    sync: Mapped[ScheduledPlaylistSync] = relationship(back_populates="tracks")
    targets: Mapped[list[PlaylistTrackTarget]] = relationship(
        back_populates="playlist_track", cascade="all, delete-orphan"
    )

    def __repr__(self) -> str:
        return (
            f"<PlaylistTrack(id={self.id}, sync_id={self.sync_id}, source='{self.source_title}')>"
        )


class Config(Base):
    __tablename__ = "config"

    key: Mapped[str] = mapped_column(String(100), primary_key=True)
    value: Mapped[str] = mapped_column(Text, nullable=False)
    updated_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), server_default=func.now(), onupdate=func.now(), nullable=False
    )

    def __repr__(self) -> str:
        return f"<Config(key={self.key})>"


class AuditLog(Base):
    __tablename__ = "audit_log"

    id: Mapped[int] = mapped_column(primary_key=True)
    event_type: Mapped[str] = mapped_column(String(50), nullable=False, index=True)
    resource_type: Mapped[str | None] = mapped_column(String(50), nullable=True)
    resource_id: Mapped[str | None] = mapped_column(String(255), nullable=True)
    summary: Mapped[str] = mapped_column(Text, nullable=False)
    details: Mapped[dict[str, Any] | None] = mapped_column(JSON, nullable=True)
    created_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), server_default=func.now(), nullable=False, index=True
    )

    def __repr__(self) -> str:
        return f"<AuditLog(id={self.id}, event_type={self.event_type})>"


class UserSession(CreatedAtMixin, Base):
    """Server-side session store. The cookie only carries a signed session ID."""

    __tablename__ = "user_sessions"

    id: Mapped[str] = mapped_column(String(64), primary_key=True)
    plex_user_id: Mapped[str] = mapped_column(String(64), nullable=False, index=True)
    username: Mapped[str] = mapped_column(String(255), nullable=False)
    email: Mapped[str | None] = mapped_column(String(255), nullable=True)
    thumb: Mapped[str | None] = mapped_column(String(1024), nullable=True)
    plex_token: Mapped[str] = mapped_column(Text, nullable=False)
    expires_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), nullable=False, index=True
    )


class SyncRun(CreatedAtMixin, Base):
    __tablename__ = "sync_runs"

    id: Mapped[int] = mapped_column(primary_key=True)
    sync_id: Mapped[int] = mapped_column(
        ForeignKey("scheduled_playlist_syncs.id", ondelete="CASCADE"),
        nullable=False,
        index=True,
    )
    target_id: Mapped[str] = mapped_column(String(50), nullable=False)
    matched_count: Mapped[int] = mapped_column(Integer, default=0, nullable=False)
    failed_count: Mapped[int] = mapped_column(Integer, default=0, nullable=False)

    tracks: Mapped[list[SyncRunTrack]] = relationship(
        back_populates="run", cascade="all, delete-orphan", order_by="SyncRunTrack.position"
    )

    def __repr__(self) -> str:
        return f"<SyncRun(id={self.id}, sync_id={self.sync_id}, matched={self.matched_count})>"


class SyncRunTrack(TrackColumns, Base):
    __tablename__ = "sync_run_tracks"

    id: Mapped[int] = mapped_column(primary_key=True)
    run_id: Mapped[int] = mapped_column(
        ForeignKey("sync_runs.id", ondelete="CASCADE"),
        nullable=False,
        index=True,
    )

    run: Mapped[SyncRun] = relationship(back_populates="tracks")
    targets: Mapped[list[SyncRunTrackTarget]] = relationship(
        back_populates="sync_run_track", cascade="all, delete-orphan"
    )

    def __repr__(self) -> str:
        return f"<SyncRunTrack(id={self.id}, run_id={self.run_id}, source='{self.source_title}')>"


class PlaylistTrackTarget(Base):
    """Per-target match data for a playlist track."""

    __tablename__ = "playlist_track_targets"

    id: Mapped[int] = mapped_column(primary_key=True)
    playlist_track_id: Mapped[int] = mapped_column(
        ForeignKey("playlist_tracks.id", ondelete="CASCADE"),
        nullable=False,
        index=True,
    )
    target_id: Mapped[str] = mapped_column(String(50), nullable=False, index=True)
    item_id: Mapped[str] = mapped_column(String(255), nullable=False)
    title: Mapped[str | None] = mapped_column(String(255), nullable=True)
    artist_name: Mapped[str | None] = mapped_column(String(255), nullable=True)
    album_name: Mapped[str | None] = mapped_column(String(255), nullable=True)
    duration: Mapped[int | None] = mapped_column(Integer, nullable=True)
    rule_id: Mapped[int | None] = mapped_column(Integer, nullable=True)

    playlist_track: Mapped[PlaylistTrack] = relationship(back_populates="targets")

    __table_args__ = (
        UniqueConstraint("playlist_track_id", "target_id", name="uq_playlist_track_target"),
    )

    def __repr__(self) -> str:
        return (
            f"<PlaylistTrackTarget(id={self.id}, target={self.target_id}, "
            f"item_id='{self.item_id}')>"
        )


class SyncRunTrackTarget(Base):
    """Per-target match data for a sync run track (history)."""

    __tablename__ = "sync_run_track_targets"

    id: Mapped[int] = mapped_column(primary_key=True)
    sync_run_track_id: Mapped[int] = mapped_column(
        ForeignKey("sync_run_tracks.id", ondelete="CASCADE"),
        nullable=False,
        index=True,
    )
    target_id: Mapped[str] = mapped_column(String(50), nullable=False, index=True)
    item_id: Mapped[str] = mapped_column(String(255), nullable=False)
    title: Mapped[str | None] = mapped_column(String(255), nullable=True)
    artist_name: Mapped[str | None] = mapped_column(String(255), nullable=True)
    album_name: Mapped[str | None] = mapped_column(String(255), nullable=True)
    duration: Mapped[int | None] = mapped_column(Integer, nullable=True)
    rule_id: Mapped[int | None] = mapped_column(Integer, nullable=True)

    sync_run_track: Mapped[SyncRunTrack] = relationship(back_populates="targets")

    __table_args__ = (
        UniqueConstraint("sync_run_track_id", "target_id", name="uq_sync_run_track_target"),
    )

    def __repr__(self) -> str:
        return (
            f"<SyncRunTrackTarget(id={self.id}, target={self.target_id}, item_id='{self.item_id}')>"
        )
