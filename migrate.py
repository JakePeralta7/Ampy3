#!/usr/bin/env python
"""Database bootstrap and Alembic migration utility.

Fresh databases are created from the current ORM models and stamped at the
Alembic baseline. Use Alembic migrations for every schema change after that.

Usage:
    python migrate.py bootstrap  # Create/stamp a fresh database, or apply upgrades
    python migrate.py upgrade    # Apply pending migrations to a stamped database
    python migrate.py status     # Show current Alembic revision
    python migrate.py autogen    # Generate a new migration from model changes
"""

import asyncio
import sys

from alembic.config import Config
from sqlalchemy import create_engine, text

from alembic import command
from src.app.db import init_db
from src.app.settings import settings


def _alembic_cfg() -> Config:
    cfg = Config("alembic/alembic.ini")
    cfg.set_main_option("sqlalchemy.url", settings.database_url)
    return cfg


def _current_revision() -> str | None:
    engine = create_engine(settings.database_url)
    try:
        with engine.connect() as conn:
            row = conn.execute(text("SELECT version_num FROM alembic_version LIMIT 1")).fetchone()
            return row[0] if row else None
    except Exception:
        return None
    finally:
        engine.dispose()


def upgrade() -> None:
    """Apply pending migrations to an Alembic-managed database."""
    print(f"Current revision: {_current_revision()}")
    command.upgrade(_alembic_cfg(), "head")
    print(f"New revision:     {_current_revision()}")


def bootstrap() -> None:
    """Create and stamp a fresh database, or upgrade an existing one."""
    print(f"Current revision: {_current_revision()}")
    asyncio.run(init_db())
    print(f"New revision:     {_current_revision()}")


def status() -> None:
    print(f"Current revision: {_current_revision()}")
    command.history(_alembic_cfg())


def autogen() -> None:
    msg = input("Migration message: ").strip() or "auto"
    command.revision(_alembic_cfg(), message=msg, autogenerate=True)


if __name__ == "__main__":
    actions = {"bootstrap": bootstrap, "upgrade": upgrade, "status": status, "autogen": autogen}
    action = sys.argv[1] if len(sys.argv) > 1 else ""
    if action not in actions:
        print(f"Usage: python migrate.py [{' | '.join(actions)}]")
        sys.exit(1)
    try:
        actions[action]()
    except Exception as e:
        print(f"Error: {e}")
        import traceback

        traceback.print_exc()
        sys.exit(1)
