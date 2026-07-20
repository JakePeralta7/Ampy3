#!/usr/bin/env python
"""Database migration utility script.

This script helps manage database migrations and can fix migration state issues.

Usage:
    python migrate.py upgrade    # Apply all pending migrations
    python migrate.py reset      # Reset migration state and reapply all
    python migrate.py status     # Show current migration status
"""
import asyncio
import sys
from sqlalchemy import create_engine, inspect, text
from alembic.config import Config
from alembic import command

from src.app.settings import settings


def get_current_revision(engine):
    """Get the current alembic revision."""
    try:
        with engine.connect() as conn:
            result = conn.execute(text("SELECT version_num FROM alembic_version LIMIT 1"))
            row = result.fetchone()
            return row[0] if row else None
    except Exception:
        return None


def upgrade_migrations():
    """Upgrade to the latest migration."""
    alembic_cfg = Config("alembic/alembic.ini")
    alembic_cfg.set_main_option("sqlalchemy.url", settings.database_url)
    
    engine = create_engine(settings.database_url)
    try:
        current_rev = get_current_revision(engine)
        print(f"Current revision: {current_rev}")
        
        print("Upgrading to head...")
        command.upgrade(alembic_cfg, "head")
        
        new_rev = get_current_revision(engine)
        print(f"New revision: {new_rev}")
        print("✓ Migration upgrade completed successfully")
    finally:
        engine.dispose()


def reset_migrations():
    """Reset migration state (downgrade to initial, then upgrade to head)."""
    alembic_cfg = Config("alembic/alembic.ini")
    alembic_cfg.set_main_option("sqlalchemy.url", settings.database_url)
    
    engine = create_engine(settings.database_url)
    try:
        current_rev = get_current_revision(engine)
        print(f"Current revision: {current_rev}")
        
        # Downgrade to the initial migration
        print("Downgrading to initial revision...")
        command.downgrade(alembic_cfg, "54f7e2d8b1a3")
        
        # Upgrade to head
        print("Upgrading to head...")
        command.upgrade(alembic_cfg, "head")
        
        new_rev = get_current_revision(engine)
        print(f"New revision: {new_rev}")
        print("✓ Migration reset completed successfully")
    finally:
        engine.dispose()


def show_status():
    """Show migration status."""
    alembic_cfg = Config("alembic/alembic.ini")
    alembic_cfg.set_main_option("sqlalchemy.url", settings.database_url)
    
    engine = create_engine(settings.database_url)
    try:
        current_rev = get_current_revision(engine)
        print(f"Current revision: {current_rev}")
        
        # Show available migrations
        print("\nAvailable migrations:")
        command.history(alembic_cfg)
    finally:
        engine.dispose()


if __name__ == "__main__":
    if len(sys.argv) < 2:
        print("Usage: python migrate.py [upgrade|reset|status]")
        sys.exit(1)
    
    action = sys.argv[1]
    
    try:
        if action == "upgrade":
            upgrade_migrations()
        elif action == "reset":
            reset_migrations()
        elif action == "status":
            show_status()
        else:
            print(f"Unknown action: {action}")
            sys.exit(1)
    except Exception as e:
        print(f"✗ Error: {e}")
        import traceback
        traceback.print_exc()
        sys.exit(1)
