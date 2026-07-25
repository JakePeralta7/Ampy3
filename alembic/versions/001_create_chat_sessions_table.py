"""create chat_sessions table

Revision ID: 001
Revises:
Create Date: 2026-07-23 00:00:00.000000

"""
import sqlalchemy as sa

from alembic import op

# revision identifiers, used by Alembic.
revision = '001'
down_revision = None
branch_labels = None
depends_on = None


def upgrade() -> None:
    op.create_table(
        'chat_sessions',
        sa.Column('id', sa.String(64), nullable=False),
        sa.Column('plex_user_id', sa.String(64), nullable=False),
        sa.Column('preview', sa.String(255), nullable=False),
        sa.Column('title', sa.String(255), nullable=True),
        sa.Column('created_at', sa.DateTime(timezone=True), server_default=sa.func.now(), nullable=False),
        sa.Column('updated_at', sa.DateTime(timezone=True), server_default=sa.func.now(), nullable=False, onupdate=sa.func.now()),
        sa.PrimaryKeyConstraint('id'),
        sa.Index('ix_chat_sessions_plex_user_id', 'plex_user_id'),
        sa.Index('ix_chat_sessions_created_at', 'created_at'),
        sa.Index('ix_chat_sessions_updated_at', 'updated_at'),
    )


def downgrade() -> None:
    op.drop_table('chat_sessions')
