"""Database configuration and initialization."""
from collections.abc import AsyncGenerator, Generator

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


async def init_db() -> None:
    """Create all tables from ORM models, then seed default rules.

    Uses ``create_all(checkfirst=True)`` so existing tables are never
    dropped — safe to call on every startup.  Future schema changes
    should be handled via Alembic migrations generated against the
    updated models.
    """
    import src.app.models  # noqa: F401 — registers all ORM models on Base

    async with async_engine.begin() as conn:
        await conn.run_sync(Base.metadata.create_all, checkfirst=True)

    from src.app.match_rules.loader import seed_default_rules
    await seed_default_rules()


async def close_db() -> None:
    """Close database connections."""
    await async_engine.dispose()
    sync_engine.dispose()
