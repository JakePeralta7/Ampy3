# Backup & restore

Three things to protect: the **Postgres database** (the source of truth for sync state, match rules, audit log, sessions), the **`cookies/` directory** (so the worker can re-authenticate to YouTube Music), and any **custom match rules or schedules** you have (those live in the DB but are worth naming explicitly).

## Postgres backup

The database container exposes `pg_dump` / `pg_restore`. The simplest approach:

```bash
# Logical backup — works across Postgres major versions
docker compose exec -T postgres pg_dump -U ampy3 -Fc ampy3 > backup-$(date +%F).dump

# Restore (DESTRUCTIVE — wipes existing DB)
docker compose exec -T postgres dropdb -U ampy3 ampy3 --if-exists
docker compose exec -T postgres createdb -U ampy3 ampy3
docker compose exec -T postgres pg_restore -U ampy3 -d ampy3 --no-owner < backup-YYYY-MM-DD.dump
```

!!! tip "Schedule it"
    Run this from a cron job on the host, or from a separate "backup" container, with daily retention. The audit log table grows monotonically — most users want at least 30 days of history, with a longer cold-storage tier.

## Continuous WAL archiving (advanced)

For point-in-time recovery, enable Postgres WAL archiving in a custom override of `docker-compose.yml`:

```yaml
services:
  postgres:
    command: >
      postgres
      -c archive_mode=on
      -c archive_command='test ! -f /var/lib/postgresql/wal/%f && cp %p /var/lib/postgresql/wal/%f'
    volumes:
      - postgres_wal:/var/lib/postgresql/wal
```

Combined with a daily logical backup, this gives you both PITR and simple restores.

## Valkey

Valkey is configured with **RDB snapshots every 60s + AOF everysec**, so it can lose at most ~1 second of broker state on a crash. For most Ampy3 deployments this is fine — tasks re-enqueue on the next scheduler tick or manual run.

If you want zero broker loss, configure replication (`--replicaof ...`) or run a managed Redis-compatible service.

```bash
# Manual RDB snapshot
docker compose exec valkey redis-cli BGSAVE

# List RDB files
docker compose exec valkey ls -la /data
```

## Cookies

The `cookies/` directory is a bind mount — **back it up alongside the database**. Cookies expire (typically a few weeks to months); refresh them periodically and rerun any sync that fails with an auth error.

## Migration workflow

The `migrate.py` CLI manages schema changes:

```bash
# Show what's applied
python migrate.py status

# Apply pending migrations
python migrate.py upgrade

# Bootstrap a fresh database (creates schema from ORM models + stamps baseline)
python migrate.py bootstrap

# Generate a new migration after changing ORM models
python migrate.py autogen
```

`bootstrap` is what runs automatically at API startup via [`init_db()`][app.db.init_db] — see [`src/app/db.py`][app.db] for the exact behaviour. In a fresh DB it creates the schema and stamps it at the Alembic baseline. In an existing DB it runs `upgrade()`.

!!! warning "Don't edit `alembic.ini`'s `sqlalchemy.url`"
    The placeholder URL is overridden at runtime from `settings.database_url`. Editing the ini directly is a no-op at best, breakage at worst.

## Restore-from-zero procedure

Total loss (new VM, empty disks):

1. `git clone https://github.com/JakePeralta7/Ampy3 && cd Ampy3`
2. Recreate `cookies/` with your `cookies.txt`
3. Restore Postgres: `docker compose up -d postgres && docker compose exec -T postgres pg_restore ...`
4. `docker compose up --build -d`
5. Verify: `curl http://localhost:8000/health`

## What to back up

| Data | Where | Backup method |
|------|-------|---------------|
| Sync state, match rules, schedules, audit log, sessions, owner token | Postgres | `pg_dump` (above) |
| YouTube Music auth | `cookies/cookies.txt` | Copy the file |
| Plex SSO owner token | Postgres `Config` table | Covered by `pg_dump` — *but rotating your Plex password invalidates it* |
| Custom node handlers / source adapters | Source code in this repo | Git, not Postgres |
| Custom match-rule canvases | Postgres | Covered by `pg_dump` |

## Where to look next

- [Docker](docker.md) — service topology
- [Monitoring](monitoring.md) — verify your backups with the audit log query
- [`migrate.py`](https://github.com/JakePeralta7/Ampy3/blob/main/migrate.py) — migration CLI source