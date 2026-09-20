"""Unit tests for sync pipeline phases (FetchPhase, MatchPhase, FinalizePhase).

These tests exercise the phase logic with a fake session object -- no real
database is required.
"""

import asyncio
from contextlib import nullcontext
from unittest.mock import MagicMock

from src.app.core.models import PlaylistMetadata, TrackMetadata
from src.app.models import (
    PlaylistTrack,
    PlaylistTrackTarget,
    ScheduledPlaylistSync,
    SyncRun,
    SyncRunTrack,
    SyncRunTrackTarget,
)
from src.app.worker import phases
from src.app.worker.phases import FetchPhase, FinalizePhase, MatchPhase


class _FakeResult:
    """Mimics the ``scalars()`` result chain."""

    def __init__(self, rows: list):
        self._rows = rows

    def scalars(self):
        return self

    def all(self):
        return self._rows

    def first(self):
        return self._rows[0] if self._rows else None

    def unique(self):
        return self


class _FakeDB:
    """Paper stand-in for a SQLAlchemy session.

    ``by_entity`` maps a mapped class to the rows every select on that class
    should return (where-clauses are ignored).
    """

    def __init__(self):
        self.calls: list = []
        self.added: list = []
        self.deleted: list = []
        self.by_entity: dict = {}

    def execute(self, stmt):
        self.calls.append(stmt)
        entity = None
        try:
            entity = stmt.column_descriptions[0]["type"]
        except Exception:
            entity = None
        return _FakeResult(self.by_entity.get(entity, []))

    def add(self, obj):
        if isinstance(obj, ScheduledPlaylistSync) and obj.id is None:
            obj.id = 42
        self.added.append(obj)

    def add_all(self, objs):
        self.added.extend(objs)

    def delete(self, obj):
        self.deleted.append(obj)

    def flush(self):
        pass


class _FakeCtx:
    """Minimal SyncContext stand-in for the session bridge."""

    def __init__(self, sync_id: int, target_id: str, db: _FakeDB):
        self.sync_id = sync_id
        self.target_id = target_id
        self.playlist_title = None
        self.source_url = "https://www.deezer.com/playlist/1"
        self.target = None
        self._db = db

    def session(self):
        return nullcontext(self._db)


class _FakeSource:
    """Fake source adapter returning a canned playlist."""

    source_id = "deezer"
    display_name = "Deezer"

    @classmethod
    def supports_url(cls, url):  # noqa: ANN001
        return True

    async def get_playlist(self, url):  # noqa: ANN001
        raise AssertionError("get_playlist must not be called")


class _FakeSourceBad:
    """Fake source that rejects every URL."""

    source_id = "deezer"
    display_name = "Deezer"

    @classmethod
    def supports_url(cls, url):  # noqa: ANN001
        return False


class _FakeEngine:
    """Fake MatchEngine with a single built-in match."""

    async def run(self, track, rules=None):  # noqa: ANN001
        return [
            {
                "item_id": "plex-1",
                "title": "Song 1",
                "artist_name": "Artist",
                "_rule_id": 3,
            }
        ]


def _make_track(position: int, title: str, item_id: str, **kwargs):
    track = PlaylistTrack(
        sync_id=1, position=position, source_title=title, item_id=item_id, **kwargs
    )
    track.id = position + 100
    return track


def _async_stub(result):
    """``run_async`` replacement: return ``result``, discard the coroutine."""

    def _run(coro):
        if asyncio.iscoroutine(coro):
            coro.close()
        return result

    return _run


class TestFetchPhase:
    """Tests for FetchPhase."""

    def test_valid_url_persists_tracks(self, monkeypatch):
        fake_db = _FakeDB()
        ctx = _FakeCtx(sync_id=1, target_id="jellyfin", db=fake_db)
        playlist = PlaylistMetadata(
            source_id="deezer-1",
            source="deezer",
            title="Test Pl",
            tracks=[
                TrackMetadata(
                    title="Song 1",
                    artist_name="Artist",
                    duration_ms=120_000,
                    source_id="src-item-1",
                ),
                TrackMetadata(
                    title="Song 2",
                    artist_name="Artist",
                    duration_ms=180_000,
                    source_id="src-item-2",
                ),
            ],
            external_url="https://www.deezer.com/playlist/1",
        )

        monkeypatch.setattr(phases, "run_async", _async_stub(playlist))
        monkeypatch.setattr(phases, "session_scope", lambda: nullcontext(fake_db))
        monkeypatch.setattr(phases.SourceRegistry, "get", lambda source_id: _FakeSource)

        result = FetchPhase().execute(
            ctx,
            {
                "source_url": "https://www.deezer.com/playlist/1",
                "source": "deezer",
                "target_ids": ["jellyfin"],
            },
        )

        assert result.success
        assert result.data["track_items"] == ["src-item-1", "src-item-2"]
        assert [r["position"] for r in result.data["track_rows"]] == [0, 1]
        assert any(isinstance(obj, ScheduledPlaylistSync) for obj in fake_db.added)
        assert any(isinstance(obj, PlaylistTrack) for obj in fake_db.added)

    def test_invalid_url_fails_phase(self, monkeypatch):
        fake_db = _FakeDB()
        ctx = _FakeCtx(sync_id=1, target_id="jellyfin", db=fake_db)
        monkeypatch.setattr(phases.SourceRegistry, "get", lambda source_id: _FakeSourceBad)

        result = FetchPhase().execute(
            ctx,
            {"source_url": "not-a-url", "source": "deezer", "target_ids": ["jellyfin"]},
        )

        assert not result.success
        assert result.error is not None
        assert "Invalid" in result.error

    def test_save_source_tracks_updates_existing(self):
        fake_db = _FakeDB()
        old_0 = _make_track(0, "Old Title", "old-item-0")
        old_1 = _make_track(1, "Old Two", "old-item-1")
        fake_db.by_entity[PlaylistTrack] = [old_0, old_1]

        track_rows = [
            {"position": 0, "source_title": "New Title", "item_id": "new-item-0"},
            {"position": 1, "source_title": "New Two", "item_id": "new-item-1"},
        ]

        FetchPhase()._save_source_tracks(
            fake_db, None, "https://www.deezer.com/playlist/1", "deezer", "Pl", track_rows, []
        )

        assert old_0.source_title == "New Title"
        assert old_0.item_id == "new-item-0"
        assert old_1.item_id == "new-item-1"
        assert fake_db.deleted == []
        assert not [o for o in fake_db.added if isinstance(o, PlaylistTrack)]

    def test_save_source_tracks_deletes_removed_positions(self):
        fake_db = _FakeDB()
        old_0 = _make_track(0, "Keep", "item-0")
        old_1 = _make_track(1, "Keep", "item-1")
        old_2 = _make_track(2, "Gone", "item-2")
        fake_db.by_entity[PlaylistTrack] = [old_0, old_1, old_2]

        track_rows = [
            {"position": 0, "source_title": "Keep", "item_id": "item-0"},
            {"position": 1, "source_title": "Keep", "item_id": "item-1"},
        ]

        FetchPhase()._save_source_tracks(
            fake_db, None, "https://www.deezer.com/playlist/1", "deezer", "Pl", track_rows, []
        )

        assert fake_db.deleted == [old_2]

    def test_save_source_tracks_inserts_new(self):
        fake_db = _FakeDB()
        old_0 = _make_track(0, "Keep", "item-0")
        fake_db.by_entity[PlaylistTrack] = [old_0]

        track_rows = [
            {"position": 0, "source_title": "Keep", "item_id": "item-0"},
            {"position": 1, "source_title": "Brand New", "item_id": "item-new"},
        ]

        FetchPhase()._save_source_tracks(
            fake_db, None, "https://www.deezer.com/playlist/1", "deezer", "Pl", track_rows, []
        )

        new_tracks = [o for o in fake_db.added if isinstance(o, PlaylistTrack)]
        assert len(new_tracks) == 1
        assert new_tracks[0].position == 1
        assert new_tracks[0].source_title == "Brand New"
        assert old_0.source_title == "Keep"


class TestMatchPhase:
    """Tests for MatchPhase."""

    def test_empty_rules_marks_all_failed(self, monkeypatch):
        fake_db = _FakeDB()
        row = _make_track(0, "Song 1", "src1")
        fake_db.by_entity[PlaylistTrack] = [row]
        ctx = _FakeCtx(sync_id=1, target_id="jellyfin", db=fake_db)

        monkeypatch.setattr(phases, "get_active_rules_sync", lambda: [])

        result = MatchPhase().execute(ctx, {"track_items": ["src1", "src2"]})

        assert result.success
        assert result.data == {"matched": 0, "failed": 2}

    def test_loads_rules_once(self, monkeypatch):
        fake_db = _FakeDB()
        row = _make_track(0, "Song 1", "src1")
        fake_db.by_entity[PlaylistTrack] = [row]
        ctx = _FakeCtx(sync_id=1, target_id="jellyfin", db=fake_db)

        rules_mock = MagicMock(return_value=[])
        monkeypatch.setattr(phases, "get_active_rules_sync", rules_mock)

        MatchPhase().execute(ctx, {"track_items": ["src1", "src2"]})

        assert rules_mock.call_count == 1

    def test_successful_match_persists_target(self, monkeypatch):
        fake_db = _FakeDB()
        row = _make_track(0, "Song 1", "src1", source_artist="Artist")
        fake_db.by_entity[PlaylistTrack] = [row]
        ctx = _FakeCtx(sync_id=1, target_id="jellyfin", db=fake_db)

        monkeypatch.setattr(phases, "get_active_rules_sync", lambda: [object()])
        monkeypatch.setattr(phases, "MatchEngine", lambda target: _FakeEngine())
        monkeypatch.setattr(phases, "run_async", lambda coro: asyncio.run(coro))

        result = MatchPhase().execute(ctx, {"track_items": ["src1"]})

        assert result.success
        assert result.data == {"matched": 1, "failed": 0}
        assert any(type(call).__name__ == "Insert" for call in fake_db.calls)


class TestFinalizePhase:
    """Tests for FinalizePhase."""

    def test_finalize_counts_updates_run(self):
        fake_db = _FakeDB()
        run = SyncRun(sync_id=1, target_id="jellyfin", status="running", execution_id="e1")
        run.id = 5
        fake_db.by_entity[SyncRun] = [run]

        FinalizePhase()._finalize_counts(fake_db, _FakeCtx(1, "jellyfin", fake_db), 3, 1)

        assert run.matched_count == 3
        assert run.failed_count == 1
        assert run.status == "completed"

    def test_snapshot_history_builds_target_rows(self):
        fake_db = _FakeDB()
        run = SyncRun(sync_id=1, target_id="jellyfin", status="running", execution_id="e1")
        run.id = 5
        run_track = SyncRunTrack(run_id=5, position=0, item_id="src1", source_title="Song 1")
        run_track.id = 100
        track = _make_track(0, "Song 1", "src1")
        target = PlaylistTrackTarget(
            playlist_track_id=track.id, target_id="jellyfin", item_id="plex-1", title="Song 1"
        )
        track.targets.append(target)
        fake_db.by_entity[SyncRun] = [run]
        fake_db.by_entity[SyncRunTrack] = [run_track]
        fake_db.by_entity[PlaylistTrack] = [track]

        FinalizePhase()._snapshot_history(fake_db, _FakeCtx(1, "jellyfin", fake_db))

        assert len(fake_db.added) == 1
        row = fake_db.added[0]
        assert isinstance(row, SyncRunTrackTarget)
        assert row.sync_run_track_id == 100
        assert row.item_id == "plex-1"
        assert row.target_id == "jellyfin"

    def test_execute_wiring(self, monkeypatch):
        fake_db = _FakeDB()
        ctx = _FakeCtx(sync_id=1, target_id="jellyfin", db=fake_db)

        phase = FinalizePhase()
        for name in ("_finalize_counts", "_snapshot_history", "_update_stats"):
            monkeypatch.setattr(phase, name, MagicMock())
        monkeypatch.setattr(phase, "_collect_matched_ids", MagicMock(return_value=[]))
        monkeypatch.setattr(phase, "_get_playlist_id", MagicMock(return_value="plex-list-1"))
        monkeypatch.setattr(phase, "_sync_target_playlist", MagicMock())

        result = phase.execute(ctx, {"matched": 2, "failed": 1})

        assert result.success
        assert result.data["matched"] == 2
        assert result.data["failed"] == 1
        assert result.data["target_playlist_id"] == "plex-list-1"
        phase._finalize_counts.assert_called_once_with(fake_db, ctx, 2, 1)
