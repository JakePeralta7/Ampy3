"""Shared music-platform client Valkey caching tests.

Caching moved from ``IPlatformSource.get_playlist`` into the per-platform
clients (``YouTubeMusicClient`` / ``DeezerClient``), so these tests exercise
the client layer directly.
"""

import json

import pytest

from src.app.core.clients.deezer import DeezerClient
from src.app.core.clients.ytmusic import YouTubeMusicClient
from src.app.core.models import TrackMetadata
from src.app.core.sources.ytmusic import YouTubeMusicSource
from src.app.services.valkey import ValkeyService
from src.app.settings import settings


class FakeCache:
    def __init__(self):
        self.store: dict[str, tuple[int, str]] = {}
        self.read_error: Exception | None = None
        self.write_error: Exception | None = None

    def get(self, key):
        if self.read_error:
            raise self.read_error
        entry = self.store.get(key)
        return entry[1] if entry else None

    def setex(self, key, ttl, value):
        if self.write_error:
            raise self.write_error
        self.store[key] = (ttl, value)

    def keys(self):
        return list(self.store)


@pytest.fixture
def cache(monkeypatch):
    instance = FakeCache()
    monkeypatch.setattr(ValkeyService, "get_sync_instance", classmethod(lambda cls: instance))
    return instance


@pytest.fixture
def yt_client():
    client = YouTubeMusicClient()
    return client


# ── YouTube MusicClient ─────────────────────────────────────────────


async def test_ytmusic_playlist_miss_stores_then_hits(cache, yt_client, monkeypatch):
    calls = []

    async def fake_run(method_name, *args, **kwargs):
        calls.append((method_name, args, kwargs))
        return {"title": "Playlist", "tracks": [{"title": "Song", "videoId": "v1"}]}

    monkeypatch.setattr(yt_client, "_run", fake_run)
    monkeypatch.setattr("src.app.core.clients.ytmusic.get_ytmusic_auth", lambda: None)

    first = await yt_client.get_playlist("PL123")
    second = await yt_client.get_playlist("PL123")

    assert first == second == {"title": "Playlist", "tracks": [{"title": "Song", "videoId": "v1"}]}
    assert len(calls) == 1
    assert "youtube_music:get_playlist:PL123" in cache.store
    ttl, payload = cache.store["youtube_music:get_playlist:PL123"]
    assert ttl == settings.source_playlist_cache_ttl_seconds
    assert json.loads(payload) == {
        "title": "Playlist",
        "tracks": [{"title": "Song", "videoId": "v1"}],
    }


async def test_ytmusic_home_key_annotated_with_session(cache, yt_client, monkeypatch):
    async def fake_run(method_name, *args, **kwargs):
        return {"Personal": [{"title": "Pick", "playlistId": "PL1"}]}

    monkeypatch.setattr(yt_client, "_run", fake_run)
    monkeypatch.setattr("src.app.core.clients.ytmusic.get_ytmusic_auth", lambda: None)

    await yt_client.get_home()

    assert "youtube_music:get_home:anon" in cache.store
    ttl, _ = cache.store["youtube_music:get_home:anon"]
    assert ttl == settings.explore_cache_ttl_seconds


async def test_ytmusic_reauth_isolates_home_cache(cache, yt_client, monkeypatch):
    calls = []

    async def fake_run(method_name, *args, **kwargs):
        calls.append(method_name)
        return {"Personal": []}

    monkeypatch.setattr(yt_client, "_run", fake_run)
    monkeypatch.setattr("src.app.core.clients.ytmusic.get_ytmusic_auth", lambda: None)

    await yt_client.get_home()
    assert calls == ["get_home"]

    monkeypatch.setattr(
        "src.app.core.clients.ytmusic.get_ytmusic_auth",
        lambda: {"Authorization": "SAPISIDHASH new", "Cookie": "c"},
    )
    await yt_client.get_home()

    assert calls == ["get_home", "get_home"]
    assert "youtube_music:get_home:anon" in cache.store
    assert any(k.startswith("youtube_music:get_home:session:") for k in cache.store)


async def test_ytmusic_force_bypasses_cache(cache, yt_client, monkeypatch):
    calls = []

    async def fake_run(method_name, *args, **kwargs):
        calls.append(method_name)
        return {"top_songs": []}

    monkeypatch.setattr(yt_client, "_run", fake_run)
    monkeypatch.setattr("src.app.core.clients.ytmusic.get_ytmusic_auth", lambda: None)

    await yt_client.get_home()
    await yt_client.get_home()
    await yt_client.get_home(force=True)

    assert calls == ["get_home", "get_home"]


async def test_ytmusic_failed_fetch_is_not_cached(cache, yt_client, monkeypatch):
    async def fake_run(method_name, *args, **kwargs):
        raise RuntimeError("upstream down")

    monkeypatch.setattr(yt_client, "_run", fake_run)

    with pytest.raises(RuntimeError):
        await yt_client.get_playlist("PL123")

    assert cache.store == {}


async def test_ytmusic_malformed_cache_falls_back_to_fetch(cache, yt_client, monkeypatch):
    cache.store["youtube_music:get_playlist:PL123"] = (60, "not json")
    calls = []

    async def fake_run(method_name, *args, **kwargs):
        calls.append(method_name)
        return {"title": "Fresh", "tracks": []}

    monkeypatch.setattr(yt_client, "_run", fake_run)

    result = await yt_client.get_playlist("PL123")

    assert result == {"title": "Fresh", "tracks": []}
    assert calls == ["get_playlist"]


async def test_ytmusic_cache_read_error_falls_back(cache, yt_client, monkeypatch):
    cache.read_error = ConnectionError("valkey down")
    calls = []

    async def fake_run(method_name, *args, **kwargs):
        calls.append(method_name)
        return {"title": "Fresh", "tracks": []}

    monkeypatch.setattr(yt_client, "_run", fake_run)

    result = await yt_client.get_playlist("PL123")

    assert result == {"title": "Fresh", "tracks": []}
    assert calls == ["get_playlist"]


# ── DeezerClient ────────────────────────────────────────────────────


async def test_deezer_playlist_cache(cache, monkeypatch):
    client = DeezerClient()
    calls = []

    async def fake_get(endpoint, params=None):
        calls.append((endpoint, params))
        return {"title": "Mix", "id": 123, "tracks": {"data": [{"title": "Song"}]}}

    monkeypatch.setattr(client, "_get", fake_get)

    first = await client.get_playlist("123")
    second = await client.get_playlist("123")

    assert first == second == {"title": "Mix", "id": 123, "tracks": {"data": [{"title": "Song"}]}}
    assert calls == [("playlist/123", None)]
    assert "deezer:get_playlist:123" in cache.store
    assert cache.store["deezer:get_playlist:123"][0] == settings.source_playlist_cache_ttl_seconds


async def test_deezer_moods_cached(cache, monkeypatch):
    client = DeezerClient()

    async def fake_get(endpoint, params=None):
        return [{"id": 1, "name": "Party"}]

    monkeypatch.setattr(client, "_get", fake_get)

    moods = await client.get_moods()
    again = await client.get_moods()

    assert moods == again == [{"id": 1, "name": "Party"}]
    assert "deezer:get_moods" in cache.store
    assert cache.store["deezer:get_moods"][0] == settings.explore_cache_ttl_seconds


async def test_deezer_failed_fetch_is_not_cached(cache, monkeypatch):
    client = DeezerClient()

    async def fake_get(endpoint, params=None):
        raise RuntimeError("upstream down")

    monkeypatch.setattr(client, "_get", fake_get)

    with pytest.raises(RuntimeError):
        await client.get_playlist("123")

    assert cache.store == {}


# ── source parsing still covered ────────────────────────────────────


def test_ytmusic_parser_keeps_source_metadata_mapping():
    playlist = YouTubeMusicSource._parse_playlist_data(
        "PL123",
        "https://music.youtube.com/playlist?list=PL123",
        {
            "title": "Playlist",
            "description": "Description",
            "tracks": [
                {
                    "videoId": "video-1",
                    "title": "Song",
                    "artists": [{"name": "Artist"}],
                    "album": {"name": "Album"},
                    "duration_seconds": 123,
                    "musicbrainz_id": "mbid-1",
                }
            ],
        },
    )

    assert playlist.source_id == "PL123"
    assert playlist.description == "Description"
    assert playlist.tracks == [
        TrackMetadata(
            mbid="mbid-1",
            title="Song",
            artist_name="Artist",
            album_name="Album",
            duration_ms=123000,
            source_id="video-1",
        )
    ]
