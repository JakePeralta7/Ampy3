"""rename plex columns to target

Revision ID: e7ac2c1b384f
Revises: 54f7e2d8b1a3
Create Date: 2026-07-21 19:23:32.838544

"""
from alembic import op
import sqlalchemy as sa


# revision identifiers, used by Alembic.
revision = 'e7ac2c1b384f'
down_revision = '54f7e2d8b1a3'
branch_labels = None
depends_on = None


def upgrade() -> None:
    op.alter_column(
        "scheduled_playlist_syncs",
        "plex_playlist_name",
        new_column_name="target_playlist_name",
    )
    op.alter_column(
        "scheduled_playlist_syncs",
        "plex_playlist_id",
        new_column_name="target_playlist_id",
    )
    op.alter_column(
        "playlist_tracks",
        "match_plex_id",
        new_column_name="match_item_id",
    )


def downgrade() -> None:
    op.alter_column(
        "playlist_tracks",
        "match_item_id",
        new_column_name="match_plex_id",
    )
    op.alter_column(
        "scheduled_playlist_syncs",
        "target_playlist_id",
        new_column_name="plex_playlist_id",
    )
    op.alter_column(
        "scheduled_playlist_syncs",
        "target_playlist_name",
        new_column_name="plex_playlist_name",
    )
