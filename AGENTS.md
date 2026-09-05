# AGENTS.md

## What this is

Ampy3 syncs YouTube Music playlists to Plex/Jellyfin using MusicBrainz IDs for metadata matching. Python/FastAPI backend + React/TypeScript frontend, orchestrated via Docker Compose with Celery workers and Valkey (Redis-compatible).

## Project layout

```
src/                  # Python backend (FastAPI + Celery)
  main.py             # App entrypoint, lifespan, SPA serving
  app/
    api/              # FastAPI route handlers (registered via register_routers)
    auth/             # Plex SSO authentication (tokens, session middleware)
    core/             # Domain logic: targets/, sources/, providers/, matching, explore/
    match_rules/      # YAML-based match rule schema, parser, loader, defaults/
    models.py         # ORM models (SQLAlchemy 2.0 mapped_column style)
    schemas/          # Pydantic request/response schemas
    services/         # Service layer with lazy singletons (ServiceContainer)
    worker/           # Celery worker: tasks, pipeline, matcher, context, session
    db.py             # SQLAlchemy engines (async for FastAPI, sync for Celery)
    settings.py       # Pydantic BaseSettings — all config from env vars
    constants.py      # Platform IDs and shared constants
web/                  # React SPA (Vite + Tailwind + Biome)
  src/
    features/<domain>/  # Feature components grouped by domain: explore/, playlists/, rules/
    hooks/              # Custom hooks, one per API domain (usePlaylistDetails, useSyncHistory, ...)
    api/<resource>/     # API clients, one folder per backend resource + client.ts HTTP wrapper
    components/
      ui/               # Design-system primitives (Button, Modal, FormField, ...)
      layout/           # AppLayout, PageLayout, Nav
      auth/             # Route guards (ProtectedRoute, RequireServer)
    lib/                # Shared utils/constants/styles (formatTimestamp, getErrorMessage, ...)
    pages/              # Top-level route components
alembic/              # Database migrations (PostgreSQL)
tests/                # Pytest tests
docs/                 # MkDocs site (Material + mkdocstrings), published on Read the Docs
```

## Commands

### Backend (Python)

```bash
# Lint (CI runs ruff check + ruff format --check)
ruff check src/ tests/
ruff format --check src/ tests/

# Format
ruff format src/ tests/

# Run all tests (PYTHONPATH=src is required)
PYTHONPATH=src pytest

# Start locally without Docker (from repo root)
PYTHONPATH=src uvicorn main:app --host 0.0.0.0 --port 8000
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
python migrate.py bootstrap  # Create/stamp fresh DB, or upgrade existing
python migrate.py upgrade    # Apply pending Alembic migrations
python migrate.py autogen    # Generate migration from model changes
python migrate.py status     # Show current revision
```

Alembic migrations run automatically at API startup via `src/app/db.py:init_db()`. The alembic config lives at `alembic/alembic.ini`; the URL is overridden at runtime from `settings.database_url`.

## Key architecture notes

- **PYTHONPATH must include `src/`**. The Dockerfile sets `PYTHONPATH=/app/src`. Locally, always prefix commands with `PYTHONPATH=src` when running from repo root.
- **Dual database engines**: Async (`asyncpg`) for FastAPI routes, sync (`psycopg2`) for Celery workers. Both in `src/app/db.py`. Never mix session factories.
- **Service container**: `src/app/services/__init__.py` provides lazy singletons via `get_celery_app()`, `get_valkey_client()`, `get_sync_target()`, etc. Use these instead of creating clients directly.
- **Target registry**: Sync targets (Plex, Jellyfin) register via `@register_target` in `src/app/core/targets/`. Use `get_sync_target("Plex")` to obtain an instance.
- **Source registry**: Music sources (YouTube Music, Deezer) register in `src/app/core/sources/`.
- **Settings**: All config is in `src/app/settings.py` as a Pydantic `BaseSettings` singleton. No `.env` template files — env vars are the source of truth. See `.env.example` for reference.
- **CORS**: When `REQUIRE_AUTH=true`, only `APP_URL` is allowed. Otherwise `*`.
- **Docs site**: MkDocs + Material + mkdocstrings under `docs/` (built to `site/`, wired via `.readthedocs.yaml`). `dev` building needs the `docs` extra (`pip install -e ".[docs]"` then `mkdocs serve`). `docs/development/architecture.md` has deeper backend context than this file.
- **SPA serving**: `src/main.py` mounts `web/dist/` as static and serves `index.html` for non-API routes. Build the frontend before running the API if you want the UI.
- **Frontend dev server**: Vite on `:5173` proxies `/api` to `:8000`. No API key or auth needed in dev.
- **pnpm only**: The frontend uses pnpm (`packageManager` pinned in `web/package.json`, consumed by Corepack/CI). Do not add `package-lock.json` — it is git-ignored; install with `pnpm install --frozen-lockfile`.
- **pytest asyncio_mode**: Set to `"auto"` in `pyproject.toml` — no need for `@pytest.mark.asyncio`.
- **No conftest.py**: Tests rely on individual monkeypatching; there's no shared test fixture file.

## Lint / format config

- **Python**: Ruff (`pyproject.toml`). Line length 100. Target py314. Ruff selects: E, F, I, N, W, UP, B, SIM. Ignores `F401`.
- **Frontend**: Biome (`web/biome.json`). Space indent, line width 100. Recommended preset with several a11y rules disabled.
- **TypeScript type check**: `npx tsc --noEmit` in `web/` (CI runs this separately from Biome).
- **No pre-commit hooks** in this repo.

## Gotchas

- The `cookies/` directory is mounted read-only into containers for `yt-dlp` cookie auth. It must exist or the volume mount fails. On Linux hosts, the container runs as the non-root `appuser` (uid 999), so the directory needs read/traverse permission for that uid (`chmod 755 cookies/`) or yt-dlp gets unusable cookies.
- **`POSTGRES_PASSWORD` charset**: `docker compose` requires `POSTGRES_PASSWORD` (set via env or `.env`). It becomes part of the database DSN verbatim (the DSN is always derived — never configure it directly). Keep it to letters, digits, `-`, `_` — URL-reserved characters (`/`, `?`, `@`) silently break the connection. The postgres port is no longer published to the host.
- **Auth is fail-closed**: `REQUIRE_AUTH=true` without a `SECRET_KEY` (≥32 chars) makes the app refuse to start — never fall back to disabling auth. `SECRET_KEY` under 32 characters is rejected in `settings.py`.
- **`docker compose` requires `POSTGRES_PASSWORD`** (set via env or `.env`); the postgres port is no longer published to the host.
- Containers run as the non-root `appuser` (see `Dockerfile`). The dev overlay (`docker-compose.dev.yml`) overrides `user: "0:0"` so hot-reload can write bytecode.
- Python 3.14 (PEP 758) allows `except A, B:` without parens; ruff targets py314 so it strips the "redundant" parens — don't re-add them or `ruff format --check` fails.
- Celery workers use the **sync** SQLAlchemy engine; the API uses async. Do not mix session factories.
- The `alembic.ini` placeholder URL (`driver://user:password@localhost/dbname`) is overridden at runtime — never edit it directly.
- `F401` (unused imports) is intentionally ignored in Ruff config.
- CI runs `ruff format --check` (not just `ruff check`) — ensure code is formatted before pushing.
- CI tests use `|| test $? -eq 5` to tolerate pytest exit code 5 (no tests collected).
