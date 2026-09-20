"""Add error_message to sync_runs.

Revision ID: 005_sync_runs_error_message
Revises: 004_sync_runs_execution_id_index
Create Date: 2026-09-20

Pre-flight target connection failures (and pipeline errors) are recorded on
the run so the History/Pipeline UI can show why it failed instead of leaving
the user to guess from track-level failure counts.
"""

import sqlalchemy as sa

from alembic import op

revision = "005_sync_runs_error_message"
down_revision = "004_sync_runs_execution_id_index"
branch_labels = None
depends_on = None


def upgrade() -> None:
    op.add_column("sync_runs", sa.Column("error_message", sa.Text(), nullable=True))


def downgrade() -> None:
    op.drop_column("sync_runs", "error_message")
