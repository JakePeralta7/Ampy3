import asyncio

import pytest

from src.app.services import sync_tasks


class FakeValkey:
    def __init__(self):
        self.sets = {}
        self.expires = {}
        self.deleted = []
        self.strings = {}

    def sadd(self, key, value):
        self.sets.setdefault(key, set()).add(value)
        return 1

    def srem(self, key, value):
        self.sets.get(key, set()).discard(value)
        return 1

    def expire(self, key, ttl):
        self.expires[key] = ttl
        return 1

    def smembers(self, key):
        return set(self.sets.get(key, set()))

    def set(self, key, value, ex=None):
        self.strings[key] = value
        if ex is not None:
            self.expires[key] = ex
        return True

    def get(self, key):
        return self.strings.get(key)

    def delete(self, key):
        self.deleted.append(key)
        self.sets.pop(key, None)
        self.strings.pop(key, None)
        return 1


@pytest.fixture
def fake_valkey(monkeypatch):
    client = FakeValkey()
    monkeypatch.setattr(sync_tasks, "_client", lambda: client)
    return client


def test_register_and_unregister_task(fake_valkey):
    sync_tasks.register_sync_task(42, "task-a")
    sync_tasks.register_sync_task(42, "task-b")

    assert fake_valkey.sets["ampy3:sync-tasks:42"] == {"task-a", "task-b"}
    assert fake_valkey.expires["ampy3:sync-tasks:42"] == sync_tasks.KEY_TTL_SECONDS

    sync_tasks.unregister_sync_task(42, "task-a")
    assert fake_valkey.sets["ampy3:sync-tasks:42"] == {"task-b"}


def test_register_task_is_noop_without_sync_or_task_id(fake_valkey):
    sync_tasks.register_sync_task(None, "task-a")
    sync_tasks.register_sync_task(42, "")
    assert fake_valkey.sets == {}


def test_register_task_stores_the_reverse_mapping(fake_valkey):
    sync_tasks.register_sync_task(42, "task-a")

    assert fake_valkey.strings["ampy3:task-to-sync:task-a"] == "42"
    assert sync_tasks.get_sync_id_for_task("task-a") == 42


def test_unregister_keeps_the_reverse_mapping(fake_valkey):
    """The API resolves task_id → sync_id to authorize status polling.

    That must keep working once the task finished, so the reverse key is
    only expired, never deleted.
    """
    sync_tasks.register_sync_task(42, "task-a")
    sync_tasks.unregister_sync_task(42, "task-a")

    assert "ampy3:task-to-sync:task-a" not in fake_valkey.deleted
    assert fake_valkey.strings["ampy3:task-to-sync:task-a"] == "42"
    assert sync_tasks.get_sync_id_for_task("task-a") == 42


async def test_async_reverse_lookup_uses_the_async_client(monkeypatch, fake_valkey):
    """The API must not use the blocking Valkey client."""
    fake_valkey.strings["ampy3:task-to-sync:task-a"] = "42"

    class FakeAsyncValkey:
        async def get(self, key):
            return fake_valkey.strings.get(key)

    class FakeService:
        @classmethod
        def get_instance(cls):
            return FakeAsyncValkey()

    monkeypatch.setattr(sync_tasks, "ValkeyService", FakeService)

    assert await sync_tasks.get_sync_id_for_task_async("task-a") == 42
    assert await sync_tasks.get_sync_id_for_task_async("unknown") is None


def test_revoke_terminates_tracked_tasks(fake_valkey, monkeypatch):
    import src.app.worker.app as worker_app

    fake_valkey.sets["ampy3:sync-tasks:7"] = {"t1", "t2"}
    revoked = []

    class FakeControl:
        def revoke(self, task_ids, terminate=False):
            revoked.append((list(task_ids), terminate))

    monkeypatch.setattr(worker_app.celery_app, "control", FakeControl())

    sync_tasks._revoke_sync(7)

    assert set(revoked[0][0]) == {"t1", "t2"}
    assert revoked[0][1] is True
    assert "ampy3:sync-tasks:7" in fake_valkey.deleted


def test_revoke_schedule_tasks_best_effort(fake_valkey, monkeypatch):
    calls = []

    def fake_revoke(sync_id):
        calls.append(sync_id)
        if sync_id == 1:
            raise RuntimeError("broker hiccup")

    monkeypatch.setattr(sync_tasks, "_revoke_sync", fake_revoke)

    asyncio.run(sync_tasks.revoke_schedule_tasks(1))
    asyncio.run(sync_tasks.revoke_schedule_tasks(2))
    asyncio.run(sync_tasks.revoke_schedule_tasks(None))

    assert calls == [1, 2]
