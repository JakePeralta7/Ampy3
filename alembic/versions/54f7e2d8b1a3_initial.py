"""initial schema with seed data

Revision ID: 54f7e2d8b1a3
Revises: None
Create Date: 2026-07-04 12:00:00.000000

"""
from alembic import op
import sqlalchemy as sa
from sqlalchemy.dialects.postgresql import JSON
from sqlalchemy.sql import table, column
from datetime import datetime, timezone

revision = "54f7e2d8b1a3"
down_revision = None
branch_labels = None
depends_on = None


QUICK_START_CANVAS = {
    "nodes": [
        {
            "id": "qs_search",
            "type": "search",
            "position": {"x": 100, "y": 100},
            "config": {
                "fields_to_search": ["search_title", "search_artist", "search_album"],
                "max_results": 50,
            },
        },
        {
            "id": "qs_compare",
            "type": "compare",
            "position": {"x": 400, "y": 100},
            "config": {
                "fields_to_match": ["title", "artist_name", "album_name"],
                "threshold": 0.75,
                "weights": {"title": 0.5, "artist_name": 0.25, "album_name": 0.25},
            },
        },
    ],
    "edges": [
        {
            "id": "e_qs_search_qs_compare",
            "source": "qs_search",
            "target": "qs_compare",
            "sourceHandle": "out",
            "targetHandle": "candidates",
        },
    ],
}


TITLE_NORMALIZATION_CANVAS = {
    "nodes": [
        {
            "id": "tn_src",
            "type": "track_source",
            "position": {"x": 50, "y": 200},
            "config": {},
        },
        {
            "id": "tn_extract_artist",
            "type": "transform",
            "position": {"x": 200, "y": 200},
            "config": {
                "field": "title",
                "target_field": "artist_name",
                "operation": "regex_extract",
                "pattern": "^(.+?)\\s*[\u2013\u2014-]\\s*",
                "group": 1,
            },
        },
        {
            "id": "tn_strip_ft",
            "type": "transform",
            "position": {"x": 350, "y": 200},
            "config": {
                "field": "title",
                "target_field": "title",
                "operation": "regex_replace",
                "pattern": "\\s*[\\(\\s]*(?:ft\\.?|feat\\.?|featuring)\\s*.*$",
                "replacement": "",
            },
        },
        {
            "id": "tn_strip_video",
            "type": "transform",
            "position": {"x": 500, "y": 200},
            "config": {
                "field": "title",
                "target_field": "title",
                "operation": "regex_replace",
                "pattern": "\\s*[\\[\\(]\\s*(?:Official\\s+(?:Music\\s+)?Video|OFFICIAL\\s+(?:MUSIC\\s+)?VIDEO)\\s*[\\]\\)]",
                "replacement": "",
            },
        },
        {
            "id": "tn_strip_mv",
            "type": "transform",
            "position": {"x": 650, "y": 200},
            "config": {
                "field": "title",
                "target_field": "title",
                "operation": "regex_replace",
                "pattern": "(?:\\s*[\u2013\u2014-]\\s*)?M\\/V\\s*$",
                "replacement": "",
            },
        },
        {
            "id": "tn_strip_movie",
            "type": "transform",
            "position": {"x": 800, "y": 200},
            "config": {
                "field": "title",
                "target_field": "title",
                "operation": "regex_replace",
                "pattern": "\\s*\\(from\\s+[^)]*\\)",
                "replacement": "",
            },
        },
        {
            "id": "tn_strip_label",
            "type": "transform",
            "position": {"x": 950, "y": 200},
            "config": {
                "field": "title",
                "target_field": "title",
                "operation": "regex_replace",
                "pattern": "\\s*\\[[^\\]]*\\]\\s*$",
                "replacement": "",
            },
        },
        {
            "id": "tn_trim",
            "type": "transform",
            "position": {"x": 1100, "y": 200},
            "config": {
                "field": "title",
                "target_field": "title",
                "operation": "trim",
            },
        },
        {
            "id": "tn_search",
            "type": "search",
            "position": {"x": 1250, "y": 200},
            "config": {
                "fields_to_search": ["search_title", "search_artist"],
                "max_results": 50,
            },
        },
        {
            "id": "tn_compare",
            "type": "compare",
            "position": {"x": 1500, "y": 200},
            "config": {
                "fields_to_match": ["title", "artist_name"],
                "threshold": 0.7,
                "weights": {"title": 0.6, "artist_name": 0.4},
            },
        },
    ],
    "edges": [
        {
            "id": "e_tn_src_extract",
            "source": "tn_src",
            "target": "tn_extract_artist",
            "sourceHandle": "out",
            "targetHandle": "in",
        },
        {
            "id": "e_tn_extract_stripft",
            "source": "tn_extract_artist",
            "target": "tn_strip_ft",
            "sourceHandle": "out",
            "targetHandle": "in",
        },
        {
            "id": "e_tn_stripft_stripvideo",
            "source": "tn_strip_ft",
            "target": "tn_strip_video",
            "sourceHandle": "out",
            "targetHandle": "in",
        },
        {
            "id": "e_tn_stripvideo_stripmv",
            "source": "tn_strip_video",
            "target": "tn_strip_mv",
            "sourceHandle": "out",
            "targetHandle": "in",
        },
        {
            "id": "e_tn_stripmv_stripmovie",
            "source": "tn_strip_mv",
            "target": "tn_strip_movie",
            "sourceHandle": "out",
            "targetHandle": "in",
        },
        {
            "id": "e_tn_stripmovie_striplabel",
            "source": "tn_strip_movie",
            "target": "tn_strip_label",
            "sourceHandle": "out",
            "targetHandle": "in",
        },
        {
            "id": "e_tn_striplabel_trim",
            "source": "tn_strip_label",
            "target": "tn_trim",
            "sourceHandle": "out",
            "targetHandle": "in",
        },
        {
            "id": "e_tn_trim_search",
            "source": "tn_trim",
            "target": "tn_search",
            "sourceHandle": "out",
            "targetHandle": "in",
        },
        {
            "id": "e_tn_search_compare",
            "source": "tn_search",
            "target": "tn_compare",
            "sourceHandle": "out",
            "targetHandle": "candidates",
        },
    ],
}


def upgrade() -> None:
    # --- scheduled_playlist_syncs ---
    op.create_table(
        "scheduled_playlist_syncs",
        sa.Column("id", sa.Integer(), autoincrement=True, nullable=False),
        sa.Column("source", sa.String(50), nullable=False, server_default=sa.text("'youtube_music'")),
        sa.Column("source_url", sa.String(2048), nullable=False),
        sa.Column("plex_playlist_name", sa.String(255), nullable=False),
        sa.Column("plex_playlist_id", sa.String(255), nullable=True),
        sa.Column("schedule_interval", sa.String(50), nullable=False, server_default=sa.text("'daily'")),
        sa.Column("is_active", sa.Boolean(), nullable=False, server_default=sa.text("true")),
        sa.Column("replace_existing", sa.Boolean(), nullable=False, server_default=sa.text("false")),
        sa.Column("last_synced_at", sa.DateTime(timezone=True), nullable=True),
        sa.Column("next_sync_at", sa.DateTime(timezone=True), nullable=False),
        sa.Column("matched_count", sa.Integer(), nullable=False, server_default=sa.text("0")),
        sa.Column("failed_count", sa.Integer(), nullable=False, server_default=sa.text("0")),
        sa.Column("error_message", sa.Text(), nullable=True),
        sa.Column(
            "created_at",
            sa.DateTime(timezone=True),
            server_default=sa.func.now(),
            nullable=False,
        ),
        sa.Column(
            "updated_at",
            sa.DateTime(timezone=True),
            server_default=sa.func.now(),
            nullable=False,
        ),
        sa.PrimaryKeyConstraint("id"),
    )

    # --- playlist_tracks ---
    op.create_table(
        "playlist_tracks",
        sa.Column("id", sa.Integer(), autoincrement=True, nullable=False),
        sa.Column("sync_id", sa.Integer(), nullable=False),
        sa.Column("position", sa.Integer(), nullable=False, server_default=sa.text("0")),
        sa.Column("source_title", sa.String(255), nullable=True),
        sa.Column("source_artist", sa.String(255), nullable=True),
        sa.Column("source_album", sa.String(255), nullable=True),
        sa.Column("source_duration_ms", sa.Integer(), nullable=True),
        sa.Column("source_id", sa.String(255), nullable=True),
        sa.Column("match_plex_id", sa.String(255), nullable=True),
        sa.Column("match_title", sa.String(255), nullable=True),
        sa.Column("match_artist", sa.String(255), nullable=True),
        sa.Column("match_album", sa.String(255), nullable=True),
        sa.Column("match_duration", sa.Integer(), nullable=True),
        sa.Column("match_rule_id", sa.Integer(), nullable=True),
        sa.Column(
            "created_at",
            sa.DateTime(timezone=True),
            server_default=sa.func.now(),
            nullable=False,
        ),
        sa.ForeignKeyConstraint(
            ["sync_id"],
            ["scheduled_playlist_syncs.id"],
            ondelete="CASCADE",
        ),
        sa.PrimaryKeyConstraint("id"),
    )
    op.create_index(
        op.f("ix_playlist_tracks_sync_id"), "playlist_tracks", ["sync_id"], unique=False
    )

    # --- match_rules (with is_default) ---
    op.create_table(
        "match_rules",
        sa.Column("id", sa.Integer(), autoincrement=True, nullable=False),
        sa.Column("name", sa.String(100), nullable=False),
        sa.Column("priority", sa.Integer(), nullable=False, server_default=sa.text("0")),
        sa.Column("is_active", sa.Boolean(), nullable=False, server_default=sa.text("true")),
        sa.Column("is_default", sa.Boolean(), nullable=False, server_default=sa.text("false")),
        sa.Column("canvas", JSON, nullable=False, server_default=sa.text("'{}'::json")),
        sa.Column(
            "created_at",
            sa.DateTime(timezone=True),
            server_default=sa.func.now(),
            nullable=False,
        ),
        sa.Column(
            "updated_at",
            sa.DateTime(timezone=True),
            server_default=sa.func.now(),
            nullable=False,
        ),
        sa.PrimaryKeyConstraint("id"),
    )

    # --- audit_log ---
    op.create_table(
        "audit_log",
        sa.Column("id", sa.Integer(), autoincrement=True, nullable=False),
        sa.Column("event_type", sa.String(50), nullable=False),
        sa.Column("resource_type", sa.String(50), nullable=True),
        sa.Column("resource_id", sa.String(255), nullable=True),
        sa.Column("summary", sa.Text(), nullable=False),
        sa.Column("details", JSON, nullable=True),
        sa.Column(
            "created_at",
            sa.DateTime(timezone=True),
            server_default=sa.func.now(),
            nullable=False,
        ),
        sa.PrimaryKeyConstraint("id"),
    )
    op.create_index(
        op.f("ix_audit_log_event_type"), "audit_log", ["event_type"], unique=False
    )
    op.create_index(
        op.f("ix_audit_log_created_at"), "audit_log", ["created_at"], unique=False
    )

    # --- config ---
    op.create_table(
        "config",
        sa.Column("key", sa.String(100), nullable=False),
        sa.Column("value", sa.Text(), nullable=False),
        sa.Column(
            "updated_at",
            sa.DateTime(timezone=True),
            server_default=sa.func.now(),
            nullable=False,
        ),
        sa.PrimaryKeyConstraint("key"),
    )

    # --- seed default match rules ---
    match_rules = table(
        "match_rules",
        column("name", sa.String),
        column("priority", sa.Integer),
        column("is_active", sa.Boolean),
        column("is_default", sa.Boolean),
        column("canvas", JSON),
        column("created_at", sa.DateTime),
        column("updated_at", sa.DateTime),
    )

    now = datetime.now(timezone.utc).replace(tzinfo=None)
    op.bulk_insert(
        match_rules,
        [
            {
                "name": "Quick Start",
                "priority": 0,
                "is_active": True,
                "is_default": True,
                "canvas": QUICK_START_CANVAS,
                "created_at": now,
                "updated_at": now,
            },
            {
                "name": "Title Normalization",
                "priority": 1,
                "is_active": True,
                "is_default": True,
                "canvas": TITLE_NORMALIZATION_CANVAS,
                "created_at": now,
                "updated_at": now,
            },
        ],
    )


def downgrade() -> None:
    op.execute("DELETE FROM match_rules WHERE is_default = true")
    op.drop_table("config")
    op.drop_index(op.f("ix_audit_log_created_at"), table_name="audit_log")
    op.drop_index(op.f("ix_audit_log_event_type"), table_name="audit_log")
    op.drop_table("audit_log")
    op.drop_table("match_rules")
    op.drop_index(op.f("ix_playlist_tracks_sync_id"), table_name="playlist_tracks")
    op.drop_table("playlist_tracks")
    op.drop_table("scheduled_playlist_syncs")
