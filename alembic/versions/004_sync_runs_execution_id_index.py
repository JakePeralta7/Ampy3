"""Create execution_id index on sync_runs (fix for 002 index=True ignored).

Revision ID: 004_sync_runs_execution_id_index
Revises: 003_index_hot_query_paths
Create Date: 2026-09-19

Alembic >=1.18.2 ignores Column.index=True in add_column operations.
Migration 002 added execution_id with index=True, but the index was never created.
This migration explicitly creates the index for databases that already ran 002.
"""

import sqlalchemy as sa

from alembic import op

revision = "004_sync_runs_execution_id_index"
down_revision = "003_index_hot_query_paths"
branch_labels = None
depends_on = None


def upgrade() -> None:
    # Check if index exists before creating (for DBs that already have it via fresh create_all)
    conn = op.get_bind()
    inspector = sa.inspect(conn)
    indexes = inspector.get_indexes("sync_runs")
    index_names = {idx["name"] for idx in indexes}

    if "ix_sync_runs_execution_id" not in index_names:
        op.create_index("ix_sync_runs_execution_id", "sync_runs", ["execution_id"])


def downgrade() -> None:
    op.drop_index("ix_sync_runs_execution_id", "sync_runs")
