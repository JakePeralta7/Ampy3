"""Database configuration and initialization."""
import asyncio
import os
from collections.abc import AsyncGenerator, Generator
from pathlib import Path

from sqlalchemy import create_engine
from sqlalchemy.ext.asyncio import (
    AsyncSession,
    async_sessionmaker,
    create_async_engine,
)
from sqlalchemy.orm import Session, declarative_base, sessionmaker

from src.app.settings import settings

# Create async engine for PostgreSQL (used by FastAPI)
async_engine = create_async_engine(
    # Convert postgresql:// to postgresql+asyncpg://
    settings.database_url.replace("postgresql://", "postgresql+asyncpg://"),
    echo=False,
    future=True,
    pool_size=20,
    max_overflow=10,
    pool_recycle=3600,
)

# Async session factory for FastAPI endpoints
AsyncSessionLocal = async_sessionmaker(
    async_engine,
    class_=AsyncSession,
    expire_on_commit=False,
    future=True,
)

# Create synchronous engine for Celery tasks
sync_engine = create_engine(
    settings.database_url,
    pool_pre_ping=True,
    echo=False,
)

# Synchronous session factory for Celery tasks
SessionLocal = sessionmaker(
    bind=sync_engine,
    autocommit=False,
    autoflush=False,
)

# Base class for ORM models
Base = declarative_base()


async def get_async_session() -> AsyncGenerator[AsyncSession, None]:
    """Dependency for getting async database sessions."""
    async with AsyncSessionLocal() as session:
        yield session


def get_sync_session() -> Generator[Session, None, None]:
    """Dependency for getting synchronous database sessions (for Celery)."""
    db = SessionLocal()
    try:
        yield db
    finally:
        db.close()


def _run_alembic_migrations() -> None:
    """Run Alembic migrations to bring the database to the latest revision."""
    import subprocess
    import sys

    result = subprocess.run(
        [sys.executable, "-m", "alembic", "-c", "alembic/alembic.ini", "upgrade", "head"],
        capture_output=True,
        text=True,
        cwd=str(Path(__file__).resolve().parent.parent.parent),
        env={
            **os.environ,
            "DATABASE_URL": settings.database_url,
        },
    )
    if result.stdout:
        for line in result.stdout.strip().splitlines():
            print(line)
    if result.returncode != 0:
        stderr = result.stderr.strip() if result.stderr else ""
        print(f"Migration failed (exit {result.returncode}): {stderr}")
        raise RuntimeError(f"alembic upgrade failed: {stderr}")


async def init_db():
    """Initialize database via Alembic migrations (runs subprocess at startup)."""
    await asyncio.to_thread(_run_alembic_migrations)


async def close_db():
    """Close database connections."""
    await async_engine.dispose()
    sync_engine.dispose()
