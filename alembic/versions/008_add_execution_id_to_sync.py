"""Add execution_id to scheduled_playlist_syncs for idempotency.

Revision ID: 008_add_execution_id_to_sync
Revises: 007_add_user_id_to_schedule
Create Date: 2026-10-21

Each sync can be tagged with a client-provided execution_id for idempotency:
- Prevents duplicate syncs from retried requests
- Unique constraint per user for ad-hoc syncs (execution_id must be unique
  within a user)
- Scheduled syncs store the key on the schedule row, so their scope is the
  schedule itself and the same key may be reused for a different schedule
- Nullable to support existing syncs and syncs without idempotency key
"""

import sqlalchemy as sa

from alembic import op

revision = "008_add_execution_id_to_sync"
down_revision = "007_add_user_id_to_schedule"
branch_labels = None
depends_on = None


def upgrade() -> None:
    # Add execution_id column as nullable (backward compatible)
    op.add_column(
        "scheduled_playlist_syncs",
        sa.Column("execution_id", sa.String(64), nullable=True),
    )

    # Create index for lookup performance
    op.create_index(
        "ix_scheduled_playlist_syncs_execution_id",
        "scheduled_playlist_syncs",
        ["execution_id"],
    )

    # Unique constraint per user. Only enforced for ad-hoc rows ("once") that
    # carry an idempotency key, so rows without a key do not collide and a
    # scheduled row (whose key is scoped to that schedule) is not constrained.
    op.create_index(
        "uq_sync_execution_per_user",
        "scheduled_playlist_syncs",
        ["user_id", "execution_id"],
        unique=True,
        postgresql_where=sa.text("execution_id IS NOT NULL AND schedule_interval = 'once'"),
    )


def downgrade() -> None:
    op.drop_index(
        "uq_sync_execution_per_user",
        table_name="scheduled_playlist_syncs",
    )
    op.drop_index(
        "ix_scheduled_playlist_syncs_execution_id",
        table_name="scheduled_playlist_syncs",
    )
    op.drop_column("scheduled_playlist_syncs", "execution_id")
