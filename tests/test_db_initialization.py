from pathlib import Path

from src.app import db


class FakeConnection:
    async def run_sync(self, function, *args, **kwargs):
        self.function = function


class FakeBeginContext:
    def __init__(self, connection):
        self.connection = connection

    async def __aenter__(self):
        return self.connection

    async def __aexit__(self, exc_type, exc, traceback):
        return False


class FakeAsyncEngine:
    def __init__(self):
        self.connection = FakeConnection()
        self.begin_called = False

    def begin(self):
        self.begin_called = True
        return FakeBeginContext(self.connection)


async def test_init_db_bootstraps_and_stamps_a_fresh_database(monkeypatch):
    engine = FakeAsyncEngine()
    stamped = []

    async def is_unmanaged():
        return False

    async def seed_rules():
        return None

    monkeypatch.setattr(db, "async_engine", engine)
    monkeypatch.setattr(db, "_is_alembic_managed", is_unmanaged)
    monkeypatch.setattr(db.command, "stamp", lambda config, revision: stamped.append(revision))
    monkeypatch.setattr("src.app.match_rules.loader.seed_default_rules", seed_rules)

    await db.init_db()

    assert engine.begin_called
    assert engine.connection.function.__self__ is db.Base.metadata
    assert engine.connection.function.__name__ == "create_all"
    assert stamped == ["head"]


async def test_init_db_upgrades_a_managed_database_without_creating_tables(monkeypatch):
    engine = FakeAsyncEngine()
    upgraded = []

    async def is_managed():
        return True

    async def seed_rules():
        return None

    monkeypatch.setattr(db, "async_engine", engine)
    monkeypatch.setattr(db, "_is_alembic_managed", is_managed)
    monkeypatch.setattr(db.command, "upgrade", lambda config, revision: upgraded.append(revision))
    monkeypatch.setattr("src.app.match_rules.loader.seed_default_rules", seed_rules)

    await db.init_db()

    assert upgraded == ["head"]
    assert not engine.begin_called


def test_alembic_has_orm_baseline_revision():
    versions_dir = Path(__file__).parents[1] / "alembic" / "versions"
    revisions = sorted(
        path.name for path in versions_dir.glob("*.py") if path.name != "__init__.py"
    )

    assert "001_orm_schema_baseline.py" in revisions
