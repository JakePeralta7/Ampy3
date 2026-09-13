"""Unit tests for the shared logging configuration (src/app/log_config.py)."""

import json
import logging

import pytest
from pythonjsonlogger.json import JsonFormatter

from src.app.log_config import (
    CONSOLE_FORMAT,
    TaskContextFilter,
    TaskContextFormatter,
    setup_logging,
    task_context,
)

CONTEXT_FIELDS = ("task_id", "task_name", "sync_id", "target_id")


def _root() -> logging.Logger:
    return logging.getLogger()


def _handler() -> logging.StreamHandler:
    handler = _root().handlers[0]
    assert isinstance(handler, logging.StreamHandler)
    return handler


def _record(msg: str = "hello") -> logging.LogRecord:
    return logging.LogRecord("test.log", logging.INFO, "test_file.py", 1, msg, (), None)


def _context_values(record: logging.LogRecord) -> dict[str, str]:
    return {key: str(getattr(record, key, "")) for key in CONTEXT_FIELDS}


def _run_task_filter(handler: logging.StreamHandler, record: logging.LogRecord) -> None:
    for flt in handler.filters:
        if isinstance(flt, TaskContextFilter):
            flt.filter(record)


def test_setup_logging_configures_root_logger():
    setup_logging(level="info", log_format="json")

    assert _root().level == logging.INFO
    assert isinstance(_handler().formatter, JsonFormatter)


def test_json_format_outputs_expected_fields():
    setup_logging(level="info", log_format="json")
    handler = _handler()

    record = _record()
    _run_task_filter(handler, record)
    assert handler.formatter is not None
    payload = json.loads(handler.formatter.format(record))

    assert payload["message"] == "hello"
    assert payload["level"] == "INFO"
    assert payload["logger"] == "test.log"
    assert payload["task_id"] == "-"
    assert payload["sync_id"] == "-"
    assert payload["target_id"] == "-"
    assert "time" in payload


def test_task_context_filter_injects_defaults():
    record = _record()
    assert TaskContextFilter().filter(record) is True
    assert _context_values(record) == {
        "task_id": "-",
        "task_name": "-",
        "sync_id": "-",
        "target_id": "-",
    }


def test_task_context_filter_reads_contextvar():
    token = task_context.set(
        {"task_id": "t-1", "task_name": "sync_playlists_task", "sync_id": "7", "target_id": "Plex"}
    )
    try:
        record = _record()
        assert TaskContextFilter().filter(record) is True
        assert _context_values(record) == {
            "task_id": "t-1",
            "task_name": "sync_playlists_task",
            "sync_id": "7",
            "target_id": "Plex",
        }
    finally:
        task_context.reset(token)


@pytest.mark.parametrize("level", ["bogus", ""])
def test_invalid_level_rejected(level):
    with pytest.raises(ValueError):
        setup_logging(level=level)


@pytest.mark.parametrize("log_format", ["xml", "yaml"])
def test_invalid_log_format_rejected(log_format):
    with pytest.raises(ValueError):
        setup_logging(log_format=log_format)


def test_noisy_loggers_silenced():
    setup_logging(level="info", log_format="json")

    assert logging.getLogger("httpx").level == logging.WARNING
    assert logging.getLogger("httpcore").level == logging.WARNING
    assert logging.getLogger("urllib3").level == logging.WARNING
    assert logging.getLogger("aiohttp").level == logging.WARNING
    assert logging.getLogger("alembic").level == logging.WARNING
    assert logging.getLogger("celery.app.trace").level == logging.WARNING
    assert logging.getLogger("celery.worker.strategy").level == logging.WARNING


def test_console_format_still_configurable():
    setup_logging(level="warning", log_format="console")

    handler = _handler()
    assert _root().level == logging.WARNING
    assert isinstance(handler.formatter, TaskContextFormatter)

    record = _record()
    _run_task_filter(handler, record)
    rendered = handler.formatter.format(record)
    # No task context on the API side -> no dead context bracket.
    assert "[" not in rendered
    assert "hello" in rendered


def test_task_context_formatter_renders_bracket_when_active():
    formatter = TaskContextFormatter(fmt=CONSOLE_FORMAT, datefmt="%Y-%m-%d %H:%M:%S")
    record = _record()

    token = task_context.set({"task_id": "t-1", "sync_id": "7", "target_id": "Plex"})
    try:
        rendered = formatter.format(record)
    finally:
        task_context.reset(token)

    assert "hello [t-1 | sync=7 | target=Plex]" in rendered
    assert rendered.startswith("2026") or rendered.startswith("2025")
