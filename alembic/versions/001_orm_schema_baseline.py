"""ORM schema baseline.

Revision ID: 001_orm_schema_baseline
Revises:
Create Date: 2026-07-25 00:00:00.000000

Fresh databases are created from SQLAlchemy ORM metadata before being stamped
with this revision. Future schema changes must use Alembic revisions that
depend on this baseline.
"""

revision = "001_orm_schema_baseline"
down_revision = None
branch_labels = None
depends_on = None


def upgrade() -> None:
    """The baseline is created by ORM metadata, so no migration SQL is needed."""


def downgrade() -> None:
    """The baseline is intentionally not reversible."""
