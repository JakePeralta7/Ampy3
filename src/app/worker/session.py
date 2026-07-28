"""Database session management and async bridge for Celery workers."""

import asyncio
from collections.abc import Iterator
from contextlib import contextmanager

from sqlalchemy.orm import Session

from src.app.db import SessionLocal


@contextmanager
def session_scope() -> Iterator[Session]:
    """Provide a transactional database session scope.

    Commits on success, rolls back on exception, always closes.
    """
    session = SessionLocal()
    try:
        yield session
        session.commit()
    except Exception:
        session.rollback()
        raise
    finally:
        session.close()


def run_async(coro):
    """Execute an async coroutine from a sync Celery worker context."""
    return asyncio.run(coro)
