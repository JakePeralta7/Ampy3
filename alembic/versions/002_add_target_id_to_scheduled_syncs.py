"""add target_id to scheduled_playlist_syncs

Revision ID: 002
Revises: 001
Create Date: 2026-07-25 00:00:00.000000
"""

import sqlalchemy as sa

from alembic import op

# revision identifiers, used by Alembic.
revision = "002"
down_revision = "001"
branch_labels = None
depends_on = None


def upgrade() -> None:
    bind = op.get_bind()
    inspector = sa.inspect(bind)
    if not inspector.has_table("scheduled_playlist_syncs"):
        return
    cols = {c["name"] for c in inspector.get_columns("scheduled_playlist_syncs")}
    if "target_id" in cols:
        return

    op.add_column(
        "scheduled_playlist_syncs",
        sa.Column("target_id", sa.String(length=50), nullable=True, server_default="plex"),
    )
    op.execute("UPDATE scheduled_playlist_syncs SET target_id = 'plex' WHERE target_id IS NULL")
    op.alter_column("scheduled_playlist_syncs", "target_id", nullable=False)


def downgrade() -> None:
    bind = op.get_bind()
    inspector = sa.inspect(bind)
    if not inspector.has_table("scheduled_playlist_syncs"):
        return
    cols = {c["name"] for c in inspector.get_columns("scheduled_playlist_syncs")}
    if "target_id" not in cols:
        return

    op.drop_column("scheduled_playlist_syncs", "target_id")
