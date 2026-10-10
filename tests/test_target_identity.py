"""Regressions for B-01/B-02 (Jellyfin pagination) and B-07 (exact identity lookup)."""

from types import SimpleNamespace

from src.app.core.targets.jellyfin import JellyfinTarget
from src.app.core.targets.plex import PlexTarget


class FakeResp:
    def __init__(self, data):
        self._data = data

    def raise_for_status(self):
        pass

    def json(self):
        return self._data


def _make_jellyfin(monkeypatch, pages_by_start_index):
    """Return a JellyfinTarget wired to a stub HTTP client serving page fixtures."""
    target = JellyfinTarget(api_key="k", base_url="http://jf.local", user_id="u")
    calls = []

    class FakeClient:
        async def get(self, path, params=None):
            calls.append((path, params))
            start = int(params["StartIndex"]) if params else 0
            return FakeResp(pages_by_start_index[start])

    target._client = FakeClient()
    return target, calls


async def test_jellyfin_get_items_in_playlist_paginates():
    t, _ = _make_jellyfin(
        None,
        {
            0: {
                "Items": [{"Id": "1", "Name": "a"}, {"Id": "2", "Name": "b"}],
                "TotalRecordCount": 3,
            },
            2: {"Items": [{"Id": "3", "Name": "c"}], "TotalRecordCount": 3},
        },
    )
    items = await t.get_items_in_playlist("pl1")
    assert [i["item_id"] for i in items] == ["1", "2", "3"]


async def test_jellyfin_search_playlists_paginates_and_filters():
    pages = {
        0: {
            "Items": [
                {"Id": "p1", "Name": "Rock Hits", "Overview": "{}"},
                {"Id": "p2", "Name": "Chill Vibes", "Overview": "{}"},
            ],
            "TotalRecordCount": 3,
        },
        2: {"Items": [{"Id": "p3", "Name": "More Rock", "Overview": "{}"}], "TotalRecordCount": 3},
    }
    t, calls = _make_jellyfin(None, pages)

    out = await t.search_playlists("rock")
    assert [p["title"] for p in out] == ["Rock Hits", "More Rock"]
    # Two page requests, both carry StartIndex.
    assert [c[1]["StartIndex"] for c in calls] == ["0", "2"]


async def test_jellyfin_metadata_roundtrip_exact_lookup(monkeypatch):
    expected = {
        "playlist_id": "9",
        "title": "My Mix",
        "summary": '{"source_url": "https://music.youtube.com/playlist?list=PLabc", "sync_id": 4}',
        "track_count": 0,
    }

    async def fake_search(_query):
        return [expected]

    # Exact source id in metadata JSON matches.
    t = JellyfinTarget(api_key="k", base_url="http://jf.local", user_id="u")
    monkeypatch.setattr(t, "search_playlists", fake_search)
    assert await t.get_playlist_by_source_id("PLabc") == expected

    # Foreign id embedded in a URL must NOT match (substring regression).
    async def fake_search_other(_query):
        return [
            {
                "playlist_id": "9",
                "title": "My Mix",
                "summary": '{"source_url": "https://music.youtube.com/playlist?list=PLabc_x"}',
                "track_count": 0,
            }
        ]

    t2 = JellyfinTarget(api_key="k", base_url="http://jf.local", user_id="u")
    monkeypatch.setattr(t2, "search_playlists", fake_search_other)
    assert await t2.get_playlist_by_source_id("abc") is None
    # Exact id of the OTHER playlist still resolves.
    assert (await t2.get_playlist_by_source_id("PLabc_x"))["playlist_id"] == "9"


def test_jellyfin_meta_parsing_helpers():
    t = JellyfinTarget(api_key="k", base_url="http://jf.local", user_id="u")
    assert t._meta_from_overview({"summary": '{"source_id": "S1"}'}) == {"source_id": "S1"}
    assert t._meta_from_overview({"summary": "not json"}) == {}
    assert t._meta_from_overview({"summary": ""}) == {}
    assert t._source_id_from_url("https://x/playlist?list=PLQ&si=1") == "PLQ"
    assert t._source_id_from_url("https://x/playlist?si=1") == ""


async def test_plex_exact_source_id_lookup_does_not_substring_match(monkeypatch):
    t = PlexTarget(token="tok", base_url="http://plex.local:32400")

    xml_other = (
        '<MediaContainer size="1">'
        '<Playlist ratingKey="10" title="Mix" '
        'summary="{&quot;source_url&quot;: &quot;https://music.youtube.com/playlist?list=PLabc_deep&quot;}"/>'
        "</MediaContainer>"
    )
    calls = []

    class FakeResp:
        def raise_for_status(self):
            pass

        @property
        def text(self):
            return xml_other

    class FakeClient:
        async def get(self, url, params=None):
            calls.append(url)
            return FakeResp()

    t._client = FakeClient()

    # 'abc' is a substring of the stored id 'PLabc_deep' — must NOT match.
    assert await t.get_playlist_by_source_id("abc") is None
    assert (await t.get_playlist_by_source_id("PLabc_deep"))["rating_key"] == "10"


def test_plex_meta_parsing_helpers():
    t = PlexTarget(token="tok", base_url="http://plex.local:32400")
    assert t._meta_from_summary('{"source_id": "S1"}') == {"source_id": "S1"}
    assert t._meta_from_summary("not json") == {}
    assert t._meta_from_summary("") == {}
    assert t._source_id_from_url("https://x/playlist?list=PLQ&si=1") == "PLQ"


def test_source_id_from_url_handles_both_source_shapes():
    from src.app.core.urls import source_id_from_url

    # YouTube Music query form.
    assert source_id_from_url("https://music.youtube.com/playlist?list=PLabc&si=1") == "PLabc"
    # Deezer path form.
    assert source_id_from_url("https://www.deezer.com/playlist/123456") == "123456"
    assert source_id_from_url("https://www.deezer.com/playlist/123456?utm=x") == "123456"
    # No playlist reference.
    assert source_id_from_url("https://deezer.com/playlist") == ""
    assert source_id_from_url("") == ""


class _StubResult:
    def scalars(self):
        return SimpleNamespace(first=lambda: None)


class _StubDb:
    def execute(self, stmt):
        return _StubResult()


class _StubScope:
    def __enter__(self):
        return _StubDb()

    def __exit__(self, *args):
        return False


async def test_create_metadata_persists_source_id(monkeypatch):
    from src.app.core.urls import source_id_from_url
    from src.app.worker import playlist_sync as playlist_sync_module
    from src.app.worker.playlist_sync import PlaylistSync

    created = {}

    async def fake_update(*args, **kwargs):
        return True

    async def fake_create(**kwargs):
        created.update(kwargs)
        return "new-id"

    target = SimpleNamespace(create_playlist=fake_create, update_playlist=fake_update)
    ctx = SimpleNamespace(target_id="Plex", target=target)
    monkeypatch.setattr(playlist_sync_module, "session_scope", lambda: _StubScope())

    sync = PlaylistSync(ctx)
    result = await sync.sync(
        sync_id=3,
        title="My Mix",
        matched_item_ids=["mb:1", "mb:2"],
        source_url="https://music.youtube.com/playlist?list=PLabc",
    )

    assert result == "new-id"
    assert created["custom_metadata"]["sync_id"] == 3
    assert created["custom_metadata"]["source_url"].endswith("list=PLabc")
    assert (
        source_id_from_url(created["custom_metadata"]["source_url"])
        == created["custom_metadata"]["source_id"]
        == "PLabc"
    )


async def test_create_metadata_omits_source_id_when_unparseable(monkeypatch):
    from src.app.worker import playlist_sync as playlist_sync_module
    from src.app.worker.playlist_sync import PlaylistSync

    created = {}

    async def fake_update(*args, **kwargs):
        return True

    async def fake_create(**kwargs):
        created.update(kwargs)
        return "new-id"

    target = SimpleNamespace(create_playlist=fake_create, update_playlist=fake_update)
    ctx = SimpleNamespace(target_id="Plex", target=target)
    monkeypatch.setattr(playlist_sync_module, "session_scope", lambda: _StubScope())

    sync = PlaylistSync(ctx)
    await sync.sync(
        sync_id=3,
        title="My Mix",
        matched_item_ids=["mb:1"],
        source_url="https://example.com/not-a-playlist",
    )

    assert "source_id" not in created["custom_metadata"]
