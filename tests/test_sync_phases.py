"""Unit tests for the Valkey-backed FetchPhase status helpers."""

import json

from src.app.services import sync_tasks
from src.app.services.sync_tasks import get_fetch_phase, get_fetch_phase_async, set_fetch_phase


class FakeClient:
    """Minimal in-memory stand-in for the sync Valkey client."""

    def __init__(self) -> None:
        self._data: dict[str, str] = {}
        self.expires: dict[str, int] = {}

    def set(self, key: str, value: str, ex: int | None = None) -> None:
        self._data[key] = value
        if ex is not None:
            self.expires[key] = ex

    def get(self, key: str) -> str | None:
        return self._data.get(key)


class FakeAsyncClient:
    """Minimal in-memory stand-in for the async Valkey client."""

    def __init__(self) -> None:
        self._data: dict[str, str] = {}

    async def get(self, key: str) -> str | None:
        return self._data.get(key)

    async def set(self, key: str, value: str, ex: int | None = None) -> None:
        self._data[key] = value


def _patch_sync_client(monkeypatch, client: FakeClient) -> None:
    monkeypatch.setattr(sync_tasks.ValkeyService, "get_sync_instance", lambda: client)


def _patch_async_client(monkeypatch, client: FakeAsyncClient) -> None:
    monkeypatch.setattr(sync_tasks.ValkeyService, "get_instance", lambda: client)


def test_set_and_get_fetch_phase(monkeypatch):
    client = FakeClient()
    _patch_sync_client(monkeypatch, client)

    set_fetch_phase(42, "running", started_at="2026-01-01T00:00:00+00:00")

    assert get_fetch_phase(42) == {
        "status": "running",
        "started_at": "2026-01-01T00:00:00+00:00",
        "completed_at": None,
        "execution_id": None,
    }
    assert client.expires[list(client.expires)[0]] == 24 * 3600


def test_fetch_phase_round_trips_execution_id(monkeypatch):
    client = FakeClient()
    _patch_sync_client(monkeypatch, client)

    set_fetch_phase(
        42,
        "running",
        started_at="2026-01-01T00:00:00+00:00",
        execution_id="abc123",
    )
    set_fetch_phase(42, "completed", completed_at="2026-01-01T00:00:05+00:00")

    phase = get_fetch_phase(42)
    assert phase is not None
    assert phase["status"] == "completed"
    assert phase["execution_id"] == "abc123"


def test_new_running_phase_replaces_execution_id(monkeypatch):
    client = FakeClient()
    _patch_sync_client(monkeypatch, client)

    set_fetch_phase(42, "running", started_at="2026-01-01T00:00:00+00:00", execution_id="abc123")
    set_fetch_phase(42, "running", started_at="2026-01-02T00:00:00+00:00", execution_id="xyz789")

    phase = get_fetch_phase(42)
    assert phase is not None
    assert phase["execution_id"] == "xyz789"


def test_completed_keeps_started_at_and_sets_completed_at(monkeypatch):
    client = FakeClient()
    _patch_sync_client(monkeypatch, client)

    set_fetch_phase(42, "running", started_at="2026-01-01T00:00:00+00:00")
    set_fetch_phase(42, "completed", completed_at="2026-01-01T00:00:05+00:00")

    phase = get_fetch_phase(42)
    assert phase is not None
    assert phase["status"] == "completed"
    assert phase["started_at"] == "2026-01-01T00:00:00+00:00"
    assert phase["completed_at"] == "2026-01-01T00:00:05+00:00"


def test_new_running_phase_clears_previous_completed_at(monkeypatch):
    client = FakeClient()
    _patch_sync_client(monkeypatch, client)

    set_fetch_phase(42, "running", started_at="2026-01-01T00:00:00+00:00")
    set_fetch_phase(42, "completed", completed_at="2026-01-01T00:00:05+00:00")
    set_fetch_phase(42, "running", started_at="2026-01-02T00:00:00+00:00")

    phase = get_fetch_phase(42)
    assert phase is not None
    assert phase["status"] == "running"
    assert phase["started_at"] == "2026-01-02T00:00:00+00:00"
    assert phase["completed_at"] is None


def test_missing_phase_returns_none(monkeypatch):
    _patch_sync_client(monkeypatch, FakeClient())
    assert get_fetch_phase(999) is None


async def test_async_get_fetch_phase(monkeypatch):
    client = FakeAsyncClient()
    _patch_async_client(monkeypatch, client)
    client._data[f"{sync_tasks.PHASE_KEY_PREFIX}42:fetch"] = json.dumps(
        {"status": "completed", "started_at": "2026-01-01T00:00:00+00:00", "completed_at": None}
    )

    phase = await get_fetch_phase_async(42)

    assert phase == {
        "status": "completed",
        "started_at": "2026-01-01T00:00:00+00:00",
        "completed_at": None,
    }


def test_none_sync_id_is_noop(monkeypatch):
    client = FakeClient()
    _patch_sync_client(monkeypatch, client)

    set_fetch_phase(None, "running")
    assert client._data == {}
    assert get_fetch_phase(None) is None
