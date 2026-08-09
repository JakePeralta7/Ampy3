# Architecture

Ampy3 is a fairly conventional FastAPI + Celery stack, but a few opinionated choices are worth understanding before you start hacking.

## Repo layout

```
src/                       # Python backend (FastAPI + Celery)
  main.py                  # App entrypoint, lifespan, SPA serving
  app/
    api/                   # Route handlers, registered via register_routers
    services/              # Service layer with lazy singletons
    core/                  # Domain code: matching, sources, targets, nodes, explore
    auth/                  # Plex SSO + session middleware
    worker/                # Celery tasks, SyncPipeline, phases
    db.py                  # SQLAlchemy engines (async + sync)
    settings.py            # Pydantic BaseSettings — env-var config
    models.py              # ORM models (SQLAlchemy 2.0)
    schemas/               # Pydantic request/response schemas
alembic/                   # Database migrations
web/                       # React SPA (Vite + Tailwind + Biome)
tests/                     # Pytest
```

## Dual database engines

`src/app/db.py` creates **two** SQLAlchemy engines from the same `DATABASE_URL`:

| Engine | Driver | Used by | Session factory |
|--------|--------|---------|-----------------|
| `async_engine` | `asyncpg` | FastAPI routes, lifespan, scheduler | `AsyncSessionLocal()` |
| `sync_engine` | `psycopg2-binary` | Celery tasks | `SessionLocal()` |

Mixing the two is the most common bug — an async session inside a Celery task will deadlock; a sync session inside an async route will block the event loop. If you're not sure, ask: *am I in a request handler or a Celery task?*

## ServiceContainer (lazy singletons)

`src/app/services/__init__.py` provides a small dependency-injection layer. Instead of creating clients at import time, you call factories:

```python
from src.app.services import get_celery_app, get_valkey_client, get_sync_target

celery_app = get_celery_app()         # returns CeleryService.get_instance()
valkey     = get_valkey_client()      # returns ValkeyService.get_instance()
target     = await get_sync_target()  # TargetService — async because construction is
```

Each service subclasses [`ServiceBase`][app.services.base.ServiceBase] and exposes `get_instance()` / `reset()`. `reset()` is used in tests to drop state between cases.

## Lifespan

`src/main.py` defines an async `@asynccontextmanager` lifespan that runs on startup/shutdown:

1. Falls back to no-auth if `REQUIRE_AUTH=true` but `SECRET_KEY` is empty
2. Calls `init_db()` — creates schema or runs Alembic upgrades (see [Migrations](#migrations))
3. Purges expired sessions
4. Initialises the Plex client (sections probe)
5. Starts APScheduler

Failure of any individual step is logged but **does not crash the API** — Ampy3 stays up in a degraded state rather than refusing to serve requests.

## SPA serving

When `web/dist/` exists, FastAPI:

- Mounts `/assets` from `web/dist/assets/` (cacheable long-term)
- Falls through to `web/dist/index.html` for every non-`/api/*` path
- Bypasses this for `/api/*` so 404s there go through the JSON handler

This means you can deploy Ampy3 behind a single reverse proxy — no separate static-file server.

## CORS

`main.py` configures `CORSMiddleware`:

- When `REQUIRE_AUTH=true`: only `APP_URL` is allowed
- When `REQUIRE_AUTH=false`: `*`

The React frontend proxies `/api` to the backend during development (`pnpm run dev` → Vite on `:5173` → `:8000`), so CORS doesn't bite there. In production both run from the same origin.

## Migrations

Alembic is configured in `alembic/alembic.ini` — but the `sqlalchemy.url` placeholder is overridden at runtime from `settings.database_url`. **Do not edit the ini's URL.**

The bootstrap logic in `init_db()`:

1. If the DB is **not** Alembic-managed → `Base.metadata.create_all()` + `alembic stamp head`
2. If it **is** Alembic-managed → `alembic upgrade head`

In a development environment you usually want `python migrate.py bootstrap` (creates + stamps) or `python migrate.py upgrade` (applies pending).

## AsyncCelery

The Celery worker uses `app.worker.tasks` with the **sync** SQLAlchemy session inside. Async is bridged via `app.worker.session.run_async` for cases where an underlying library (e.g. `ytmusicapi`) requires it.

## Match-rule DSL

Match rules are a tiny DAG stored in the `MatchRule` table. The DAG is a dict-of-nodes + list-of-edges, executed by [`NodeGraphExecutor`][app.core.services.matcher.NodeGraphExecutor] in topological order. See [Metadata matching → Match-rule YAML](../guides/metadata-matching.md#match-rule-yaml) for the schema.

## Where to look next

- [Sync pipeline](../guides/sync-pipeline.md)
- [Sources and targets](../guides/sources-and-targets.md)
- [Reference → Services](../reference/services.md) — lazy singletons in detail