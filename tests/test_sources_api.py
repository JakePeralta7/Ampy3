"""Source discovery and connection-test endpoints."""

import pytest

from src.app.api import sources as sources_api
from src.app.api.sources import get_sources
from src.app.schemas.sources import SourceTestRequest
from src.app.services.ytauth import get_ytmusic_auth, invalidate_ytmusic_auth_cache, validate_ytmusic_auth


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
    monkeypatch.setattr("src.app.services.ytauth._load_ytmusic_auth_sync", lambda: None)
    monkeypatch.setattr("src.app.settings.settings.ytmusic_auth", "")
    invalidate_ytmusic_auth_cache()

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
        "src.app.services.ytauth._load_ytmusic_auth_sync",
        lambda: {"Authorization": "SAPISIDHASH x", "Cookie": "y"},
    )
    invalidate_ytmusic_auth_cache()

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


async def test_test_source_ytmusic_uses_stored_auth_when_empty_body(monkeypatch) -> None:
    captured = {}

    def _validate(raw):
        captured["raw"] = raw

    monkeypatch.setattr("src.app.api.sources.validate_ytmusic_auth", _validate)
    monkeypatch.setattr(
        "src.app.services.ytauth._load_ytmusic_auth_sync",
        lambda: {"Authorization": "SAPISIDHASH stored", "Cookie": "stored"},
    )
    invalidate_ytmusic_auth_cache()
    result = await sources_api.test_source(
        SourceTestRequest(source_id="youtube_music"), _user={"id": "user"}
    )
    assert result.ok is True
    assert captured["raw"] == '{"Authorization": "SAPISIDHASH stored", "Cookie": "stored"}'


async def test_test_source_ytmusic_fails_when_no_stored_auth(monkeypatch) -> None:
    monkeypatch.setattr("src.app.services.ytauth._load_ytmusic_auth_sync", lambda: None)
    monkeypatch.setattr("src.app.settings.settings.ytmusic_auth", "")
    invalidate_ytmusic_auth_cache()
    result = await sources_api.test_source(
        SourceTestRequest(source_id="youtube_music"), _user={"id": "user"}
    )
    assert result.ok is False
    assert result.error and "No authentication payload provided" in result.error


async def test_get_ytmusic_auth_returns_none_when_unset(monkeypatch) -> None:
    monkeypatch.setattr("src.app.services.ytauth._load_ytmusic_auth_sync", lambda: None)
    invalidate_ytmusic_auth_cache()
    assert await get_ytmusic_auth() is None


async def test_get_ytmusic_auth_returns_none_when_invalid_json(monkeypatch) -> None:
    monkeypatch.setattr("src.app.services.ytauth._load_ytmusic_auth_sync", lambda: None)
    monkeypatch.setattr("src.app.settings.settings.ytmusic_auth", "not-json")
    invalidate_ytmusic_auth_cache()
    assert await get_ytmusic_auth() is None


async def test_get_ytmusic_auth_returns_none_when_not_object(monkeypatch) -> None:
    monkeypatch.setattr("src.app.services.ytauth._load_ytmusic_auth_sync", lambda: None)
    monkeypatch.setattr("src.app.settings.settings.ytmusic_auth", '["list"]')
    invalidate_ytmusic_auth_cache()
    assert await get_ytmusic_auth() is None


async def test_get_ytmusic_auth_uses_db_over_env(monkeypatch) -> None:
    monkeypatch.setattr(
        "src.app.services.ytauth._load_ytmusic_auth_sync",
        lambda: {"Authorization": "SAPISIDHASH db", "Cookie": "db"},
    )
    monkeypatch.setattr("src.app.settings.settings.ytmusic_auth", '{"Authorization": "env"}')
    invalidate_ytmusic_auth_cache()
    auth = await get_ytmusic_auth()
    assert auth == {"Authorization": "SAPISIDHASH db", "Cookie": "db"}


async def test_get_ytmusic_auth_falls_back_to_env_when_no_row(monkeypatch) -> None:
    monkeypatch.setattr("src.app.services.ytauth._stored_ytmusic_auth", lambda: "")
    monkeypatch.setattr(
        "src.app.settings.settings.ytmusic_auth", '{"Authorization": "SAPISIDHASH env"}'
    )
    invalidate_ytmusic_auth_cache()
    auth = await get_ytmusic_auth()
    assert auth == {"Authorization": "SAPISIDHASH env"}


async def test_get_ytmusic_auth_keeps_flat_headers(monkeypatch) -> None:
    monkeypatch.setattr(
        "src.app.services.ytauth._load_ytmusic_auth_sync",
        lambda: {"Authorization": "SAPISIDHASH x", "Cookie": "y"},
    )
    invalidate_ytmusic_auth_cache()
    assert await get_ytmusic_auth() == {"Authorization": "SAPISIDHASH x", "Cookie": "y"}


async def test_get_ytmusic_auth_unwraps_nested_headers(monkeypatch) -> None:
    monkeypatch.setattr(
        "src.app.services.ytauth._load_ytmusic_auth_sync",
        lambda: {"Authorization": "SAPISIDHASH x"},
    )
    invalidate_ytmusic_auth_cache()
    assert await get_ytmusic_auth() == {"Authorization": "SAPISIDHASH x"}


def test_validate_ytmusic_auth_rejects_empty() -> None:
    with pytest.raises(ValueError):
        validate_ytmusic_auth("")


def test_validate_ytmusic_auth_rejects_invalid_json() -> None:
    with pytest.raises(ValueError):
        validate_ytmusic_auth("nope")


def test_validate_ytmusic_auth_rejects_non_object() -> None:
    with pytest.raises(ValueError):
        validate_ytmusic_auth('["list"]')
