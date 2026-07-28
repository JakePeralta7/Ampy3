"""Database configuration and initialization."""

from collections.abc import AsyncGenerator, Generator

from alembic.config import Config
from sqlalchemy import create_engine, inspect
from sqlalchemy.ext.asyncio import AsyncSession, async_sessionmaker, create_async_engine
from sqlalchemy.orm import DeclarativeBase, Session, sessionmaker

from alembic import command
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
    pool_size=20,
    max_overflow=10,
    pool_recycle=3600,
)

# Synchronous session factory for Celery tasks
SessionLocal = sessionmaker(
    bind=sync_engine,
    autocommit=False,
    autoflush=False,
)


# Base class for ORM models
class Base(DeclarativeBase):
    pass


async def get_async_session() -> AsyncGenerator[AsyncSession]:
    """Dependency for getting async database sessions."""
    async with AsyncSessionLocal() as session:
        yield session


def get_sync_session() -> Generator[Session]:
    """Dependency for getting synchronous database sessions (for Celery)."""
    db = SessionLocal()
    try:
        yield db
    finally:
        db.close()


def _alembic_config() -> Config:
    cfg = Config("alembic/alembic.ini")
    cfg.set_main_option("sqlalchemy.url", settings.database_url)
    return cfg


async def _is_alembic_managed() -> bool:
    """Return whether the database has already been stamped by Alembic."""
    async with async_engine.connect() as conn:
        return await conn.run_sync(
            lambda sync_conn: inspect(sync_conn).has_table("alembic_version")
        )


async def init_db() -> None:
    """Bootstrap fresh databases and upgrade Alembic-managed databases.

    A fresh database is created from the current ORM metadata and stamped at
    Alembic head. Once stamped, all later schema changes must be handled by
    Alembic migrations; ``create_all`` is never run for an existing database.
    """
    import src.app.models  # noqa: F401

    cfg = _alembic_config()
    if await _is_alembic_managed():
        command.upgrade(cfg, "head")
    else:
        async with async_engine.begin() as conn:
            await conn.run_sync(Base.metadata.create_all, checkfirst=True)
        command.stamp(cfg, "head")

    from src.app.match_rules.loader import seed_default_rules

    await seed_default_rules()


async def close_db() -> None:
    """Close database connections."""
    await async_engine.dispose()
    sync_engine.dispose()
