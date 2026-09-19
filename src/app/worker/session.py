"""Database session management and async bridge for Celery workers."""

import asyncio
import logging
import threading
import time
from collections.abc import Iterator
from concurrent.futures import TimeoutError as FuturesTimeoutError
from contextlib import contextmanager

from celery.signals import worker_process_init, worker_shutdown
from sqlalchemy.orm import Session

from src.app.db import SessionLocal

logger = logging.getLogger(__name__)

_loop: asyncio.AbstractEventLoop | None = None
_loop_lock = threading.Lock()
_loop_thread: threading.Thread | None = None
_loop_ready: threading.Event = threading.Event()


def _get_run_timeout_seconds() -> int:
    """Get timeout derived from Celery config: soft_time_limit - 3min buffer (min 60s)."""
    from src.app.worker.app import celery_app

    return max(60, (celery_app.conf.task_soft_time_limit or 3480) - 180)


@worker_process_init.connect
def _init_worker_loop(**kwargs) -> None:
    """Initialize a fresh event loop in each forked worker process.

    Prefork workers inherit the parent's memory but NOT the thread driving the
    event loop. Creating a new loop per process avoids the "inherited dead loop"
    problem where coroutines hang indefinitely on a loop with no driving thread.
    """
    global _loop, _loop_thread
    _loop = asyncio.new_event_loop()
    _loop_thread = threading.Thread(
        target=_loop.run_forever,
        name="ampy-worker-asyncio",
        daemon=True,
    )
    _loop_ready.set()
    _loop_thread.start()
    logger.debug("Initialized worker event loop in process %s", threading.current_thread().ident)


@worker_shutdown.connect
def _shutdown_worker_loop(**kwargs) -> None:
    """Stop the worker's event loop and join the driver thread."""
    global _loop, _loop_thread
    if _loop and not _loop.is_closed():
        _loop.call_soon_threadsafe(_loop.stop)
    if _loop_thread and _loop_thread.is_alive():
        _loop_thread.join(timeout=5)
    logger.debug("Shutdown worker event loop")


def _create_loop() -> None:
    """Create the persistent event loop and its driver thread."""
    global _loop, _loop_thread
    with _loop_lock:
        if _loop is None or _loop.is_closed():
            _loop = asyncio.new_event_loop()
            _loop_thread = threading.Thread(
                target=_loop.run_forever,
                name="ampy-worker-asyncio",
                daemon=True,
            )
            _loop_thread.start()
            logger.debug(
                "Created worker event loop in process %s", threading.current_thread().ident
            )


def _worker_loop() -> asyncio.AbstractEventLoop:
    """Return the persistent event loop for this worker process.

    The loop is created by `_init_worker_loop` via the `worker_process_init`
    signal, which fires once per forked child process. Under pools that do not
    emit that signal (solo/threads), the loop is created lazily on first use.
    """
    global _loop
    if (_loop is None or _loop.is_closed()) and not _loop_ready.wait(timeout=1):
        _create_loop()
    loop = _loop
    if loop is None or loop.is_closed():
        raise RuntimeError("Worker event loop is not running")
    return loop


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
