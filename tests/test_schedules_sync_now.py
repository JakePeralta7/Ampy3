"""409/skip behavior for manual and bulk sync-now when a run is in flight."""

from types import SimpleNamespace

import pytest
from fastapi import HTTPException

from src.app.api import schedules as schedules_api


class FakeSyncs:
    def __init__(self, syncs):
        self.syncs = syncs

    def scalar_one_or_none(self):
        return self.syncs[0]

    def scalars(self):
        return SimpleNamespace(all=lambda: self.syncs)


class FakeDb:
    def __init__(self, syncs=None):
        self.syncs = syncs or [
            SimpleNamespace(id=1, target_playlist_name="Mix 1"),
            SimpleNamespace(id=2, target_playlist_name="Mix 2"),
        ]

    async def execute(self, stmt):
        return FakeSyncs(self.syncs)


class FakeAsyncResult:
    def __init__(self, task_id):
        self.id = task_id


def _patch_trigger(monkeypatch, behavior):
    monkeypatch.setattr(
        "src.app.services.scheduler.SchedulerService.trigger_sync_now",
        staticmethod(behavior),
    )


async def _blocked_trigger(sync):
    return None


async def _free_trigger(sync):
    return FakeAsyncResult("task-1")


async def _partial_bulk_trigger(sync):
    return None if sync.id == 1 else FakeAsyncResult(f"task-{sync.id}")


def _patch_log(monkeypatch, recorder=None):
    async def fake_log(**kwargs):
        if recorder is not None:
            recorder.append(kwargs)

    monkeypatch.setattr(schedules_api, "log_event", fake_log)


async def test_single_sync_now_returns_409_when_run_in_flight(monkeypatch):
    _patch_trigger(monkeypatch, _blocked_trigger)

    with pytest.raises(HTTPException) as exc:
        await schedules_api.trigger_sync_now(
            sync_id=1,
            db=FakeDb([SimpleNamespace(id=1, target_playlist_name="Mix 1", user_id="u")]),
            user={"plex_user_id": "u"},
        )

    assert exc.value.status_code == 409


async def test_single_sync_now_dispatches_and_logs_when_lock_free(monkeypatch):
    logged = []
    _patch_log(monkeypatch, logged)
    _patch_trigger(monkeypatch, _free_trigger)

    response = await schedules_api.trigger_sync_now(
        sync_id=1,
        db=FakeDb([SimpleNamespace(id=1, target_playlist_name="Mix 1", user_id="u")]),
        user={"plex_user_id": "u"},
    )

    assert response.task_id == "task-1"
    assert logged and logged[0]["event_type"] == "sync.manually_triggered"


async def test_bulk_sync_now_skips_locked_schedules(monkeypatch):
    logged = []
    _patch_log(monkeypatch, logged)
    _patch_trigger(monkeypatch, _partial_bulk_trigger)

    response = await schedules_api.bulk_sync_now(
        body=SimpleNamespace(ids=[1, 2]),
        db=FakeDb(
            [
                SimpleNamespace(id=1, target_playlist_name="Mix 1", user_id="u"),
                SimpleNamespace(id=2, target_playlist_name="Mix 2", user_id="u"),
            ]
        ),
        user={"plex_user_id": "u"},
    )

    assert response.processed == 1
    assert response.task_ids == ["task-2"]
    assert response.skipped_ids == [1]
    assert "1 skipped" in logged[0]["summary"]
