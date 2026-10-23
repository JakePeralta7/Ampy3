"""Phase 1 security tests — WebSocket auth, user scoping, SECRET_KEY hardening, PIN rate limit.

The tests are hermetic: no database, no Valkey and no network. The API
handlers are called directly with fakes, the same way
``tests/test_sync_diff_scoping.py`` does it.
"""

import json
from types import SimpleNamespace
from unittest.mock import AsyncMock

import pytest
from fastapi import HTTPException
from sqlalchemy.dialects import postgresql
from starlette.requests import Request

from src.app.api import audit as audit_api
from src.app.api import syncs as syncs_api
from src.app.api import websocket as ws_api
from src.app.auth import router as auth_router
from src.app.services.websocket_manager import WebSocketConnectionManager

# ─────────────────────────────────────────────────────────────────────────────
# Fakes
# ─────────────────────────────────────────────────────────────────────────────


class FakeResult:
    """Minimal stand-in for a SQLAlchemy result object."""

    def __init__(self, *, row=None, rows=(), scalar=None):
        self._row = row
        self._rows = list(rows)
        self._scalar = scalar

    def scalar_one_or_none(self):
        return self._row

    def scalar_one(self):
        return self._scalar if self._scalar is not None else self._row

    def scalars(self):
        rows = self._rows

        class _Scalars:
            def all(self):
                return list(rows)

            def first(self):
                return rows[0] if rows else None

        return _Scalars()

    def all(self):
        return list(self._rows)


class FakeSession:
    """Async session double that records statements and replays results."""

    def __init__(self, results=None):
        self.executed: list = []
        self.committed = False
        self._results = list(results or [])

    async def __aenter__(self):
        return self

    async def __aexit__(self, exc_type, exc, tb):
        return False

    async def execute(self, stmt):
        self.executed.append(stmt)
        if self._results:
            return self._results.pop(0)
        return FakeResult()

    async def commit(self):
        self.committed = True

    async def rollback(self):
        pass


class FakeWebSocket:
    """WebSocket double recording accept/close calls."""

    def __init__(self, cookies=None):
        self.cookies = cookies or {}
        self.accepted = False
        self.closed_code: int | None = None
        self.closed_reason: str | None = None
        self.sent: list[str] = []

    async def accept(self):
        self.accepted = True

    async def close(self, code=1000, reason=""):
        self.closed_code = code
        self.closed_reason = reason

    async def receive_text(self):
        # Break the keep-alive loop of the endpoint handlers.
        raise RuntimeError("client went away")

    async def send_text(self, text):
        self.sent.append(text)


def make_request(ip: str = "1.2.3.4") -> Request:
    """Build a minimal Starlette request with a client IP."""
    scope = {
        "type": "http",
        "method": "GET",
        "path": "/api/auth/plex/login",
        "headers": [(b"host", b"testserver")],
        "client": (ip, 1234),
        "query_string": b"",
        "scheme": "http",
        "server": ("testserver", 80),
    }
    return Request(scope)


def compile_sql(stmt) -> str:
    """Compile a statement with literal values so assertions can match them."""
    return str(
        stmt.compile(
            dialect=postgresql.dialect(),
            compile_kwargs={"literal_binds": True},
        )
    )


# ─────────────────────────────────────────────────────────────────────────────
# WebSocket authentication
# ─────────────────────────────────────────────────────────────────────────────


async def test_ws_authenticate_allows_local_user_when_auth_disabled(monkeypatch):
    """With REQUIRE_AUTH=false the WebSocket endpoints accept the local stub user."""
    monkeypatch.setattr(ws_api.settings, "require_auth", False)

    user = await ws_api._authenticate(FakeWebSocket())

    assert user is not None
    assert user["plex_user_id"] == "local"


async def test_ws_authenticate_rejects_missing_session(monkeypatch):
    """With REQUIRE_AUTH=true a missing/invalid session is rejected."""
    monkeypatch.setattr(ws_api.settings, "secret_key", "a" * 32)
    monkeypatch.setattr(ws_api.settings, "require_auth", True)
    monkeypatch.setattr(ws_api, "verify_session", AsyncMock(return_value=None))

    assert await ws_api._authenticate(FakeWebSocket()) is None


async def test_ws_authenticate_rejects_broken_session(monkeypatch):
    """A raising session verifier must not authenticate the connection."""
    monkeypatch.setattr(ws_api.settings, "secret_key", "a" * 32)
    monkeypatch.setattr(ws_api.settings, "require_auth", True)
    monkeypatch.setattr(ws_api, "verify_session", AsyncMock(side_effect=ValueError("bad cookie")))

    assert await ws_api._authenticate(FakeWebSocket()) is None


async def test_ws_authenticate_returns_session_user(monkeypatch):
    """A valid session yields the session user."""
    monkeypatch.setattr(ws_api.settings, "secret_key", "a" * 32)
    monkeypatch.setattr(ws_api.settings, "require_auth", True)
    monkeypatch.setattr(
        ws_api,
        "verify_session",
        AsyncMock(return_value={"plex_user_id": "user-1", "username": "alice"}),
    )

    user = await ws_api._authenticate(FakeWebSocket(cookies={"ampy3_session": "token"}))

    assert user["plex_user_id"] == "user-1"


async def test_ws_syncs_closes_unauthorized_connection(monkeypatch):
    """An unauthenticated client is closed with the unauthorized code.

    The socket is accepted first: a close frame can only be delivered after
    the handshake, otherwise the client only sees a bare HTTP 403.
    """
    monkeypatch.setattr(ws_api.settings, "secret_key", "a" * 32)
    monkeypatch.setattr(ws_api.settings, "require_auth", True)
    monkeypatch.setattr(ws_api, "verify_session", AsyncMock(return_value=None))

    ws = FakeWebSocket()
    await ws_api.websocket_syncs(ws)

    assert ws.accepted is True
    assert ws.closed_code == ws_api.WS_CLOSE_UNAUTHORIZED


async def test_ws_syncs_connects_without_auth_when_disabled(monkeypatch):
    """REQUIRE_AUTH=false keeps the realtime channel working."""
    monkeypatch.setattr(ws_api.settings, "require_auth", False)
    manager = WebSocketConnectionManager()
    monkeypatch.setattr(ws_api, "get_websocket_manager", lambda: manager)

    ws = FakeWebSocket()
    await ws_api.websocket_syncs(ws)

    assert ws.accepted is True
    assert manager.get_connection_count("syncs") == 0  # disconnected on teardown


async def test_ws_pipeline_rejects_non_owner(monkeypatch):
    """Only the owner of a sync may subscribe to its pipeline channel."""
    monkeypatch.setattr(ws_api.settings, "secret_key", "a" * 32)
    monkeypatch.setattr(ws_api.settings, "require_auth", True)
    monkeypatch.setattr(
        ws_api, "verify_session", AsyncMock(return_value={"plex_user_id": "user-2"})
    )
    monkeypatch.setattr(
        ws_api,
        "AsyncSessionLocal",
        lambda: FakeSession(results=[FakeResult(row=SimpleNamespace(id=5, user_id="user-1"))]),
    )

    ws = FakeWebSocket()
    await ws_api.websocket_pipeline(ws, "5")

    assert ws.accepted is True
    assert ws.closed_code == ws_api.WS_CLOSE_FORBIDDEN


async def test_ws_pipeline_rejects_invalid_sync_id(monkeypatch):
    """A non-numeric sync id is rejected before touching the database."""
    monkeypatch.setattr(ws_api.settings, "secret_key", "a" * 32)
    monkeypatch.setattr(ws_api.settings, "require_auth", True)
    monkeypatch.setattr(
        ws_api, "verify_session", AsyncMock(return_value={"plex_user_id": "user-1"})
    )

    ws = FakeWebSocket()
    await ws_api.websocket_pipeline(ws, "not-a-number")

    assert ws.accepted is True
    assert ws.closed_code == ws_api.WS_CLOSE_INVALID_SYNC_ID


async def test_ws_pipeline_allows_owner(monkeypatch):
    """The owner of a sync may subscribe to its pipeline channel."""
    monkeypatch.setattr(ws_api.settings, "secret_key", "a" * 32)
    monkeypatch.setattr(ws_api.settings, "require_auth", True)
    monkeypatch.setattr(
        ws_api, "verify_session", AsyncMock(return_value={"plex_user_id": "user-1"})
    )
    monkeypatch.setattr(
        ws_api,
        "AsyncSessionLocal",
        lambda: FakeSession(results=[FakeResult(row=SimpleNamespace(id=5, user_id="user-1"))]),
    )
    manager = WebSocketConnectionManager()
    monkeypatch.setattr(ws_api, "get_websocket_manager", lambda: manager)

    ws = FakeWebSocket()
    await ws_api.websocket_pipeline(ws, "5")

    assert ws.accepted is True
    assert ws.closed_code is None


# ─────────────────────────────────────────────────────────────────────────────
# User scoping
# ─────────────────────────────────────────────────────────────────────────────


async def test_unmatched_tracks_are_scoped_to_the_user(monkeypatch):
    """get_unmatched_tracks must filter on the owning user."""
    fake = FakeSession()
    monkeypatch.setattr(syncs_api, "AsyncSessionLocal", lambda: fake)

    await syncs_api.get_unmatched_tracks(limit=50, _user={"plex_user_id": "user-1"})

    sql = compile_sql(fake.executed[0])
    assert "scheduled_playlist_syncs.user_id = 'user-1'" in sql


async def test_sync_status_unknown_task_is_not_found(monkeypatch):
    """A task the backend knows about but that cannot be mapped yields 404."""
    monkeypatch.setattr(syncs_api, "get_sync_id_for_task_async", AsyncMock(return_value=None))
    monkeypatch.setattr(
        syncs_api,
        "get_sync_status_task",
        lambda task_id: {"task_id": task_id, "status": "SUCCESS"},
    )

    with pytest.raises(HTTPException) as exc_info:
        await syncs_api.get_sync_status(task_id="task-x", _user={"plex_user_id": "user-1"})

    assert exc_info.value.status_code == 404


async def test_sync_status_returns_pending_while_the_task_is_unmapped(monkeypatch):
    """A queued task without a mapping must not 404 — the client keeps polling.

    The task is enqueued before the mapping is written, so a client that
    starts polling immediately must be told "pending" instead of "not found".
    """
    monkeypatch.setattr(syncs_api, "get_sync_id_for_task_async", AsyncMock(return_value=None))
    monkeypatch.setattr(
        syncs_api,
        "get_sync_status_task",
        lambda task_id: {"task_id": task_id, "status": "PENDING"},
    )

    result = await syncs_api.get_sync_status(task_id="task-x", _user={"plex_user_id": "user-1"})

    assert result["status"] == "PENDING"
    assert result["ready"] is False
    assert result["result"] is None


async def test_sync_status_rejects_non_owner(monkeypatch):
    """A task belonging to another user must not be readable."""
    monkeypatch.setattr(syncs_api, "get_sync_id_for_task_async", AsyncMock(return_value=42))
    monkeypatch.setattr(
        syncs_api,
        "AsyncSessionLocal",
        lambda: FakeSession(results=[FakeResult(row=SimpleNamespace(id=42, user_id="user-2"))]),
    )

    with pytest.raises(HTTPException) as exc_info:
        await syncs_api.get_sync_status(task_id="task-x", _user={"plex_user_id": "user-1"})

    assert exc_info.value.status_code == 404


async def test_sync_status_returns_task_status_for_owner(monkeypatch):
    """The owner of a sync gets the task status."""
    monkeypatch.setattr(syncs_api, "get_sync_id_for_task_async", AsyncMock(return_value=42))
    monkeypatch.setattr(
        syncs_api,
        "AsyncSessionLocal",
        lambda: FakeSession(results=[FakeResult(row=SimpleNamespace(id=42, user_id="user-1"))]),
    )
    monkeypatch.setattr(
        syncs_api,
        "get_sync_status_task",
        lambda task_id: {"task_id": task_id, "status": "SUCCESS"},
    )

    result = await syncs_api.get_sync_status(task_id="task-x", _user={"plex_user_id": "user-1"})

    assert result["status"] == "SUCCESS"


# ─────────────────────────────────────────────────────────────────────────────
# Audit log scoping
# ─────────────────────────────────────────────────────────────────────────────


def _audit_row(actor: str | None, row_id: int = 1):
    return SimpleNamespace(
        id=row_id,
        event_type="sync.created",
        resource_type="playlist",
        resource_id=str(row_id),
        actor_user_id=actor,
        summary="summary",
        details=None,
        created_at=None,
    )


async def test_audit_logs_are_scoped_to_the_user(monkeypatch):
    """Only the caller's own entries (plus unattributed legacy rows) are returned."""
    own = _audit_row("user-1", 1)
    fake = FakeSession(results=[FakeResult(scalar=1), FakeResult(rows=[own])])
    monkeypatch.setattr(audit_api, "AsyncSessionLocal", lambda: fake)

    response = await audit_api.list_audit_logs(
        limit=50,
        offset=0,
        event_type=None,
        _user={"plex_user_id": "user-1"},
    )

    assert response.total == 1
    assert [log.actor_user_id for log in response.logs] == ["user-1"]

    sql = compile_sql(fake.executed[0])
    assert "audit_log.actor_user_id = 'user-1'" in sql
    assert "audit_log.actor_user_id IS NULL" in sql


async def test_audit_count_uses_the_same_filter(monkeypatch):
    """The total count is filtered exactly like the page of entries."""
    fake = FakeSession(results=[FakeResult(scalar=0), FakeResult(rows=[])])
    monkeypatch.setattr(audit_api, "AsyncSessionLocal", lambda: fake)

    response = await audit_api.list_audit_logs(
        limit=10,
        offset=0,
        event_type="sync.created",
        _user={"plex_user_id": "user-1"},
    )

    assert response.total == 0
    assert response.logs == []

    count_sql = compile_sql(fake.executed[0])
    assert "audit_log.actor_user_id = 'user-1'" in count_sql
    assert "audit_log.actor_user_id IS NULL" in count_sql


# ─────────────────────────────────────────────────────────────────────────────
# SECRET_KEY / startup gate
# ─────────────────────────────────────────────────────────────────────────────


def test_unknown_settings_keys_are_ignored():
    """A stray key in .env must never prevent the app from starting."""
    from src.app.settings import Settings

    settings = Settings(_env_file=None, totally_unknown_key="value")

    # Known settings still load; the unknown key is simply dropped.
    assert settings.app_env
    assert settings.database_url


def test_production_without_secret_key_fails_the_startup_gate(monkeypatch):
    """APP_ENV=production without a SECRET_KEY must refuse to boot."""
    from src import main
    from src.app.settings import Settings

    # Construction is allowed: the key may still come from the config table.
    test_settings = Settings(
        _env_file=None,
        app_env="production",
        require_auth=False,
        secret_key="",
        database_username="test",
        database_password="test",
    )
    monkeypatch.setattr(main, "settings", test_settings)

    with pytest.raises(RuntimeError, match="APP_ENV=production requires SECRET_KEY"):
        main.enforce_startup_gate()


def test_production_allows_unconfigured_first_boot(monkeypatch):
    """A fresh production install may boot into the setup wizard."""
    from src import main
    from src.app.settings import Settings

    test_settings = Settings(
        _env_file=None,
        app_env="production",
        require_auth=False,
        secret_key="",
        database_username="test",
        database_password="test",
    )
    monkeypatch.setattr(main, "settings", test_settings)

    main.enforce_startup_gate(allow_unconfigured=True)


def test_production_with_secret_key_passes_the_startup_gate(monkeypatch):
    """A properly configured production instance starts."""
    from src import main
    from src.app.settings import Settings

    test_settings = Settings(
        _env_file=None,
        app_env="production",
        require_auth=False,
        secret_key="k" * 32,
        database_username="test",
        database_password="test",
    )
    monkeypatch.setattr(main, "settings", test_settings)

    main.enforce_startup_gate()


def test_require_auth_without_secret_key_fails_the_startup_gate(monkeypatch):
    """REQUIRE_AUTH=true always requires a SECRET_KEY."""
    from src import main
    from src.app.settings import Settings

    # Construction is allowed: the key may still come from the config table.
    test_settings = Settings(
        _env_file=None,
        app_env="development",
        require_auth=True,
        secret_key="",
        database_username="test",
        database_password="test",
    )
    monkeypatch.setattr(main, "settings", test_settings)

    with pytest.raises(RuntimeError, match="REQUIRE_AUTH=true requires SECRET_KEY"):
        main.enforce_startup_gate(allow_unconfigured=True)


def test_require_auth_gate_rejects_short_key():
    """REQUIRE_AUTH=true rejects SECRET_KEY < 32 chars."""
    from src.app.settings import Settings

    with pytest.raises(ValueError, match="at least 32 characters"):
        Settings(_env_file=None, require_auth=True, secret_key="short")


def test_require_auth_accepts_valid_key():
    """REQUIRE_AUTH=true accepts SECRET_KEY >= 32 chars."""
    from src.app.settings import Settings

    settings = Settings(_env_file=None, require_auth=True, secret_key="a" * 32)

    assert settings.secret_key == "a" * 32


# ─────────────────────────────────────────────────────────────────────────────
# PIN rate limiting
# ─────────────────────────────────────────────────────────────────────────────


class FakeAsyncValkey:
    """Async Valkey double for the PIN rate limiter."""

    def __init__(self, counts=None, fail=False):
        self.counts = list(counts or [])
        self.fail = fail
        self.evals: list[tuple[str, int, str, int]] = []

    async def incr(self, key):
        if self.fail:
            raise RuntimeError("valkey down")
        if self.counts:
            return self.counts.pop(0)
        return 1

    async def expire(self, key, ttl):
        return True

    async def eval(self, script, numkeys, *keys_and_args):
        """Emulate the atomic INCR+EXPIRE rate-limit script."""
        if self.fail:
            raise RuntimeError("valkey down")
        key = keys_and_args[0]
        window = keys_and_args[1]
        self.evals.append((script, numkeys, key, window))
        if self.counts:
            return self.counts.pop(0)
        return 1


class FakePlexClient:
    """httpx.AsyncClient double returning a canned PIN payload."""

    payload = {"id": 123, "code": "ABCD"}

    def __init__(self, *args, **kwargs):
        pass

    async def __aenter__(self):
        return self

    async def __aexit__(self, *args):
        return None

    async def post(self, url, params=None, headers=None):
        return SimpleNamespace(
            json=lambda: dict(self.payload),
            raise_for_status=lambda: None,
        )


@pytest.fixture
def plex_login_env(monkeypatch):
    """Patch out everything plex_login touches except the rate limiter."""
    monkeypatch.setattr(auth_router.settings, "secret_key", "a" * 32)
    monkeypatch.setattr(auth_router.settings, "require_auth", True)
    monkeypatch.setattr(auth_router, "_get_client_id", AsyncMock(return_value="client-id"))
    monkeypatch.setattr(auth_router.httpx, "AsyncClient", FakePlexClient)
    # The blocking (sync) client must never be used from an async handler.
    monkeypatch.setattr(
        auth_router.ValkeyService,
        "get_sync_instance",
        classmethod(lambda cls: pytest.fail("blocking Valkey client used in async handler")),
    )


def _use_valkey(monkeypatch, client):
    monkeypatch.setattr(
        auth_router.ValkeyService,
        "get_instance",
        classmethod(lambda cls: client),
    )
    return client


async def test_plex_login_rate_limits_per_ip(monkeypatch, plex_login_env):
    """PIN requests are capped per client IP."""
    client = FakeAsyncValkey(counts=list(range(1, 12)))
    _use_valkey(monkeypatch, client)

    request = make_request("10.0.0.7")
    for _ in range(10):
        response = await auth_router.plex_login(request)
        assert response.status_code == 307

    response = await auth_router.plex_login(request)
    assert response.status_code == 429
    assert "Too many PIN requests" in json.loads(response.body)["detail"]


async def test_plex_login_arms_the_window_atomically(monkeypatch, plex_login_env):
    """The rate-limit counter and its TTL are set in one atomic script call."""
    client = FakeAsyncValkey(counts=[1])
    _use_valkey(monkeypatch, client)

    response = await auth_router.plex_login(make_request("10.0.0.8"))

    assert response.status_code == 307
    assert len(client.evals) == 1
    script, numkeys, key, window = client.evals[0]
    assert numkeys == 1
    assert key == "ampy3:pin-attempts:10.0.0.8"
    assert window == 300
    # INCR and EXPIRE must happen in the same round trip, otherwise a crash
    # between them leaves the counter without a TTL.
    assert "INCR" in script and "EXPIRE" in script


async def test_plex_login_resets_after_the_window(monkeypatch, plex_login_env):
    """Once the counter expires the request is allowed again."""
    client = FakeAsyncValkey(counts=[11, 1])
    _use_valkey(monkeypatch, client)

    request = make_request("10.0.0.9")
    assert (await auth_router.plex_login(request)).status_code == 429
    assert (await auth_router.plex_login(request)).status_code == 307


async def test_plex_login_fails_open_when_rate_limiting_breaks(monkeypatch, plex_login_env):
    """A Valkey outage must not lock users out of the login flow."""
    client = FakeAsyncValkey(fail=True)
    _use_valkey(monkeypatch, client)

    response = await auth_router.plex_login(make_request("10.0.0.10"))

    assert response.status_code == 307


# ─────────────────────────────────────────────────────────────────────────────
# Cross-user isolation (websocket broadcast)
# ─────────────────────────────────────────────────────────────────────────────


async def test_websocket_broadcasts_filtered_by_user():
    """Broadcasts carrying an owner id only reach that user."""
    manager = WebSocketConnectionManager()

    ws1 = FakeWebSocket()
    ws2 = FakeWebSocket()

    await manager.connect(ws1, "syncs", user_id="user-1")
    await manager.connect(ws2, "syncs", user_id="user-2")

    await manager.broadcast(
        "syncs", "sync_updated", {"sync_id": 1, "status": "running"}, owner_id="user-1"
    )

    assert len(ws1.sent) == 1
    assert ws2.sent == []
