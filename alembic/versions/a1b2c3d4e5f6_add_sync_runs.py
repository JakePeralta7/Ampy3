"""add sync_runs and sync_run_tracks tables

Revision ID: a1b2c3d4e5f6
Revises: e7ac2c1b384f
Create Date: 2026-07-22 12:00:00.000000

"""
from alembic import op
import sqlalchemy as sa


# revision identifiers, used by Alembic.
revision = 'a1b2c3d4e5f6'
down_revision = 'e7ac2c1b384f'
branch_labels = None
depends_on = None


def upgrade() -> None:
    op.create_table(
        'sync_runs',
        sa.Column('id', sa.Integer(), primary_key=True),
        sa.Column(
            'sync_id',
            sa.Integer(),
            sa.ForeignKey('scheduled_playlist_syncs.id', ondelete='CASCADE'),
            nullable=False,
            index=True,
        ),
        sa.Column('matched_count', sa.Integer(), nullable=False, server_default='0'),
        sa.Column('failed_count', sa.Integer(), nullable=False, server_default='0'),
        sa.Column(
            'created_at',
            sa.DateTime(timezone=True),
            server_default=sa.func.now(),
            nullable=False,
        ),
    )

    op.create_table(
        'sync_run_tracks',
        sa.Column('id', sa.Integer(), primary_key=True),
        sa.Column(
            'run_id',
            sa.Integer(),
            sa.ForeignKey('sync_runs.id', ondelete='CASCADE'),
            nullable=False,
            index=True,
        ),
        sa.Column('position', sa.Integer(), nullable=False, server_default='0'),
        sa.Column('source_title', sa.String(255), nullable=True),
        sa.Column('source_artist', sa.String(255), nullable=True),
        sa.Column('source_album', sa.String(255), nullable=True),
        sa.Column('source_duration_ms', sa.Integer(), nullable=True),
        sa.Column('source_id', sa.String(255), nullable=True),
        sa.Column('match_item_id', sa.String(255), nullable=True),
        sa.Column('match_title', sa.String(255), nullable=True),
        sa.Column('match_artist', sa.String(255), nullable=True),
        sa.Column('match_album', sa.String(255), nullable=True),
        sa.Column('match_duration', sa.Integer(), nullable=True),
        sa.Column('match_rule_id', sa.Integer(), nullable=True),
    )


def downgrade() -> None:
    op.drop_table('sync_run_tracks')
    op.drop_table('sync_runs')
