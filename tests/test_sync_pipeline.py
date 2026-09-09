"""Unit tests for sync execution grouping by execution_id."""

from datetime import UTC, datetime, timedelta

from src.app.api.syncs import _select_execution
from src.app.models import SyncRun

BASE = datetime(2026, 1, 1, tzinfo=UTC)


def _run(
    run_id: int,
    minutes: int,
    execution_id: str | None = None,
    target_id: str = "Plex",
    status: str = "completed",
) -> SyncRun:
    return SyncRun(
        id=run_id,
        sync_id=1,
        target_id=target_id,
        status=status,
        matched_count=1,
        failed_count=0,
        created_at=BASE + timedelta(minutes=minutes),
        execution_id=execution_id,
    )


def test_selects_runs_sharing_execution_id():
    runs = [
        _run(1, 0, "exec-a", target_id="Plex"),
        _run(2, 1, "exec-a", target_id="Jellyfin"),
        _run(3, 2, "exec-b"),
    ]
    assert [r.id for r in _select_execution(runs, 1)] == [1, 2]


def test_recent_other_execution_is_not_merged_in():
    runs = [
        _run(1, 0, "exec-a"),
        _run(2, 5, "exec-b"),
    ]
    assert [r.id for r in _select_execution(runs, 1)] == [1]


def test_multi_target_execution_shared():
    runs = [
        _run(1, 0, "exec-a", target_id="Plex"),
        _run(2, 1, "exec-a", target_id="Jellyfin"),
    ]
    assert [r.id for r in _select_execution(runs, 1)] == [1, 2]


def test_retried_target_keeps_newest_run_per_target():
    runs = [
        _run(1, 0, "exec-a", status="failed"),
        _run(2, 1, "exec-a", status="completed"),
        _run(3, 2, "exec-a", target_id="Jellyfin"),
    ]
    assert [r.id for r in _select_execution(runs, 1)] == [2, 3]


def test_legacy_run_without_execution_id_shows_alone():
    runs = [
        _run(1, 0),
        _run(2, 1, "exec-a"),
        _run(3, 2, "exec-a"),
    ]
    assert [r.id for r in _select_execution(runs, 1)] == [1]


def test_unknown_run_id_returns_empty():
    runs = [_run(1, 0, "exec-a")]
    assert _select_execution(runs, 99) == []


def test_empty_runs_return_empty():
    assert _select_execution([], 1) == []
