"""Add indexes for hot query paths.

Revision ID: 003_index_hot_query_paths
Revises: 002_sync_run_execution_id
Create Date: 2026-09-14 00:00:00.000000

Adds a composite (is_active, priority) index on match_rules (every match
engine run filters active rules by priority) and an index on
schedule_targets.target_id (target-scoped sync lookups).
"""

from alembic import op

revision = "003_index_hot_query_paths"
down_revision = "002_sync_run_execution_id"
branch_labels = None
depends_on = None


def upgrade() -> None:
    op.create_index(
        "ix_match_rules_active_priority",
        "match_rules",
        ["is_active", "priority"],
        unique=False,
    )
    op.create_index(
        "ix_schedule_targets_target_id", "schedule_targets", ["target_id"], unique=False
    )


def downgrade() -> None:
    op.drop_index("ix_schedule_targets_target_id", table_name="schedule_targets")
    op.drop_index("ix_match_rules_active_priority", table_name="match_rules")
