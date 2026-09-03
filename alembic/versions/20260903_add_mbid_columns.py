"""add mbid columns to playlist_tracks and sync_run_tracks

Revision ID: 20260903_add_mbid_columns
Revises: 1375947a8e70
Create Date: 2026-09-03

"""
from alembic import op
import sqlalchemy as sa

# revision identifiers, used by Alembic.
revision = "20260903_add_mbid_columns"
down_revision = "1375947a8e70"
branch_labels = None
depends_on = None


def upgrade() -> None:
    op.add_column(
        "playlist_tracks",
        sa.Column("source_mbid", sa.String(36), nullable=True),
    )
    op.add_column(
        "playlist_tracks",
        sa.Column("source_artist_mbid", sa.String(36), nullable=True),
    )
    op.add_column(
        "playlist_tracks",
        sa.Column("source_album_mbid", sa.String(36), nullable=True),
    )

    op.add_column(
        "sync_run_tracks",
        sa.Column("source_mbid", sa.String(36), nullable=True),
    )
    op.add_column(
        "sync_run_tracks",
        sa.Column("source_artist_mbid", sa.String(36), nullable=True),
    )
    op.add_column(
        "sync_run_tracks",
        sa.Column("source_album_mbid", sa.String(36), nullable=True),
    )


def downgrade() -> None:
    op.drop_column("playlist_tracks", "source_mbid")
    op.drop_column("playlist_tracks", "source_artist_mbid")
    op.drop_column("playlist_tracks", "source_album_mbid")

    op.drop_column("sync_run_tracks", "source_mbid")
    op.drop_column("sync_run_tracks", "source_artist_mbid")
    op.drop_column("sync_run_tracks", "source_album_mbid")