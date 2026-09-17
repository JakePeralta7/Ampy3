"""Database session management and async bridge for Celery workers."""

import asyncio
import logging
import threading
import time
from collections.abc import Iterator
from concurrent.futures import TimeoutError as FuturesTimeoutError
from contextlib import contextmanager

from sqlalchemy.orm import Session

from src.app.db import SessionLocal

logger = logging.getLogger(__name__)

_loop: asyncio.AbstractEventLoop | None = None
_loop_lock = threading.Lock()
_loop_thread: threading.Thread | None = None
_shutdown_registered = False


def _get_run_timeout_seconds() -> int:
    """Get timeout derived from Celery config: soft_time_limit - 3min buffer (min 60s)."""
    from src.app.worker.app import celery_app

    return max(60, (celery_app.conf.task_soft_time_limit or 3480) - 180)


def _worker_loop() -> asyncio.AbstractEventLoop:
    """Return the single persistent event loop for Celery workers.

    ``asyncio.run()`` creates and closes a fresh loop on every call, stranding
    any long-lived async resource (httpx clients, cached aiohttp sessions)
    bound to the now-closed loop. A single long-running loop in a daemon
    thread keeps those clients valid for the lifetime of the worker process.
    """
    global _loop, _loop_thread, _shutdown_registered
    if _loop is None or _loop.is_closed():
        with _loop_lock:
            if _loop is None or _loop.is_closed():
                _loop = asyncio.new_event_loop()
                _loop_thread = threading.Thread(
                    target=_loop.run_forever,
                    name="ampy-worker-asyncio",
                    daemon=True,
                )
                _loop_thread.start()

                if not _shutdown_registered:
                    from celery.signals import worker_shutdown

                    def _shutdown(**kwargs):
                        if _loop and not _loop.is_closed():
                            _loop.call_soon_threadsafe(_loop.stop)
                        if _loop_thread and _loop_thread.is_alive():
                            _loop_thread.join(timeout=5)

                    worker_shutdown.connect(_shutdown)
                    _shutdown_registered = True
    assert _loop is not None
    return _loop


def run_async(coro):
    """Execute an async coroutine from a sync Celery worker context."""
    loop = _worker_loop()
    future = asyncio.run_coroutine_threadsafe(coro, loop)
    try:
        return future.result(timeout=_get_run_timeout_seconds())
    except FuturesTimeoutError:
        future.cancel()
        timeout = _get_run_timeout_seconds()
        raise TimeoutError(f"Coroutine did not complete within {timeout}s") from None


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
        session.expire_all()  # Ensure objects are refreshed on next access
        logger.debug("Session committed in %.2fms", (time.monotonic() - _t0) * 1000)
    except Exception:
        session.rollback()
        logger.debug("Session rolled back", exc_info=True)
        raise
    finally:
        session.close()
