# AGENTS.md

## What this is

Ampy3 syncs YouTube Music playlists to Plex, using MusicBrainz IDs for metadata matching. Python/FastAPI backend + React/TypeScript frontend, orchestrated via Docker Compose with Celery workers and Valkey (Redis-compatible).

## Project layout

```
src/                  # Python backend (FastAPI + Celery)
  main.py             # App entrypoint, lifespan, SPA serving
  app/
    api/              # Route handlers (registered via register_routers)
    services/         # Service layer with lazy singletons (ServiceContainer)
    amp/              # Music sync domain (orchestrator, Plex client, YTMusic source)
    tasks.py          # Celery task definitions
    db.py             # SQLAlchemy engines (async for FastAPI, sync for Celery)
    settings.py       # Pydantic BaseSettings — all config from env vars
    models.py         # ORM models (SQLAlchemy 2.0 mapped_column style)
web/                  # React SPA (Vite + Tailwind + Biome)
alembic/              # Database migrations (PostgreSQL)
tests/                # Pytest tests
```

## Commands

### Backend (Python)

```bash
# Format
black src/ tests/ alembic/ migrate.py

# Lint
ruff check src/ tests/

# Run all tests
pytest

# Start locally without Docker (from repo root)
uvicorn main:app --host 0.0.0.0 --port 8000
# Requires PYTHONPATH=/app/src (already set in Dockerfile)
```

### Frontend (web/)

```bash
cd web
pnpm install
pnpm run lint        # Biome check
pnpm run format      # Biome format --write
pnpm run build       # tsc && vite build
pnpm run dev         # Vite dev server on :5173 (proxies /api to :8000)
```

### Docker

```bash
docker compose up --build    # Full stack: api, worker, web, valkey, postgres
```

### Database migrations

```bash
python migrate.py upgrade    # Apply pending Alembic migrations
python migrate.py reset      # Reset to initial migration, reapply
python migrate.py status     # Show current revision
```

Alembic migrations run automatically at API startup via `src/app/db.py:init_db()`. The alembic config lives at `alembic/alembic.ini`; the URL is overridden at runtime from `settings.database_url`.

## Key architecture notes

- **PYTHONPATH must include `src/`**. The Dockerfile sets `PYTHONPATH=/app/src`. Locally, run commands from repo root or set this explicitly.
- **Dual database engines**: Async (`asyncpg`) for FastAPI routes, sync (`psycopg2`) for Celery workers. Both in `src/app/db.py`.
- **Service container**: `src/app/services/__init__.py` provides lazy singletons via `get_celery_app()`, `get_valkey_client()`, etc. Use these instead of creating clients directly.
- **Settings**: All config is in `src/app/settings.py` as a Pydantic `BaseSettings` singleton. No `.env` template files — env vars are the source of truth.
- **CORS**: When `REQUIRE_AUTH=true`, only `APP_URL` is allowed. Otherwise `*`.
- **SPA serving**: `src/main.py` mounts `web/dist/` as static and serves `index.html` for non-API routes. Build the frontend before running the API if you want the UI.
- **Frontend dev server**: Vite on `:5173` proxies `/api` to `:8000`. No API key or auth needed in dev.
- **pytest asyncio_mode**: Set to `"auto"` in `pyproject.toml` — no need for `@pytest.mark.asyncio`.
- **conftest.py**: Sets default env vars (`PLEX_HOST`, `PLEX_TOKEN`, etc.) before imports so the app doesn't crash on missing config.

## Lint / format config

- **Python**: Black + Ruff (`pyproject.toml`). Line length 100. Target py314. Ruff selects: E, F, I, N, W, UP, B, SIM. Ignores `F401`.
- **Frontend**: Biome (`web/biome.json`). Space indent, line width 100. Recommended preset with several a11y rules disabled.
- **No pre-commit hooks or CI config** in this repo.

## Gotchas

- The `cookies/` directory is mounted read-only into containers for `yt-dlp` cookie auth. It must exist or the volume mount fails.
- Celery workers use the **sync** SQLAlchemy engine; the API uses async. Do not mix session factories.
- The `alembic.ini` placeholder URL (`driver://user:password@localhost/dbname`) is overridden at runtime — never edit it directly.
- `F401` (unused imports) is intentionally ignored in Ruff config.
