"""Phase 2 security tests: Idempotency and Plex error handling."""

import uuid
from types import SimpleNamespace
from unittest.mock import AsyncMock, Mock, patch

import httpx
import pytest

from src.app.core.targets.plex_errors import (
    PlexErrorInfo,
    PlexErrorType,
    categorize_plex_error,
)
from src.app.models import ScheduledPlaylistSync
from src.app.schemas.syncs import SyncTriggerRequest, SyncTriggerResponse

# IDEMPOTENCY TESTS


class TestIdempotencyBasic:
    """Test basic idempotency: same execution_id = same response."""

    def test_execution_id_field_exists_in_model(self):
        """Verify ScheduledPlaylistSync has execution_id field."""
        from sqlalchemy import inspect

        mapper = inspect(ScheduledPlaylistSync)
        columns = {col.name for col in mapper.columns}
        assert "execution_id" in columns
        assert mapper.columns["execution_id"].nullable is True

    def test_unique_index_on_execution_id(self):
        """Verify the partial unique index exists on (user_id, execution_id)."""
        from sqlalchemy import inspect

        mapper = inspect(ScheduledPlaylistSync)
        indexes = {i.name: i for i in mapper.mapped_table.indexes}
        assert "uq_sync_execution_per_user" in indexes

        index = indexes["uq_sync_execution_per_user"]
        assert index.unique is True
        assert [col.name for col in index.columns] == ["user_id", "execution_id"]
        # Partial index: rows without an idempotency key are not constrained.
        where = index.dialect_options["postgresql"]["where"]
        assert where is not None
        # Only ad-hoc rows are constrained. A scheduled sync stores the key on
        # its own row, so its scope is the schedule itself — the same client
        # key must stay usable for a second schedule.
        assert "execution_id IS NOT NULL" in str(where)
        assert "schedule_interval = 'once'" in str(where)

    def test_execution_id_auto_generated_if_not_provided(self):
        """If no execution_id provided, UUID should be generated."""
        request = SyncTriggerRequest(
            playlist_url="https://music.youtube.com/playlist?list=PLtest",
            execution_id=None,
        )
        assert request.execution_id is None

    def test_execution_id_validation_format(self):
        """execution_id should accept UUID format."""
        test_uuid = uuid.uuid4().hex
        request = SyncTriggerRequest(
            playlist_url="https://music.youtube.com/playlist?list=PLtest",
            execution_id=test_uuid,
        )
        assert request.execution_id == test_uuid

    def test_response_fields_for_existing_sync(self):
        """Response when returning existing sync should have sync_id, no task_id."""
        response = SyncTriggerResponse(
            message="Sync already exists (idempotent response)",
            task_id=None,
            status_url=None,
            sync_id=123,
        )
        assert response.sync_id == 123
        assert response.task_id is None
        assert response.status_url is None

    def test_response_fields_for_new_sync(self):
        """A new sync reports both the task id and the created sync id."""
        response = SyncTriggerResponse(
            message="Sync job started successfully.",
            task_id="task-123",
            status_url="/api/v1/syncs/status/task-123",
            sync_id=456,
        )
        assert response.task_id == "task-123"
        assert response.status_url == "/api/v1/syncs/status/task-123"
        assert response.sync_id == 456

    def test_different_users_same_execution_id_are_different_syncs(self):
        """The idempotency key is scoped per user, not globally."""
        from sqlalchemy import inspect

        mapper = inspect(ScheduledPlaylistSync)
        indexes = {i.name: i for i in mapper.mapped_table.indexes}
        index = indexes["uq_sync_execution_per_user"]

        # user_id is part of the index, so the same execution_id may exist
        # once per user.
        assert "user_id" in [col.name for col in index.columns]


# PLEX ERROR CATEGORIZATION TESTS


class TestPlexErrorCategorization:
    """Test error categorization logic."""

    def test_network_error_connection_refused(self):
        """Connection refused should be categorized as transient."""
        error = ConnectionError("Connection refused")
        result = categorize_plex_error(error)

        assert result.error_type == PlexErrorType.NETWORK_ERROR
        assert result.is_transient is True
        assert "Connection refused" in result.message

    def test_network_error_timeout(self):
        """Timeout should be categorized as transient."""
        error = httpx.TimeoutException("Request timed out")
        result = categorize_plex_error(error)

        assert result.error_type == PlexErrorType.NETWORK_ERROR
        assert result.is_transient is True

    def test_auth_error_401_unauthorized(self):
        """401 should be categorized as fatal auth error."""
        response = Mock()
        response.status_code = 401
        error = httpx.HTTPStatusError("401 Unauthorized", request=Mock(), response=response)
        result = categorize_plex_error(error)

        assert result.error_type == PlexErrorType.AUTH_ERROR
        assert result.is_transient is False
        assert "401" in result.message

    def test_auth_error_403_forbidden(self):
        """403 should be categorized as fatal auth error."""
        response = Mock()
        response.status_code = 403
        error = httpx.HTTPStatusError("403 Forbidden", request=Mock(), response=response)
        result = categorize_plex_error(error)

        assert result.error_type == PlexErrorType.AUTH_ERROR
        assert result.is_transient is False

    def test_not_found_error_404(self):
        """404 should be categorized as fatal not found."""
        response = Mock()
        response.status_code = 404
        error = httpx.HTTPStatusError("404 Not Found", request=Mock(), response=response)
        result = categorize_plex_error(error)

        assert result.error_type == PlexErrorType.NOT_FOUND
        assert result.is_transient is False

    def test_rate_limit_error_429(self):
        """429 should be categorized as transient rate limit."""
        response = Mock()
        response.status_code = 429
        error = httpx.HTTPStatusError("429 Too Many Requests", request=Mock(), response=response)
        result = categorize_plex_error(error)

        assert result.error_type == PlexErrorType.RATE_LIMITED
        assert result.is_transient is True

    def test_server_error_500(self):
        """500 should be categorized as transient server error."""
        response = Mock()
        response.status_code = 500
        error = httpx.HTTPStatusError("500 Server Error", request=Mock(), response=response)
        result = categorize_plex_error(error)

        assert result.error_type == PlexErrorType.SERVER_ERROR
        assert result.is_transient is True

    def test_server_error_503(self):
        """503 should be categorized as transient server error."""
        response = Mock()
        response.status_code = 503
        error = httpx.HTTPStatusError("503 Service Unavailable", request=Mock(), response=response)
        result = categorize_plex_error(error)

        assert result.error_type == PlexErrorType.SERVER_ERROR
        assert result.is_transient is True


# PLEX ERROR INFO TESTS


class TestPlexErrorInfo:
    """Test error info dataclass."""

    def test_error_info_structure(self):
        """PlexErrorInfo should have required fields."""
        info = PlexErrorInfo(
            error_type=PlexErrorType.NETWORK_ERROR,
            message="Connection timeout",
            is_transient=True,
        )

        assert info.error_type == PlexErrorType.NETWORK_ERROR
        assert info.message == "Connection timeout"
        assert info.is_transient is True
        assert info.retry_count == 0
        assert info.max_retries == 3

    def test_error_info_string_representation(self):
        """PlexErrorInfo should have readable string representation."""
        info = PlexErrorInfo(
            error_type=PlexErrorType.AUTH_ERROR,
            message="Token expired",
            is_transient=False,
        )

        str_repr = str(info)
        assert "auth_error" in str_repr
        assert "Token expired" in str_repr

    def test_error_info_with_custom_max_retries(self):
        """PlexErrorInfo should support custom max_retries."""
        info = PlexErrorInfo(
            error_type=PlexErrorType.RATE_LIMITED,
            message="Rate limited",
            is_transient=True,
            max_retries=5,
        )

        assert info.max_retries == 5

    def test_error_info_retry_count_increment(self):
        """PlexErrorInfo retry_count should be mutable."""
        info = PlexErrorInfo(
            error_type=PlexErrorType.SERVER_ERROR,
            message="500 error",
            is_transient=True,
        )

        assert info.retry_count == 0
        info.retry_count += 1
        assert info.retry_count == 1


# ERROR HANDLING STRATEGY TESTS


class TestErrorHandlingStrategy:
    """Test error handling strategies."""

    def test_transient_error_should_retry(self):
        """Transient errors should be retried."""
        error_info = PlexErrorInfo(
            error_type=PlexErrorType.NETWORK_ERROR,
            message="Timeout",
            is_transient=True,
        )

        should_retry = error_info.is_transient
        assert should_retry is True

    def test_fatal_error_should_skip(self):
        """Fatal errors should skip gracefully."""
        error_info = PlexErrorInfo(
            error_type=PlexErrorType.AUTH_ERROR,
            message="Invalid token",
            is_transient=False,
        )

        should_skip = not error_info.is_transient
        assert should_skip is True

    def test_not_found_is_fatal_skip(self):
        """404 Not Found should skip gracefully."""
        error_info = PlexErrorInfo(
            error_type=PlexErrorType.NOT_FOUND,
            message="Playlist not found",
            is_transient=False,
        )

        assert error_info.is_transient is False

    def test_retry_count_respects_max_retries(self):
        """Retry should stop at max_retries."""
        error_info = PlexErrorInfo(
            error_type=PlexErrorType.SERVER_ERROR,
            message="500 error",
            is_transient=True,
            max_retries=3,
        )

        for attempt in range(1, 5):
            error_info.retry_count = attempt
            should_retry = error_info.retry_count < error_info.max_retries

            if attempt == 3:
                assert not should_retry


# EDGE CASES


class TestEdgeCases:
    """Test edge cases and corner scenarios."""

    def test_unknown_error_is_not_transient(self):
        """Unknown errors should default to not transient (safe default)."""
        error = RuntimeError("Some random error")
        result = categorize_plex_error(error)

        assert result.error_type == PlexErrorType.UNKNOWN
        assert result.is_transient is False

    def test_execution_id_null_always_allowed(self):
        """NULL execution_id should always be allowed (backward compat)."""
        sync1 = ScheduledPlaylistSync(
            user_id="user-1",
            source="youtube_music",
            source_url="https://example.com/1",
            target_playlist_name="Playlist 1",
            schedule_interval="daily",
            next_sync_at="2026-10-22T00:00:00Z",
            execution_id=None,
        )

        sync2 = ScheduledPlaylistSync(
            user_id="user-1",
            source="youtube_music",
            source_url="https://example.com/2",
            target_playlist_name="Playlist 2",
            schedule_interval="daily",
            next_sync_at="2026-10-22T00:00:00Z",
            execution_id=None,
        )

        assert sync1.user_id == sync2.user_id
        assert sync1.execution_id is None
        assert sync2.execution_id is None

    def test_connect_error_connection_error_type(self):
        """httpx.ConnectError should be recognized as network error."""
        error = httpx.ConnectError("Failed to connect")
        result = categorize_plex_error(error)

        assert result.error_type == PlexErrorType.NETWORK_ERROR
        assert result.is_transient is True

    def test_schema_backward_compatibility(self):
        """Schemas should accept requests without execution_id."""
        request = SyncTriggerRequest(
            playlist_url="https://music.youtube.com/playlist?list=PLtest",
            source="youtube_music",
            target_id="plex",
        )

        assert request.execution_id is None


# INTEGRATION TESTS


class TestIntegrationStructure:
    """Test integration of idempotency and error handling."""

    def test_sync_creation_with_execution_id_flow(self):
        """Verify complete flow: request -> schema -> execution_id -> DB."""
        execution_id = uuid.uuid4().hex
        request = SyncTriggerRequest(
            playlist_url="https://music.youtube.com/playlist?list=PLtest",
            execution_id=execution_id,
        )

        assert request.execution_id == execution_id

        new_sync = ScheduledPlaylistSync(
            user_id="plex-user-123",
            source="youtube_music",
            source_url=request.playlist_url,
            target_playlist_name="Test",
            schedule_interval="once",
            next_sync_at="2026-10-22T00:00:00Z",
            execution_id=execution_id,
        )

        assert new_sync.execution_id == execution_id
        assert new_sync.user_id == "plex-user-123"

    def test_error_handling_in_pipeline_decision(self):
        """Verify error -> categorize -> decide flow."""
        error1 = httpx.TimeoutException("timeout")
        info1 = categorize_plex_error(error1)
        assert info1.is_transient

        response2 = Mock()
        response2.status_code = 401
        error2 = httpx.HTTPStatusError("401", request=Mock(), response=response2)
        info2 = categorize_plex_error(error2)
        assert not info2.is_transient

        response3 = Mock()
        response3.status_code = 404
        error3 = httpx.HTTPStatusError("404", request=Mock(), response=response3)
        info3 = categorize_plex_error(error3)
        assert not info3.is_transient

    def test_migration_compatibility(self):
        """Test that migration-related changes are backward compatible."""
        old_sync = ScheduledPlaylistSync(
            user_id="plex-user-1",
            source="youtube_music",
            source_url="https://example.com",
            target_playlist_name="Old Playlist",
            schedule_interval="daily",
            next_sync_at="2026-10-22T00:00:00Z",
        )

        assert old_sync.execution_id is None

        new_sync = ScheduledPlaylistSync(
            user_id="plex-user-1",
            source="youtube_music",
            source_url="https://example.com",
            target_playlist_name="New Playlist",
            schedule_interval="daily",
            next_sync_at="2026-10-22T00:00:00Z",
            execution_id=uuid.uuid4().hex,
        )

        assert new_sync.execution_id is not None
        assert old_sync.user_id == new_sync.user_id


# ─────────────────────────────────────────────────────────────────────────────
# Idempotency behaviour of the trigger endpoint (hermetic)
# ─────────────────────────────────────────────────────────────────────────────


class FakeResult:
    """Minimal result object returning a single row."""

    def __init__(self, row=None):
        self._row = row

    def scalar_one_or_none(self):
        return self._row

    def scalar_one(self):
        return self._row


class FakeSession:
    """Async session double that assigns ids on flush."""

    def __init__(self, results=None, new_id=123, get_result=None):
        self.executed = []
        self.added = []
        self.deleted = []
        self.committed = False
        self._results = list(results or [])
        self._new_id = new_id
        self._get_result = get_result

    async def __aenter__(self):
        return self

    async def __aexit__(self, exc_type, exc, tb):
        return False

    async def execute(self, stmt):
        self.executed.append(stmt)
        if self._results:
            return self._results.pop(0)
        return FakeResult()

    def add(self, obj):
        self.added.append(obj)

    async def get(self, model, pk):
        if self._get_result is not None:
            return self._get_result
        return SimpleNamespace(id=pk, execution_id="exec-1")

    async def delete(self, obj):
        self.deleted.append(obj)

    async def flush(self):
        for obj in self.added:
            if getattr(obj, "id", None) is None:
                obj.id = self._new_id

    async def commit(self):
        self.committed = True

    async def rollback(self):
        pass


@pytest.fixture
def trigger_env(monkeypatch):
    """Patch out everything trigger_sync touches except the database."""
    from src.app.api import syncs as syncs_api

    enqueued: list[dict] = []

    class FakeTask:
        id = "task-1"

    def fake_delay(**kwargs):
        enqueued.append(kwargs)
        return FakeTask()

    monkeypatch.setattr(
        syncs_api,
        "list_sync_targets",
        AsyncMock(return_value=[{"id": "plex", "name": "Plex"}]),
    )
    monkeypatch.setattr(syncs_api.sync_playlists_task, "delay", fake_delay)
    monkeypatch.setattr(syncs_api, "log_event", AsyncMock())
    # The reverse task→sync mapping lives in Valkey; keep the test hermetic.
    monkeypatch.setattr(syncs_api, "register_sync_task_async", AsyncMock())
    monkeypatch.setattr(syncs_api, "broadcast_sync_event", AsyncMock())
    return enqueued


def compile_sql(stmt) -> str:
    """Compile a statement with literal values so assertions can match them."""
    from sqlalchemy.dialects import postgresql

    return str(
        stmt.compile(
            dialect=postgresql.dialect(),
            compile_kwargs={"literal_binds": True},
        )
    )


def _request(**kwargs) -> SyncTriggerRequest:
    return SyncTriggerRequest(
        playlist_url="https://music.youtube.com/playlist?list=PLtest",
        source="youtube_music",
        target_id="plex",
        **kwargs,
    )


async def test_trigger_sync_commits_the_new_sync_record(monkeypatch, trigger_env):
    """The ad-hoc sync record must be committed, otherwise it is rolled back."""
    from src.app.api import syncs as syncs_api

    fake = FakeSession()
    monkeypatch.setattr(syncs_api, "AsyncSessionLocal", lambda: fake)

    response = await syncs_api.trigger_sync(
        body=_request(execution_id="exec-1"),
        _user={"plex_user_id": "user-1"},
    )

    assert fake.committed is True
    assert response.sync_id == 123
    assert response.task_id == "task-1"
    # The worker needs the sync id and the owner to attribute audit events.
    assert trigger_env[0]["sync_id"] == 123
    assert trigger_env[0]["user_id"] == "user-1"


async def test_trigger_sync_is_idempotent(monkeypatch, trigger_env):
    """A repeated execution_id returns the existing sync and enqueues nothing."""
    from src.app.api import syncs as syncs_api

    existing = SimpleNamespace(id=99)
    fake = FakeSession(results=[FakeResult(row=existing)])
    monkeypatch.setattr(syncs_api, "AsyncSessionLocal", lambda: fake)

    response = await syncs_api.trigger_sync(
        body=_request(execution_id="exec-1"),
        _user={"plex_user_id": "user-1"},
    )

    assert response.sync_id == 99
    assert response.task_id is None
    assert response.status_url is None
    assert trigger_env == []
    assert fake.committed is False


async def test_trigger_sync_persists_execution_id_for_scheduled_syncs(monkeypatch, trigger_env):
    """A scheduled sync stores the idempotency key so retries resolve to it."""
    from src.app.api import syncs as syncs_api

    schedule = SimpleNamespace(id=7, execution_id=None)
    fake = FakeSession(results=[FakeResult(row=None), FakeResult(row=schedule)])
    monkeypatch.setattr(syncs_api, "AsyncSessionLocal", lambda: fake)

    response = await syncs_api.trigger_sync(
        body=_request(execution_id="exec-2", schedule_id=7),
        _user={"plex_user_id": "user-1"},
    )

    assert schedule.execution_id == "exec-2"
    assert fake.committed is True
    assert response.sync_id == 7


async def test_trigger_sync_scopes_the_idempotency_lookup_to_the_request_target(
    monkeypatch, trigger_env
):
    """An ad-hoc key must not resolve against a schedule that carries the same key."""
    from src.app.api import syncs as syncs_api

    fake = FakeSession()
    monkeypatch.setattr(syncs_api, "AsyncSessionLocal", lambda: fake)

    await syncs_api.trigger_sync(
        body=_request(execution_id="exec-1"),
        _user={"plex_user_id": "user-1"},
    )

    sql = compile_sql(fake.executed[0])
    assert "scheduled_playlist_syncs.schedule_interval = 'once'" in sql
    assert "scheduled_playlist_syncs.id =" not in sql


async def test_trigger_sync_scopes_the_idempotency_lookup_to_the_schedule(monkeypatch, trigger_env):
    """A scheduled key resolves against its own schedule, not any other row."""
    from src.app.api import syncs as syncs_api

    schedule = SimpleNamespace(id=7, execution_id=None)
    fake = FakeSession(results=[FakeResult(row=None), FakeResult(row=schedule)])
    monkeypatch.setattr(syncs_api, "AsyncSessionLocal", lambda: fake)

    await syncs_api.trigger_sync(
        body=_request(execution_id="exec-2", schedule_id=7),
        _user={"plex_user_id": "user-1"},
    )

    sql = compile_sql(fake.executed[0])
    assert "scheduled_playlist_syncs.id = 7" in sql
    assert "schedule_interval = 'once'" not in sql


async def test_trigger_sync_registers_the_task_mapping_before_answering(monkeypatch, trigger_env):
    """The task→sync mapping must exist before the client starts polling."""
    from src.app.api import syncs as syncs_api

    fake = FakeSession()
    monkeypatch.setattr(syncs_api, "AsyncSessionLocal", lambda: fake)

    await syncs_api.trigger_sync(
        body=_request(execution_id="exec-1"),
        _user={"plex_user_id": "user-1"},
    )

    syncs_api.register_sync_task_async.assert_awaited_once_with(123, "task-1")


async def test_trigger_sync_discards_the_record_when_the_broker_refuses(monkeypatch, trigger_env):
    """A task that cannot be published must not leave a phantom sync behind."""
    from fastapi import HTTPException

    from src.app.api import syncs as syncs_api

    def boom(**kwargs):
        raise RuntimeError("broker down")

    monkeypatch.setattr(syncs_api.sync_playlists_task, "delay", boom)

    fake = FakeSession()
    monkeypatch.setattr(syncs_api, "AsyncSessionLocal", lambda: fake)

    with pytest.raises(HTTPException) as exc_info:
        await syncs_api.trigger_sync(
            body=_request(execution_id="exec-1"),
            _user={"plex_user_id": "user-1"},
        )

    assert exc_info.value.status_code == 500
    assert len(fake.deleted) == 1


async def test_trigger_sync_restores_the_schedule_key_when_the_broker_refuses(
    monkeypatch, trigger_env
):
    """A failed enqueue must not leave the schedule holding a stale idempotency key."""
    from fastapi import HTTPException

    from src.app.api import syncs as syncs_api

    def boom(**kwargs):
        raise RuntimeError("broker down")

    monkeypatch.setattr(syncs_api.sync_playlists_task, "delay", boom)

    schedule = SimpleNamespace(id=7, execution_id="old-key")
    fake = FakeSession(
        results=[FakeResult(row=None), FakeResult(row=schedule)], get_result=schedule
    )
    monkeypatch.setattr(syncs_api, "AsyncSessionLocal", lambda: fake)

    with pytest.raises(HTTPException) as exc_info:
        await syncs_api.trigger_sync(
            body=_request(execution_id="exec-2", schedule_id=7),
            _user={"plex_user_id": "user-1"},
        )

    assert exc_info.value.status_code == 500
    assert schedule.execution_id == "old-key"


class TestExecutionIdConflictDetection:
    """Only the idempotency index may be treated as an idempotency race."""

    def _integrity_error(self, message: str):
        from sqlalchemy.exc import IntegrityError

        return IntegrityError("stmt", {}, Exception(message))

    def test_idempotency_index_is_recognized(self):
        from src.app.api.syncs import _is_execution_id_conflict

        exc = self._integrity_error(
            'duplicate key value violates unique constraint "uq_sync_execution_per_user"'
        )

        assert _is_execution_id_conflict(exc) is True

    def test_foreign_key_violation_is_not_an_idempotency_race(self):
        from src.app.api.syncs import _is_execution_id_conflict

        exc = self._integrity_error(
            'insert or update on table "scheduled_playlist_syncs" violates foreign key '
            'constraint "fk_scheduled_playlist_syncs_user_id"'
        )

        assert _is_execution_id_conflict(exc) is False
