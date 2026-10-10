"""Add user_id to scheduled_playlist_syncs.

Revision ID: 007_add_user_id_to_schedule
Revises: 006_audit_log_actor
Create Date: 2026-09-23

Each scheduled playlist sync now belongs to a user (via Plex user ID from
the session). This enables per-user authorization for sync operations.
"""

import sqlalchemy as sa

from alembic import op

revision = "007_add_user_id_to_schedule"
down_revision = "006_audit_log_actor"
branch_labels = None
depends_on = None


def upgrade() -> None:
    # Add column as NOT NULL. Since this is a new database version,
    # no backfilling is needed.
    op.add_column(
        "scheduled_playlist_syncs",
        sa.Column("user_id", sa.String(64), nullable=False),
    )
    # Create index
    op.create_index("ix_scheduled_playlist_syncs_user_id", "scheduled_playlist_syncs", ["user_id"])
    # Add foreign key
    op.create_foreign_key(
        "fk_scheduled_playlist_syncs_user_id_user_sessions",
        "scheduled_playlist_syncs",
        "user_sessions",
        ["user_id"],
        ["plex_user_id"],
    )


def downgrade() -> None:
    op.drop_constraint(
        "fk_scheduled_playlist_syncs_user_id_user_sessions",
        "scheduled_playlist_syncs",
        type_="foreignkey",
    )
    op.drop_index("ix_scheduled_playlist_syncs_user_id", table_name="scheduled_playlist_syncs")
    op.drop_column("scheduled_playlist_syncs", "user_id")