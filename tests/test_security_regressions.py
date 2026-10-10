"""Regressions for A-05/A-06 (URL validation), C-01 (dispatch lock) and A-08 (audit actor)."""

import pytest

from src.app.core.urls import InvalidServerUrlError, validate_server_url


class TestValidateServerUrl:
    def test_accepts_wellformed_http_urls(self):
        assert validate_server_url("http://plex.local:32400") == "http://plex.local:32400"
        assert (
            validate_server_url("https://jellyfin.example.com:443/")
            == "https://jellyfin.example.com:443/"
        )

    def test_rejects_non_http_schemes(self):
        for bad in ("ftp://plex.local", "file:///etc/passwd", "//plex.local", "plex.local"):
            with pytest.raises(InvalidServerUrlError):
                validate_server_url(bad)

    def test_rejects_empty(self):
        with pytest.raises(InvalidServerUrlError):
            validate_server_url("   ")

    def test_rejects_embedded_credentials(self):
        with pytest.raises(InvalidServerUrlError):
            validate_server_url("https://user:pw@plex.local")

    def test_rejects_query_and_fragment(self):
        with pytest.raises(InvalidServerUrlError):
            validate_server_url("http://plex.local?x=1")
        with pytest.raises(InvalidServerUrlError):
            validate_server_url("http://plex.local#y")

    def test_rejects_no_hostname(self):
        with pytest.raises(InvalidServerUrlError):
            validate_server_url("http:///")


async def test_identity_probe_allows_custom_hostname_when_server_matches(monkeypatch):
    from src.app.auth import router as auth_router

    async def fake_fetch(url):
        assert url == "https://plex.mydomain.com"
        return "M1"

    monkeypatch.setattr(auth_router, "_fetch_machine_identifier", fake_fetch)
    assert await auth_router._matches_resource_identity("https://plex.mydomain.com", "M1")


async def test_identity_probe_rejects_mismatched_server(monkeypatch):
    from src.app.auth import router as auth_router

    async def fake_fetch(url):
        return "M2"  # a different Plex server answers at this URL

    monkeypatch.setattr(auth_router, "_fetch_machine_identifier", fake_fetch)
    assert not await auth_router._matches_resource_identity("https://evil.example.com", "M1")


async def test_identity_probe_rejects_unreachable_server(monkeypatch):
    from src.app.auth import router as auth_router

    async def fake_fetch(url):
        return None

    monkeypatch.setattr(auth_router, "_fetch_machine_identifier", fake_fetch)
    assert not await auth_router._matches_resource_identity("https://down.example.com", "M1")


async def test_fetch_machine_identifier_parses_identity_response(monkeypatch):
    from src.app.auth import router as auth_router

    class FakeResp:
        def json(self):
            return {"MediaContainer": {"machineIdentifier": "M1"}}

        def raise_for_status(self):
            return None

    class FakeClient:
        def __init__(self, *args, **kwargs):
            pass

        async def __aenter__(self):
            return self

        async def __aexit__(self, *args):
            return None

        async def get(self, url):
            assert url == "http://server.myproxy.example:32400/identity"
            return FakeResp()

    monkeypatch.setattr(auth_router.httpx, "AsyncClient", FakeClient)
    machine_id = await auth_router._fetch_machine_identifier("http://server.myproxy.example:32400")
    assert machine_id == "M1"


def test_dispatch_lock_blocks_overlap_and_fails_open(monkeypatch):
    from src.app.services import scheduler as scheduler_service

    class FakeValkey:
        def __init__(self, result):
            self.result = result

        def set(self, name, value, nx=False, ex=None):
            return self.result

    class FakeService:
        client = None

        @classmethod
        def get_sync_instance(cls):
            return cls.client

    monkeypatch.setattr(scheduler_service, "ValkeyService", FakeService)

    # Lock unavailable => dispatch is skipped (already in progress).
    FakeService.client = FakeValkey(False)
    assert not scheduler_service._try_acquire_dispatch_lock(7)

    # Lock available => dispatch proceeds.
    FakeService.client = FakeValkey(True)
    assert scheduler_service._try_acquire_dispatch_lock(7)

    # Valkey outage => fail open (return unstored token), sync proceeds.
    FakeService.client = FakeValkey(False)

    def boom(*args, **kwargs):
        raise RuntimeError("valkey down")

    FakeService.get_sync_instance = staticmethod(boom)
    token = scheduler_service._try_acquire_dispatch_lock(7)
    assert token  # Token returned (not None), so sync will proceed
    assert isinstance(token, str)


def test_audit_actor_contextvar():
    from src.app.services.audit import get_audit_actor, set_audit_actor

    set_audit_actor({"plex_user_id": "user-123", "username": "alice"})
    assert get_audit_actor() == "user-123"

    set_audit_actor(None)
    assert get_audit_actor() is None

    set_audit_actor({"plex_user_id": "local"})
    assert get_audit_actor() == "local"


def test_audit_log_model_has_actor_column():
    from src.app.models import AuditLog

    assert hasattr(AuditLog, "actor_user_id")
