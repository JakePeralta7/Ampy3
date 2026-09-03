"""add status to sync_runs

Revision ID: 1375947a8e70
Revises: 001_orm_schema_baseline
Create Date: 2026-09-01 16:38:42.272040

"""
from alembic import op
import sqlalchemy as sa

# revision identifiers, used by Alembic.
revision = "1375947a8e70"
down_revision = "001_orm_schema_baseline"
branch_labels = None
depends_on = None


def upgrade() -> None:
    op.add_column(
        "sync_runs",
        sa.Column("status", sa.String(length=20), server_default="running", nullable=False),
    )


def downgrade() -> None:
    op.drop_column("sync_runs", "status")