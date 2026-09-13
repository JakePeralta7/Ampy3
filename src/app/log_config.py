"""Central logging configuration shared by the API and Celery worker."""

import logging
import logging.config
from contextvars import ContextVar
from typing import Any

LEVELS = {
    "debug": logging.DEBUG,
    "info": logging.INFO,
    "warning": logging.WARNING,
    "error": logging.ERROR,
    "critical": logging.CRITICAL,
}

NOISY_LOGGERS = (
    "httpcore",
    "httpx",
    "urllib3",
    "aiohttp",
    "alembic",
    # Celery's per-task dispatch/completion lines embed (truncated) task
    # payloads; the app's own lifecycle logs carry the equivalent context.
    "celery.app.trace",
    "celery.worker.strategy",
)

#: Worker execution context (task/sync/target IDs). Populated by the Celery
#: worker via ``src/app/worker/log.py`` and attached to records by
#: ``TaskContextFilter``.
task_context: ContextVar[dict[str, str]] = ContextVar("task_context")

JSON_FORMAT = (
    "%(asctime)s %(levelname)s %(name)s %(message)s "
    "%(exc_info)s %(task_id)s %(task_name)s %(sync_id)s %(target_id)s"
)

CONSOLE_FORMAT = "%(asctime)s %(levelname)s %(name)s %(message)s"


class TaskContextFilter(logging.Filter):
    """Attach worker task/sync/target IDs to every log record."""

    def filter(self, record: logging.LogRecord) -> bool:
        ctx = task_context.get({})
        record.task_id = ctx.get("task_id", "-")
        record.task_name = ctx.get("task_name", "-")
        record.sync_id = ctx.get("sync_id", "-")
        record.target_id = ctx.get("target_id", "-")
        return True


class TaskContextFormatter(logging.Formatter):
    """Append the worker context bracket to console lines only when active.

    The API never populates ``task_context``, so its console output stays
    clean; the worker renders ``[task_id | sync=… | target=…]`` while a task
    runs. The JSON formatter uses the filter-injected ``-`` defaults instead.
    """

    def format(self, record: logging.LogRecord) -> str:
        message = super().format(record)
        ctx = task_context.get({})
        if ctx:
            message = (
                f"{message} [{ctx.get('task_id', '-')} | "
                f"sync={ctx.get('sync_id', '-')} | "
                f"target={ctx.get('target_id', '-')}]"
            )
        return message


def setup_logging(level: str = "info", log_format: str = "json") -> None:
    """Configure the root logger with a reusable formatter and level.

    Args:
        level: One of ``debug``/``info``/``warning``/``error``/``critical``.
        log_format: ``json`` (python-json-logger) or ``console`` (human-readable).
    """
    if level not in LEVELS:
        raise ValueError(f"Unknown log level: {level!r}")
    if log_format not in ("json", "console"):
        raise ValueError(f"Unknown log format: {log_format!r}")

    logging.config.dictConfig(
        {
            "version": 1,
            "disable_existing_loggers": False,
            "filters": {"task_context": {"()": TaskContextFilter}},
            "formatters": {
                "json": {
                    "()": "pythonjsonlogger.json.JsonFormatter",
                    "format": JSON_FORMAT,
                    "rename_fields": {
                        "asctime": "time",
                        "levelname": "level",
                        "name": "logger",
                    },
                },
                "console": {
                    "()": TaskContextFormatter,
                    "format": CONSOLE_FORMAT,
                    "datefmt": "%Y-%m-%d %H:%M:%S",
                },
            },
            "handlers": {
                "console": {
                    "class": "logging.StreamHandler",
                    "formatter": log_format,
                    "filters": ["task_context"],
                    "stream": "ext://sys.stdout",
                },
            },
            "root": {"handlers": ["console"], "level": LEVELS[level]},
            "loggers": {name: {"level": "WARNING"} for name in NOISY_LOGGERS}
            | {
                # uvicorn configures these before ``setup_logging`` runs; route
                # access lines through the console handler so they stay valid
                # JSON objects (one per line) instead of bare text.
                "uvicorn": {"handlers": ["console"], "level": "INFO", "propagate": False},
                "uvicorn.access": {"handlers": ["console"], "level": "INFO", "propagate": False},
                # Pre-empt Celery's plaintext stderr handler: ``setup_logging``
                # runs before ``Logging.setup``, so once this handler exists
                # ``setup_task_loggers`` leaves ``celery.task`` alone.
                "celery.task": {"handlers": ["console"], "level": "WARNING", "propagate": False},
            },
        }
    )
