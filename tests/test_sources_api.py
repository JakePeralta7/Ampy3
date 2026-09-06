"""Source discovery and connection-test endpoints."""

import pytest

from src.app.api import sources as sources_api
from src.app.api.sources import get_sources
from src.app.schemas.sources import SourceTestRequest
from src.app.services.ytauth import get_ytmusic_auth, validate_ytmusic_auth


async def test_get_sources_lists_sources(monkeypatch) -> None:
    monkeypatch.setattr(
        "src.app.api.sources.SourceRegistry.list_sources",
        staticmethod(
            lambda: [
                {"id": "deezer", "name": "Deezer"},
                {"id": "youtube_music", "name": "YouTube Music"},
            ]
        ),
    )
    monkeypatch.setattr("src.app.services.ytauth._stored_ytmusic_auth", lambda: "")
    monkeypatch.setattr("src.app.settings.settings.ytmusic_auth", "")

    sources = await get_sources(_user={"id": "user"})

    by_id = {s["id"]: s for s in sources}
    assert by_id["deezer"] == {
        "id": "deezer",
        "name": "Deezer",
        "auth_required": False,
        "auth_set": None,
    }
    assert by_id["youtube_music"]["auth_required"] is True
    assert by_id["youtube_music"]["auth_set"] is False


async def test_get_sources_reports_ytmusic_auth_set(monkeypatch) -> None:
    monkeypatch.setattr(
        "src.app.api.sources.SourceRegistry.list_sources",
        staticmethod(lambda: [{"id": "youtube_music", "name": "YouTube Music"}]),
    )
    monkeypatch.setattr(
        "src.app.services.ytauth._stored_ytmusic_auth",
        lambda: '{"Authorization": "SAPISIDHASH x", "Cookie": "y"}',
    )

    sources = await get_sources(_user={"id": "user"})

    assert sources[0]["auth_set"] is True


async def test_test_source_anonymous_passes() -> None:
    result = await sources_api.test_source(
        SourceTestRequest(source_id="deezer"), _user={"id": "user"}
    )
    assert result.ok is True


async def test_test_source_unknown_fails() -> None:
    result = await sources_api.test_source(
        SourceTestRequest(source_id="nope"), _user={"id": "user"}
    )
    assert result.ok is False
    assert result.error and "Unknown source" in result.error


async def test_test_source_ytmusic_success(monkeypatch) -> None:
    monkeypatch.setattr("src.app.api.sources.validate_ytmusic_auth", lambda raw: None)
    result = await sources_api.test_source(
        SourceTestRequest(source_id="youtube_music", auth='{"cookies": {}}'),
        _user={"id": "user"},
    )
    assert result.ok is True


async def test_test_source_ytmusic_failure(monkeypatch) -> None:
    def _fail(raw):
        raise ValueError("The provided credentials do not authenticate to a YouTube Music account.")

    monkeypatch.setattr("src.app.api.sources.validate_ytmusic_auth", _fail)
    result = await sources_api.test_source(
        SourceTestRequest(source_id="youtube_music", auth="garbage"),
        _user={"id": "user"},
    )
    assert result.ok is False
    assert result.error and "do not authenticate" in result.error


def test_get_ytmusic_auth_returns_none_when_unset(monkeypatch) -> None:
    monkeypatch.setattr("src.app.services.ytauth._stored_ytmusic_auth", lambda: "")
    monkeypatch.setattr("src.app.settings.settings.ytmusic_auth", "")
    assert get_ytmusic_auth() is None


def test_get_ytmusic_auth_returns_none_when_invalid_json(monkeypatch) -> None:
    monkeypatch.setattr("src.app.services.ytauth._stored_ytmusic_auth", lambda: "not-json")
    assert get_ytmusic_auth() is None


def test_get_ytmusic_auth_returns_none_when_not_object(monkeypatch) -> None:
    monkeypatch.setattr("src.app.services.ytauth._stored_ytmusic_auth", lambda: '["list"]')
    assert get_ytmusic_auth() is None


def test_get_ytmusic_auth_uses_db_over_env(monkeypatch) -> None:
    monkeypatch.setattr(
        "src.app.services.ytauth._stored_ytmusic_auth",
        lambda: '{"Authorization": "SAPISIDHASH db", "Cookie": "db"}',
    )
    monkeypatch.setattr("src.app.settings.settings.ytmusic_auth", '{"Authorization": "env"}')
    auth = get_ytmusic_auth()
    assert auth == {"Authorization": "SAPISIDHASH db", "Cookie": "db"}


def test_get_ytmusic_auth_falls_back_to_env_when_no_row(monkeypatch) -> None:
    monkeypatch.setattr("src.app.services.ytauth._stored_ytmusic_auth", lambda: "")
    monkeypatch.setattr(
        "src.app.settings.settings.ytmusic_auth", '{"Authorization": "SAPISIDHASH env"}'
    )
    auth = get_ytmusic_auth()
    assert auth == {"Authorization": "SAPISIDHASH env"}


def test_get_ytmusic_auth_keeps_flat_headers(monkeypatch) -> None:
    payload = '{"Authorization": "SAPISIDHASH x", "Cookie": "y"}'
    monkeypatch.setattr("src.app.services.ytauth._stored_ytmusic_auth", lambda: payload)
    assert get_ytmusic_auth() == {"Authorization": "SAPISIDHASH x", "Cookie": "y"}


def test_get_ytmusic_auth_unwraps_nested_headers(monkeypatch) -> None:
    payload = '{"cookies": "abc", "headers": {"Authorization": "SAPISIDHASH x"}}'
    monkeypatch.setattr("src.app.services.ytauth._stored_ytmusic_auth", lambda: payload)
    assert get_ytmusic_auth() == {"Authorization": "SAPISIDHASH x"}


def test_validate_ytmusic_auth_rejects_empty() -> None:
    with pytest.raises(ValueError):
        validate_ytmusic_auth("")


def test_validate_ytmusic_auth_rejects_invalid_json() -> None:
    with pytest.raises(ValueError):
        validate_ytmusic_auth("nope")


def test_validate_ytmusic_auth_rejects_non_object() -> None:
    with pytest.raises(ValueError):
        validate_ytmusic_auth('["list"]')
