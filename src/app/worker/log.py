"""Worker logging context — binds Celery task and sync identifiers to logs.

Values set here are read by the ``TaskContextFilter`` in
``src.app.log_config`` and attached to every log record emitted while the
context is active, so worker modules don't need to thread IDs through every
logging call.
"""

from collections.abc import Iterator
from contextlib import contextmanager

from src.app.log_config import task_context


def update_log_context(
    *,
    task_id: str | None = None,
    task_name: str | None = None,
    sync_id: int | None = None,
    target_id: str | None = None,
) -> None:
    """Merge new fields into the active logging context, keeping the rest."""
    current = dict(task_context.get({}))
    if task_id is not None:
        current["task_id"] = task_id
    if task_name is not None:
        current["task_name"] = task_name
    if sync_id is not None:
        current["sync_id"] = str(sync_id)
    if target_id is not None:
        current["target_id"] = target_id
    task_context.set(current)


@contextmanager
def task_scope(
    *,
    task_id: str | None = None,
    task_name: str | None = None,
    sync_id: int | None = None,
    target_id: str | None = None,
) -> Iterator[None]:
    """Bind worker logging context for the duration of a block."""
    previous = task_context.get({})
    update_log_context(
        task_id=task_id,
        task_name=task_name,
        sync_id=sync_id,
        target_id=target_id,
    )
    try:
        yield
    finally:
        task_context.set(previous)
