"""Database session management and async bridge for Celery workers."""

import asyncio
import logging
import time
from collections.abc import Iterator
from contextlib import contextmanager

from sqlalchemy.orm import Session

from src.app.db import SessionLocal

logger = logging.getLogger(__name__)


@contextmanager
def session_scope() -> Iterator[Session]:
    """Provide a transactional database session scope.

    Commits on success, rolls back on exception, always closes.
    """
    session = SessionLocal()
    _t0 = time.monotonic()
    try:
        yield session
        session.commit()
        logger.debug("Session committed in %.2fms", (time.monotonic() - _t0) * 1000)
    except Exception:
        session.rollback()
        logger.debug("Session rolled back", exc_info=True)
        raise
    finally:
        session.close()


def run_async(coro):
    """Execute an async coroutine from a sync Celery worker context."""
    return asyncio.run(coro)
