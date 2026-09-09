"""Add execution_id to sync_runs.

Revision ID: 002_sync_run_execution_id
Revises: 001_orm_schema_baseline
Create Date: 2026-09-09 00:00:00.000000

Each sync invocation generates one execution_id; every SyncRun (and the fetch
phase) created by that invocation carries it, so executions can be grouped
exactly without timestamp heuristics.
"""

import sqlalchemy as sa
from alembic import op

revision = "002_sync_run_execution_id"
down_revision = "001_orm_schema_baseline"
branch_labels = None
depends_on = None


def upgrade() -> None:
    op.add_column(
        "sync_runs",
        sa.Column("execution_id", sa.String(length=64), nullable=True, index=True),
    )


def downgrade() -> None:
    op.drop_column("sync_runs", "execution_id")