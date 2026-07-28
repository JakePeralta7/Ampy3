import json

import pytest

from src.app.core.models import IPlatformSource, PlaylistMetadata, TrackMetadata
from src.app.core.sources.ytmusic import YouTubeMusicSource
from src.app.services.valkey import ValkeyService
from src.app.settings import settings


class FakeCache:
    def __init__(
        self,
        value=None,
        read_error: Exception | None = None,
        write_error: Exception | None = None,
    ):
        self.value = value
        self.read_error = read_error
        self.write_error = write_error
        self.writes = []

    def get(self, key):
        if self.read_error:
            raise self.read_error
        return self.value

    def setex(self, key, ttl, value):
        if self.write_error:
            raise self.write_error
        self.writes.append((key, ttl, value))


class FakeSource(IPlatformSource):
    source_id = "fake"
    display_name = "Fake"

    def __init__(self):
        self.fetch_count = 0

    @classmethod
    def supports_url(cls, url: str) -> bool:
        return True

    async def _fetch_playlist(self, playlist_url: str) -> PlaylistMetadata:
        self.fetch_count += 1
        return PlaylistMetadata(
            source_id="playlist-1",
            source=self.source_id,
            title="Example",
            tracks=[TrackMetadata(title="Track", artist_name="Artist", source_id="track-1")],
            external_url=playlist_url,
        )

    def get_playlist_cache_identifier(self, playlist_url: str) -> str:
        return "playlist-1"


@pytest.fixture
def cache(monkeypatch):
    instance = FakeCache()
    monkeypatch.setattr(ValkeyService, "get_sync_instance", classmethod(lambda cls: instance))
    return instance


async def test_cache_miss_fetches_and_stores_normalized_playlist(cache):
    source = FakeSource()

    playlist = await source.get_playlist("https://example.test/playlist/1")

    assert source.fetch_count == 1
    assert playlist.tracks[0].title == "Track"
    assert cache.writes[0][0] == "source:playlist:fake:playlist-1"
    assert cache.writes[0][1] == settings.source_playlist_cache_ttl_seconds
    assert json.loads(cache.writes[0][2])["tracks"][0]["artist_name"] == "Artist"


async def test_cache_hit_avoids_provider_fetch(cache):
    cache.value = json.dumps(
        {
            "source_id": "playlist-1",
            "source": "fake",
            "title": "Cached",
            "description": "",
            "external_url": "https://example.test/playlist/1",
            "tracks": [{"title": "Track", "artist_name": "Artist"}],
        }
    )
    source = FakeSource()

    playlist = await source.get_playlist("https://example.test/playlist/1")

    assert source.fetch_count == 0
    assert playlist.title == "Cached"
    assert playlist.tracks == [TrackMetadata(title="Track", artist_name="Artist")]


async def test_cache_key_is_namespaced_by_source_and_identifier():
    class OtherSource(FakeSource):
        source_id = "other"

    url = "https://example.test/playlist/1"
    assert FakeSource()._playlist_cache_key(url) != OtherSource()._playlist_cache_key(url)


async def test_malformed_cache_falls_back_to_provider(cache):
    cache.value = "not json"
    source = FakeSource()

    playlist = await source.get_playlist("https://example.test/playlist/1")

    assert playlist.title == "Example"
    assert source.fetch_count == 1


async def test_cache_errors_do_not_prevent_fetch_or_sync(monkeypatch):
    instance = FakeCache(read_error=ConnectionError("down"), write_error=ConnectionError("down"))
    monkeypatch.setattr(ValkeyService, "get_sync_instance", classmethod(lambda cls: instance))
    source = FakeSource()

    playlist = await source.get_playlist("https://example.test/playlist/1")

    assert playlist.title == "Example"
    assert source.fetch_count == 1


def test_ytmusic_parser_keeps_source_metadata_mapping():
    playlist = YouTubeMusicSource._parse_playlist_data(
        "PL123",
        "https://music.youtube.com/playlist?list=PL123",
        {
            "title": "Playlist",
            "description": "Description",
            "entries": [
                {
                    "id": "video-1",
                    "title": "Song",
                    "creator": "Artist",
                    "album": "Album",
                    "duration": 123.4,
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
            duration_ms=123400,
            source_id="video-1",
        )
    ]
