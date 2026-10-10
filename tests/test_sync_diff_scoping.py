"""Regression for A-04: sync diff must scope run lookups to the requested sync."""

import pytest
from fastapi import HTTPException
from sqlalchemy.dialects import postgresql

from src.app.api import syncs as syncs_api


class FakeSyncResult:
    def scalar_one_or_none(self):
        class FakeSync:
            id = 1
            user_id = "u"

        return FakeSync()


class FakeRunsResult:
    def scalars(self):
        class _Scalars:
            def all(self):
                return []

        return _Scalars()


class FakeSession:
    def __init__(self):
        self.executed = []

    async def __aenter__(self):
        return self

    async def __aexit__(self, exc_type, exc, tb):
        return False

    async def execute(self, stmt):
        self.executed.append(stmt)
        # First call is the sync existence check, second the runs lookup.
        return FakeSyncResult() if len(self.executed) == 1 else FakeRunsResult()


async def test_diff_requires_runs_of_the_same_sync(monkeypatch):
    """Cross-sync run IDs must not be resolvable via the diff endpoint."""
    fake = FakeSession()
    monkeypatch.setattr(syncs_api, "AsyncSessionLocal", lambda: fake)

    with pytest.raises(HTTPException) as exc_info:
        await syncs_api.get_sync_diff(
            sync_id=5, from_run=100, to_run=101, user={"plex_user_id": "u"}
        )

    assert exc_info.value.status_code == 404
    assert "not found for this sync" in str(exc_info.value.detail)

    runs_stmt = fake.executed[1]
    sql = str(runs_stmt.compile(dialect=postgresql.dialect()))
    assert "WHERE sync_runs.sync_id" in sql
    assert "sync_runs.id IN" in sql
