# Monitoring

Ampy3 surfaces state in three places: structured logs, the audit log table, and the Celery broker. Knowing where to look is half the battle.

## Service health

```bash
docker compose ps
# Look for "healthy" — postgres, valkey, web
```

```bash
curl -s http://localhost:8000/health | jq
# {"status":"ok", ...}
```

The worker doesn't have a Docker-level healthcheck. Verify it's actually consuming with:

```bash
docker compose exec worker celery -A app.worker.app inspect ping
# -> pong
```

## Logs

```bash
docker compose logs -f --tail=200 web      # API + scheduler
docker compose logs -f --tail=200 worker   # Celery worker
docker compose logs -f --tail=200 postgres # DB
docker compose logs -f --tail=200 valkey   # broker
```

Useful log lines to grep for:

| Pattern | Meaning |
|---------|---------|
| `Registered source` / `Registered target` / `Registered node` | Startup side-effects — if you don't see them for something you expected, an import is missing. |
| `SyncPipeline` / `PhaseResult` | Per-track sync progress |
| `MatchEngine` / `MatchPhase` | MusicBrainz matching activity |
| `Failed to write audit log` | DB-side problem during an event — check disk + Postgres health. |
| `Owner registered` / `Login rejected` / `Plex target configured` | Auth flow milestones |

Set `CELERY_LOG_LEVEL=debug` for noisier (more diagnostic) Celery output.

## Audit log

Every meaningful action is recorded via [`log_event`][app.services.audit.log_event] (async) or [`log_event_sync`][app.services.audit.log_event_sync] (sync, used inside Celery tasks).

| `event_type` | Triggered by |
|--------------|--------------|
| `owner_registered` | First Plex SSO login |
| `login`, `logout`, `login_rejected` | Plex SSO events |
| `plex_target_configured` | Plex setup wizard completion |
| `sync.started` | Worker begins `sync_playlists_task` |
| `sync.completed` | Worker finishes successfully |
| `sync.failed` | Worker raises |
| `sync.manually_triggered` | User clicks **Run now** in the UI |
| `sync.bulk_triggered` | Bulk "sync now" from the Schedules page |
| `track.matched` | Per-track match inside the legacy matcher |
| `settings.updated` | PUT `/api/v1/settings/` |
| `schedule.created` / `schedule.updated` / `schedule.deleted` | Schedule CRUD |
| `schedule.bulk_updated` / `schedule.bulk_deleted` | Bulk schedule operations |
| `scheduler.reloaded` | `POST /api/v1/schedules/scheduler/reload` |
| `match_rule.created` / `match_rule.cloned` / `match_rule.reordered` / `match_rule.updated` / `match_rule.deleted` | Match rule CRUD |

View via the **Audit log** page in the UI, or query the table directly:

```bash
docker compose exec postgres psql -U ampy3 ampy3 -c \
  "SELECT event_type, summary, created_at FROM audit_log ORDER BY created_at DESC LIMIT 20;"
```

The audit log is **append-only**. Plan a retention policy in [Backup & restore](backup-restore.md).

## Scheduler

[`SchedulerService`][app.services.scheduler.SchedulerService] is an APScheduler instance that runs *in the API process*. It reads scheduled syncs from the DB and enqueues Celery tasks when their interval fires.

- Schedule intervals are defined in [`src/app/constants.py`](https://github.com/JakePeralta7/Ampy3/blob/main/src/app/constants.py) (`INTERVAL_DELTAS`): `every_6h`, `every_12h`, `every_24h`, `daily`, `weekly`. A scheduled sync with no interval ("manual") never fires automatically.
- A scheduled sync missing its trigger is skipped, not queued late.
- Restarting the API re-loads schedules from the DB on startup — no manual resync needed.

Inspect:

```bash
docker compose logs web | grep -i scheduler
docker compose logs web | grep -i 'apscheduler'
```

## Celery broker

Valkey doubles as the Celery broker. Inspect queue depth:

```bash
docker compose exec valkey redis-cli LLEN celery
docker compose exec valkey redis-cli KEYS '*' | head
```

Inspect active workers and tasks:

```bash
docker compose exec worker celery -A app.worker.app inspect active
docker compose exec worker celery -A app.worker.app inspect scheduled
docker compose exec worker celery -A app.worker.app inspect reserved
```

Cancel a stuck task:

```bash
docker compose exec worker celery -A app.worker.app control revoke <task_id> --terminate
```

## Valkey cache

Source playlist fetches are cached for `SOURCE_PLAYLIST_CACHE_TTL_SECONDS` (default 300s) — see [`get_valkey_client`][app.services.get_valkey_client]. Clear if you've changed a playlist on the source and want a fresh fetch *now*:

```bash
docker compose exec valkey redis-cli FLUSHDB
```

!!! warning "FLUSHDB clears the Celery broker too"
    Both the broker and the cache share the same Valkey instance. Prefer per-key deletion (`DEL <key>`) over `FLUSHDB` in production.

## Postgres

```bash
docker compose exec postgres psql -U ampy3 ampy3 -c "\dt"      # list tables
docker compose exec postgres psql -U ampy3 ampy3 -c "\di"      # list indexes
docker compose exec postgres psql -U ampy3 ampy3 -c "SELECT version();"
```

Largest tables (often candidates for archival):

```sql
SELECT relname, pg_size_pretty(pg_total_relation_size(relid))
FROM pg_catalog.pg_statio_user_tables
ORDER BY pg_total_relation_size(relid) DESC
LIMIT 10;
```

## Healthchecks from the API

The web container exposes `/health` (basic liveness) and the standard FastAPI `/docs` (Swagger UI) at `http://localhost:8000/docs`. Use `/docs` to poke at any route by hand without going through the React UI.

## Where to look next

- [Docker](docker.md) — service topology and ops commands
- [Backup & restore](backup-restore.md) — protect the data you just learned how to query
- [`app.services`][app.services] — lazy singletons used by both API and worker