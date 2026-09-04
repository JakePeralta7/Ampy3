# CLI

Ampy3 ships with a small command-line tool: `migrate.py`. It manages database schema migrations and is what runs automatically at API startup.

## Commands

| Command | What it does |
|---------|--------------|
| `python migrate.py bootstrap` | Create the schema from the current ORM models and stamp at the Alembic baseline. Idempotent — also runs `upgrade()` if the DB is already stamped. |
| `python migrate.py upgrade` | Apply pending Alembic migrations. |
| `python migrate.py status` | Print the current Alembic revision + recent history. |
| `python migrate.py autogen` | Interactively generate a new Alembic migration from ORM changes. |

## Examples

```bash
# Fresh database — create schema + stamp
python migrate.py bootstrap

# Existing database — apply pending migrations
python migrate.py upgrade

# Check what's applied
python migrate.py status

# After editing ORM models
python migrate.py autogen   # follow the prompts
```

!!! note "API startup does this for you"
    [`init_db()`][app.db.init_db] in [`src/app/db.py`][app.db] runs the same logic at FastAPI startup. You only need to call `migrate.py` manually in CI or during explicit maintenance.

## Where to look next

- [Operations → Backup & restore](../operations/backup-restore.md)
- [Architecture → Migrations](../development/architecture.md#migrations)
- [`src/app/db.py`](https://github.com/JakePeralta7/Ampy3/blob/main/src/app/db.py)