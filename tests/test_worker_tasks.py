"""Tests for worker task helpers (pre-flight connection check, failed runs).

These exercise the worker's pre-flight and failure-recording helpers with a
fake session/target — no real database or Celery broker is required.
"""

import asyncio
from contextlib import nullcontext

import pytest

from src.app.worker import tasks
from src.app.worker.errors import SyncTargetConnectionError


class _FakeDB:
    """Paper stand-in: ``by_entity[SyncRun]`` drives what selects return."""

    def __init__(self):
        self.calls = []
        self.added = []
        self.by_entity: dict = {}

    def execute(self, stmt):
        entity = stmt.column_descriptions[0]["type"]
        rows = self.by_entity.get(entity, [])
        return _FakeResult(rows)

    def add(self, obj):
        self.added.append(obj)

    def flush(self):
        pass


class _FakeResult:
    def __init__(self, rows: list):
        self._rows = rows

    def scalars(self):
        return self

    def first(self):
        return self._rows[0] if self._rows else None


class _FakeCtx:
    """SyncContext stand-in with a settable target and fake session."""

    def __init__(self, db, target):
        self.sync_id = 42
        self.target_id = "Plex"
        self.execution_id = "exec-1"
        self.target = target
        self._db = db

    def session(self):
        return nullcontext(self._db)


def _run_coro(coro):
    """run_async replacement that actually awaits the coroutine."""
    if asyncio.iscoroutine(coro):
        return asyncio.run(coro)
    raise TypeError(f"expected coroutine, got {type(coro)!r}")


class TestVerifyTargetConnection:
    def test_passes_when_target_reachable(self, monkeypatch):
        async def ok():
            return None

        ctx = _FakeCtx(_FakeDB(), _FakeTarget(ok))
        monkeypatch.setattr("src.app.worker.session.run_async", _run_coro)

        tasks._verify_target_connection(ctx)  # no exception

    def test_wraps_target_error(self, monkeypatch):
        async def boom():
            raise RuntimeError("connection refused")

        ctx = _FakeCtx(_FakeDB(), _FakeTarget(boom))
        monkeypatch.setattr("src.app.worker.session.run_async", _run_coro)

        with pytest.raises(SyncTargetConnectionError) as excinfo:
            tasks._verify_target_connection(ctx)

        assert "connection refused" in str(excinfo.value)
        assert "Plex" in str(excinfo.value)


class TestRecordFailedRun:
    def test_creates_run_when_none_exists(self):
        fake_db = _FakeDB()
        ctx = _FakeCtx(fake_db, None)

        tasks._record_failed_run(ctx, "boom")

        assert len(fake_db.added) == 1
        run = fake_db.added[0]
        assert run.status == "failed"
        assert run.error_message == "boom"
        assert run.matched_count == 0
        assert run.execution_id == "exec-1"

    def test_reuses_running_run(self):
        fake_db = _FakeDB()
        run = tasks.SyncRun(
            sync_id=42,
            target_id="Plex",
            status="running",
            matched_count=0,
            failed_count=0,
            execution_id="exec-1",
        )
        fake_db.by_entity = {tasks.SyncRun: [run]}
        ctx = _FakeCtx(fake_db, None)

        tasks._record_failed_run(ctx, "target unreachable")

        assert fake_db.added == []
        assert run.status == "failed"
        assert run.error_message == "target unreachable"

    def test_truncates_long_errors(self):
        fake_db = _FakeDB()
        fake_db.by_entity = {tasks.SyncRun: []}
        ctx = _FakeCtx(fake_db, None)

        tasks._record_failed_run(ctx, "x" * 5000)

        assert fake_db.added[0].error_message == "x" * 2000


class _FakeTarget:
    def __init__(self, test_connection):
        self.test_connection = test_connection
