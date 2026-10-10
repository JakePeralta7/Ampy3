"""Dispatch lock ownership and release semantics (review fix 2 follow-up)."""

from types import SimpleNamespace

from src.app.services import scheduler as scheduler_service
from src.app.services.scheduler import (
    _CHILD_FINISHED_SCRIPT,
    _RELEASE_LOCK_SCRIPT,
)
from src.app.worker import tasks as worker_tasks


class FakeValkey:
    """In-memory stand-in for the Valkey client, including the two lock Lua scripts."""

    def __init__(self, store=None, fail=False):
        self.store = store or {}
        self.fail = fail

    def set(self, name, value, nx=False, ex=None):
        if self.fail:
            raise RuntimeError("valkey down")
        if nx and name in self.store:
            return False
        self.store[name] = value
        return True

    def get(self, name):
        if self.fail:
            raise RuntimeError("valkey down")
        return self.store.get(name)

    def delete(self, name):
        if self.fail:
            raise RuntimeError("valkey down")
        self.store.pop(name, None)
        return True

    def eval(self, script, numkeys, *args):
        if self.fail:
            raise RuntimeError("valkey down")
        keys = list(args[:numkeys])
        argv = list(args[numkeys:])
        if script == _CHILD_FINISHED_SCRIPT:
            return self._child_finished(keys[0], keys[1], argv[0], int(argv[1]))
        if script == _RELEASE_LOCK_SCRIPT:
            return self._release(keys[0], keys[1], argv[0])
        raise AssertionError(f"Unexpected Lua script: {script[:40]}...")

    def _release(self, lock_key, counter_key, token):
        current = self.store.get(lock_key)
        if current is None or current != token:
            return 0
        self.store.pop(lock_key, None)
        self.store.pop(counter_key, None)
        return 1

    def _child_finished(self, lock_key, counter_key, token, ttl):
        val = self.store.get(counter_key)
        if val is None:
            return 0
        stored_token, _, raw_n = val.partition(":")
        if stored_token != token or not raw_n.isdigit():
            return 0
        n = int(raw_n) - 1
        if n <= 0:
            self.store.pop(counter_key, None)
            self.store.pop(lock_key, None)
            return 1
        self.store[counter_key] = f"{stored_token}:{n}"
        return 0


class FakeValkeyService:
    client = None

    @classmethod
    def get_sync_instance(cls):
        return cls.client


def _patch_valkey(monkeypatch, valkey):
    monkeypatch.setattr(scheduler_service, "ValkeyService", FakeValkeyService)
    FakeValkeyService.client = valkey


def test_acquire_returns_owner_token_and_initializes_counter(monkeypatch):
    valkey = FakeValkey()
    _patch_valkey(monkeypatch, valkey)

    token = scheduler_service._try_acquire_dispatch_lock(7, child_count=2)
    assert token
    assert valkey.store["ampy3:dispatch_lock:7"] == token
    assert valkey.store["ampy3:dispatch_counter:7"] == f"{token}:2"


def test_acquire_returns_none_when_locked(monkeypatch):
    valkey = FakeValkey({"ampy3:dispatch_lock:7": "other-owner"})
    _patch_valkey(monkeypatch, valkey)

    assert scheduler_service._try_acquire_dispatch_lock(7, child_count=2) is None
    assert "ampy3:dispatch_counter:7" not in valkey.store


def test_acquire_returns_unstored_token_on_valkey_outage(monkeypatch):
    """On Valkey outage, return an unstored token so sync proceeds (fail-open).
    
    The token won't be stored in Valkey, so release functions treat it as a no-op.
    This ensures scheduled syncs are never blocked by infrastructure outages.
    """
    valkey = FakeValkey(fail=True)
    _patch_valkey(monkeypatch, valkey)

    # Should return a token, not None (fail-open behavior)
    token = scheduler_service._try_acquire_dispatch_lock(7, child_count=2)
    assert token  # Token is returned (non-None)
    assert isinstance(token, str)
    # But it's not stored in Valkey since the service was down
    assert "ampy3:dispatch_lock:7" not in valkey.store
    assert "ampy3:dispatch_counter:7" not in valkey.store


def test_release_only_deletes_matching_owner_token(monkeypatch):
    valkey = FakeValkey(
        {
            "ampy3:dispatch_lock:8": "expected-token",
            "ampy3:dispatch_counter:8": "expected-token:1",
        }
    )
    _patch_valkey(monkeypatch, valkey)

    scheduler_service._release_dispatch_lock(8, "other-token")
    assert valkey.store["ampy3:dispatch_lock:8"] == "expected-token"

    scheduler_service._release_dispatch_lock(8, "expected-token")
    assert "ampy3:dispatch_lock:8" not in valkey.store
    assert "ampy3:dispatch_counter:8" not in valkey.store


def test_release_noops_without_token_or_missing_key(monkeypatch):
    _patch_valkey(monkeypatch, FakeValkey())

    scheduler_service._release_dispatch_lock(9, None)
    scheduler_service._release_dispatch_lock(9, "token")  # key absent -> no-op


def test_release_swallows_valkey_errors(monkeypatch):
    valkey = FakeValkey({"ampy3:dispatch_lock:10": "t"}, fail=True)
    _patch_valkey(monkeypatch, valkey)

    scheduler_service._release_dispatch_lock(10, "t")  # must not raise


def test_child_finish_decrements_and_last_child_releases(monkeypatch):
    valkey = FakeValkey()
    _patch_valkey(monkeypatch, valkey)

    token = scheduler_service._try_acquire_dispatch_lock(11, child_count=2)

    scheduler_service._child_finished_dispatch_lock(11, token)
    assert valkey.store["ampy3:dispatch_counter:11"] == f"{token}:1"
    assert "ampy3:dispatch_lock:11" in valkey.store

    scheduler_service._child_finished_dispatch_lock(11, token)
    assert "ampy3:dispatch_counter:11" not in valkey.store
    assert "ampy3:dispatch_lock:11" not in valkey.store


def test_child_finish_ignores_stale_token(monkeypatch):
    valkey = FakeValkey()
    _patch_valkey(monkeypatch, valkey)

    token = scheduler_service._try_acquire_dispatch_lock(12, child_count=1)
    scheduler_service._child_finished_dispatch_lock(12, "some-other-token")
    assert valkey.store["ampy3:dispatch_counter:12"] == f"{token}:1"
    assert "ampy3:dispatch_lock:12" in valkey.store


def test_child_finish_swallows_valkey_errors(monkeypatch):
    valkey = FakeValkey({"ampy3:dispatch_counter:13": "t:1"}, fail=True)
    _patch_valkey(monkeypatch, valkey)

    scheduler_service._child_finished_dispatch_lock(13, "t")  # must not raise


async def test_trigger_sync_now_passes_owner_token_to_dispatch(monkeypatch):
    calls = []

    class FakeTask:
        @staticmethod
        def delay(**kwargs):
            calls.append(kwargs)
            return None

    monkeypatch.setattr(scheduler_service, "sync_playlists_task", FakeTask)
    valkey = FakeValkey()
    _patch_valkey(monkeypatch, valkey)

    sync = SimpleNamespace(
        id=7,
        source_url="https://music.youtube.com/playlist?list=PLabc",
        source="youtube_music",
        target_ids=["Plex"],
        target_playlist_name="Mix",
    )
    result = await scheduler_service.SchedulerService.trigger_sync_now(sync)
    assert result is None  # FakeTask.delay returns None
    assert calls and calls[0]["schedule_id"] == 7
    assert calls[0]["dispatch_token"]
    assert valkey.store["ampy3:dispatch_counter:7"] == f"{calls[0]['dispatch_token']}:1"


def test_postrun_parent_releases_when_never_spawned(monkeypatch):
    released = []

    def fake_release(schedule_id, token):
        released.append((schedule_id, token))

    def fake_child_release(schedule_id, token):
        raise AssertionError("child release must not fire for the parent")

    monkeypatch.setattr(scheduler_service, "_release_dispatch_lock", fake_release)
    monkeypatch.setattr(scheduler_service, "_child_finished_dispatch_lock", fake_child_release)

    sender = SimpleNamespace(spawned_targets=False)
    kwargs = {"schedule_id": 7, "dispatch_token": "token-1", "target_ids": ["Plex"]}

    worker_tasks._release_dispatch_lock_on_postrun(sender=sender, kwargs=kwargs, state="SUCCESS")
    assert released == [(7, "token-1")]

    # A retry keeps the lock held until the final attempt completes.
    worker_tasks._release_dispatch_lock_on_postrun(sender=sender, kwargs=kwargs, state="RETRY")
    assert released == [(7, "token-1")]


def test_postrun_parent_keeps_lock_when_children_spawned(monkeypatch):
    def fake_release(schedule_id, token):
        raise AssertionError("parent released despite spawning children")

    def fake_child_release(schedule_id, token):
        raise AssertionError("child release must not fire for the parent")

    monkeypatch.setattr(scheduler_service, "_release_dispatch_lock", fake_release)
    monkeypatch.setattr(scheduler_service, "_child_finished_dispatch_lock", fake_child_release)

    sender = SimpleNamespace(spawned_targets=True)
    kwargs = {"schedule_id": 7, "dispatch_token": "token-1", "target_ids": ["Plex"]}

    worker_tasks._release_dispatch_lock_on_postrun(sender=sender, kwargs=kwargs, state="SUCCESS")


def test_postrun_child_releases_via_counter(monkeypatch):
    def fake_release(schedule_id, token):
        raise AssertionError("parent release must not fire for a child")

    calls = []

    def fake_child_release(schedule_id, token):
        calls.append((schedule_id, token))

    monkeypatch.setattr(scheduler_service, "_release_dispatch_lock", fake_release)
    monkeypatch.setattr(scheduler_service, "_child_finished_dispatch_lock", fake_child_release)

    kwargs = {"schedule_id": 7, "dispatch_token": "token-1", "target_id": "Plex"}

    worker_tasks._release_dispatch_lock_on_postrun(sender=None, kwargs=kwargs, state="SUCCESS")
    assert calls == [(7, "token-1")]

    # A retrying child keeps the lock held.
    worker_tasks._release_dispatch_lock_on_postrun(sender=None, kwargs=kwargs, state="RETRY")
    assert calls == [(7, "token-1")]


def test_postrun_noops_without_token(monkeypatch):
    def fake_release(schedule_id, token):
        raise AssertionError("must not release")

    def fake_child_release(schedule_id, token):
        raise AssertionError("must not release")

    monkeypatch.setattr(scheduler_service, "_release_dispatch_lock", fake_release)
    monkeypatch.setattr(scheduler_service, "_child_finished_dispatch_lock", fake_child_release)

    worker_tasks._release_dispatch_lock_on_postrun(sender=None, kwargs={}, state="FAILURE")
    worker_tasks._release_dispatch_lock_on_postrun(
        sender=None, kwargs={"schedule_id": 7}, state="SUCCESS"
    )
