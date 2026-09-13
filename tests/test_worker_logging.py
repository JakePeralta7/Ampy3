"""Unit tests for worker logging context helpers (src/app/worker/log.py)."""

from src.app.log_config import task_context
from src.app.worker.log import task_scope, update_log_context


def test_update_log_context_merges_fields():
    token = task_context.set({})
    try:
        update_log_context(task_id="t-1", sync_id=7, target_id="Plex")
        update_log_context(task_name="sync_target_task")

        assert task_context.get() == {
            "task_id": "t-1",
            "task_name": "sync_target_task",
            "sync_id": "7",
            "target_id": "Plex",
        }
    finally:
        task_context.reset(token)


def test_update_log_context_keeps_existing_fields():
    token = task_context.set({"task_id": "t-1", "sync_id": "7"})
    try:
        update_log_context(target_id="Jellyfin")

        assert task_context.get()["task_id"] == "t-1"
        assert task_context.get()["sync_id"] == "7"
        assert task_context.get()["target_id"] == "Jellyfin"
    finally:
        task_context.reset(token)


def test_update_log_context_converts_int_sync_id():
    token = task_context.set({})
    try:
        update_log_context(sync_id=42)
        assert task_context.get()["sync_id"] == "42"
    finally:
        task_context.reset(token)


def test_task_scope_restores_previous_context():
    previous = {"task_id": "outer"}
    token = task_context.set(previous)
    try:
        with task_scope(task_id="inner", sync_id=42):
            assert task_context.get()["task_id"] == "inner"
            assert task_context.get()["sync_id"] == "42"

        assert task_context.get() == previous
    finally:
        task_context.reset(token)
