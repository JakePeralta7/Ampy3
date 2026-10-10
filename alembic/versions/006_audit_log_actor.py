"""Add actor_user_id to audit_log.

Revision ID: 006_audit_log_actor
Revises: 005_sync_runs_error_message
Create Date: 2026-09-22

Audit entries are now attributed to the authenticated user who performed the
action (captured by the session middleware), so the audit trail shows who
changed what instead of only what changed.
"""

import sqlalchemy as sa

from alembic import op

revision = "006_audit_log_actor"
down_revision = "005_sync_runs_error_message"
branch_labels = None
depends_on = None


def upgrade() -> None:
    op.add_column("audit_log", sa.Column("actor_user_id", sa.String(64), nullable=True))
    op.create_index("ix_audit_log_actor_user_id", "audit_log", ["actor_user_id"])


def downgrade() -> None:
    op.drop_index("ix_audit_log_actor_user_id", table_name="audit_log")
    op.drop_column("audit_log", "actor_user_id")