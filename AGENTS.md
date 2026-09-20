# AGENTS.md

## What this is

Ampy3 syncs YouTube Music playlists to Plex/Jellyfin using MusicBrainz IDs for metadata matching. Python/FastAPI backend + React/TypeScript frontend, orchestrated via Docker Compose with Celery workers and Valkey (Redis-compatible).

## Project layout

```
src/                  # Python backend (FastAPI + Celery)
  main.py             # App entrypoint, lifespan, production auth gates, SPA serving
  app/
    api/              # FastAPI route handlers (registered via register_routers)
    auth/             # Plex SSO authentication (tokens, session middleware)
    core/             # Domain logic: clients/, targets/, sources/, providers/, matching, explore/
    match_rules/      # YAML-based match rule schema, parser, loader, defaults/
    models.py         # ORM models (SQLAlchemy 2.0 mapped_column style)
    schemas/          # Pydantic request/response schemas
    services/         # Service layer with lazy singletons (crypto, config_fingerprint inside)
    worker/           # Celery worker: tasks, pipeline, matcher, context, session
    db.py             # SQLAlchemy engines (async for FastAPI, sync for Celery), init_db
    settings.py       # Pydantic BaseSettings — all config from env vars
    constants.py      # Platform IDs, SENSITIVE_CONFIG_KEYS, interval mapping
web/                  # React SPA (Vite + Tailwind + Biome)
  src/
    features/<domain>/  # Feature components grouped by domain: explore/, playlists/, rules/
    hooks/              # Custom hooks, one per API domain (usePlaylistDetails, useSyncHistory, ...)
    api/<resource>/     # API clients, one folder per backend resource + client.ts HTTP wrapper
    components/
      ui/               # Design-system primitives (Button, Modal, FormField, SourceIcon, ...)
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
# Lint/format from repo root (CI lints src/ only; local checks also cover tests/)
ruff check src/ tests/
ruff format --check src/ tests/
ruff format src/ tests/

# Run all tests (PYTHONPATH=src is required)
PYTHONPATH=src pytest

# Start locally without Docker (PYTHONPATH=src; skips the production gate only
# because the APP_ENV env var is unset — see Gotchas)
PYTHONPATH=src uvicorn main:app --host 0.0.0.0 --port 8000
```

### Frontend (web/)

```bash
cd web
pnpm install --frozen-lockfile
pnpm run lint        # Biome check
pnpm run format      # Biome format --write
pnpm run build       # tsc && vite build
pnpm run dev         # Vite dev server on :5173 (proxies /api to :8000)
```

### Docker

```bash
docker compose up --build                # Full stack: web, worker, valkey, postgres
# Dev overlay: hot-reload backend + Vite on :5173, sets APP_ENV=development
docker compose -f docker-compose.yml -f docker-compose.dev.yml up
```

Motd: the overlay builds `web` from the `base` target with uvicorn `--reload` and adds a `frontend` service that runs Vite inside the container.

### Version bump & release

```bash
python bump_version.py 0.2.0     # Set an explicit version (X.Y.Z)
python bump_version.py patch     # Increment major | minor | patch
python bump_version.py check     # Verify all locations agree; edit nothing
```

The app version is defined in exactly three places (`pyproject.toml`, `src/app/__init__.py`, `web/package.json`) and must stay in sync. `pyproject.toml` is the source of truth; always use this script instead of editing them by hand. The MusicBrainz user-agent derives from `src.app.__version__` — do not hardcode it anywhere.

Releasing = commit the bump, tag `vX.Y.Z`, push both: pushing a `v*` tag triggers `.github/workflows/release.yml`, which builds and pushes the `ghcr.io/jakeperalta7/ampy3-web`/`-worker` images (also refreshed to `latest` on main pushes) and creates a GitHub Release. External deployments (the `IaC/Ampy3` Forgejo repo) consume those images — this repo does not hold the deployment env.

### Database migrations

```bash
python migrate.py bootstrap  # Create/stamp fresh DB, or upgrade existing
python migrate.py upgrade    # Apply pending Alembic migrations
python migrate.py autogen    # Generate migration from model changes
python migrate.py status     # Show current revision
```

Alembic migrations run automatically at API startup via `src/app/db.py:init_db()`: fresh databases are created from ORM metadata and stamped at head; existing (alembic-managed) databases run `upgrade`. Never run `create_all` against an existing database.

## Key architecture notes

- **PYTHONPATH must include `src/`**. The Dockerfile sets `PYTHONPATH=/app/src`. Locally, always prefix commands with `PYTHONPATH=src` when running from repo root.
- **Dual database engines**: Async (`asyncpg`) for FastAPI routes, sync (`psycopg2`) for Celery workers. Both in `src/app/db.py`. Never mix session factories.
- **Service container**: `src/app/services/__init__.py` provides lazy singletons via `get_celery_app()`, `get_valkey_client()`, `get_ytmusic_client()`, `get_deezer_client()`, `get_sync_target()`, plus `reset_services()` (call in tests). Use these instead of creating clients directly.
- **Target registry**: Sync targets (Plex, Jellyfin) register via `@register_target` in `src/app/core/targets/` and are cached with a config fingerprint (see Gotchas). `get_sync_target("Plex")` returns an instance; a `config` table write invalidates cached instances.
- **Source registry**: Music sources (YouTube Music, Deezer) register in `src/app/core/sources/`.
- **Shared source clients**: `src/app/core/clients/` holds one cached client per platform (`YouTubeMusicClient`, `DeezerClient`) used by **both** the sync sources and the Explore providers. Caching lives inside the client — Valkey keys `{source}:{method}:{...}`; playlist fetches use `SOURCE_PLAYLIST_CACHE_TTL_SECONDS`, Explore content `EXPLORE_CACHE_TTL_SECONDS`. YT home keys are annotated with a session fingerprint, so a re-auth never serves the previous session's personalised feed.
- **Secrets at rest**: sensitive `config` keys (`plex_token`, `jellyfin_api_key`, `ytmusic_auth`, `owner_plex_token`) are Fernet-encrypted. Read them via `decrypt_token()` in `src/app/services/crypto.py`; never treat stored ciphertext as a token. Encrypted values are never returned to the UI — only `*_set` booleans.
- **Settings**: All config is in `src/app/settings.py` as a Pydantic `BaseSettings` singleton. Env vars are the source of truth; `.env.example` documents them (compose also auto-interpolates a repo `.env`, and pydantic-settings loads a CWD `.env` when running locally). User-editable settings (`plex_host`, `plex_token`, `ytmusic_auth`, `yt_dlp_timeout`, …) persist in the `config` table and merge over env defaults via `settings.load_overrides()`.
- **CORS**: When `REQUIRE_AUTH=true`, only `APP_URL` is allowed. Otherwise `*` (no credentials).
- **Docs site**: MkDocs + Material + mkdocstrings under `docs/` (built to `site/`, wired via `.readthedocs.yaml`). `dev` building needs the `docs` extra (`pip install -e ".[docs]"` then `mkdocs serve`). `docs/development/architecture.md` has deeper backend context than this file.
- **SPA serving**: `src/main.py` mounts `web/dist/` as static and serves `index.html` for non-API routes. Build the frontend before running the API if you want the UI.
- **Frontend dev server**: Vite on `:5173` proxies `/api` to `:8000`. No API key or auth needed in dev.
- **pnpm only**: The frontend uses pnpm (`packageManager` pinned in `web/package.json`, consumed by Corepack/CI). Do not add `package-lock.json` — it is git-ignored; install with `pnpm install --frozen-lockfile`.
- **Logging**: JSON-lines by default (`LOG_FORMAT=json`, `python-json-logger`) — logs appear as single-line JSON in `docker compose logs`. Set `LOG_FORMAT=console` for human-readable output.
- **pytest asyncio_mode**: Set to `"auto"` in `pyproject.toml` — no need for `@pytest.mark.asyncio`.
- **No conftest.py**: Tests rely on individual monkeypatching; there's no shared test fixture file.

## Lint / format config

- **Python**: Ruff (`pyproject.toml`). Line length 100. Target py314. Ruff selects: E, F, I, N, W, UP, B, SIM. Ignores `F401`.
- **Frontend**: Biome (`web/biome.json`). Space indent, line width 100. Recommended preset with several a11y rules disabled.
- **TypeScript type check**: `npx tsc --noEmit` in `web/` (CI runs this separately from Biome; `pnpm run build` runs it first).
- **mypy**: Strict config exists (`pyproject.toml`) for editor use only — CI does not run it.
- **No pre-commit hooks** in this repo.

## Gotchas

- **Fail-closed startup**: the app refuses to start when `APP_ENV=production` (the *env var*, checked in `main.py`'s lifespan) or `REQUIRE_AUTH=true` without a `SECRET_KEY` of ≥32 chars — never fall back to disabling auth. `SECRET_KEY` keys both session signing and at-rest token encryption. The `Dockerfile` bakes `ENV APP_ENV=production` (Dockerfile:61), so any standalone container run already hits this gate; the dev overlay overrides it with `APP_ENV=development`. Bare local runs (env var unset) skip the gate even though `settings.app_env` defaults to `"production"`.
- **`DATABASE_URL` is configured directly** (compose interpolates `POSTGRES_PASSWORD` into it inline; `settings.database_url` reads the env var). Keep `POSTGRES_PASSWORD` to letters, digits, `-`, `_` — URL-reserved characters (`/`, `?`, `@`) silently break the connection. The `alembic.ini` placeholder URL is overridden at runtime — never edit it directly. Compose requires `POSTGRES_PASSWORD` (env or `.env`); the postgres port is not published to the host.
- **Token decryption fails loudly**: `decrypt_token` raises `DecryptionError` for non-Fernet or foreign-key material — e.g. after rotating `SECRET_KEY` or running with config written by a different key. Never migrate stored values to plaintext; re-encrypt them under the current key instead.
- **`put_settings` no-churn**: Fernet is non-deterministic, so `api/settings.py` skips re-encrypting an unchanged plaintext token. Writing any config row changes the **config fingerprint** (`config_fingerprint.py` — SHA-256 over the whole `config` table), which invalidates cached target instances; gratuitous writes churn targets.
- **YouTube Music authentication** is configured entirely through the **Sources** settings page. The pasted ytmusicapi browser/auth JSON is stored encrypted in the `config` table under `ytmusic_auth` (never returned to the UI — only `ytmusic_auth_set` is). No `cookies/` mount or `YT_DLP_COOKIES` env is used anymore; the YouTube Music source and Explore provider both consume it via `src/app/services/ytauth.py`, which normalises it into the flat headers dict `ytmusicapi` expects (no temp file on disk).
- Containers run as the non-root `appuser` (see `Dockerfile`). The dev overlay (`docker-compose.dev.yml`) overrides `user: "0:0"` so hot-reload can write bytecode.
- Python 3.14 (PEP 758) allows `except A, B:` without parens; ruff targets py314 so it strips the "redundant" parens — don't re-add them or `ruff format --check` fails.
- Celery workers use the **sync** SQLAlchemy engine; the API uses async. Do not mix session factories.
- `F401` (unused imports) is intentionally ignored in Ruff config.
- CI runs `ruff format --check` (not just `ruff check`) — ensure code is formatted before pushing. CI tests use `|| test $? -eq 5` to tolerate pytest exit code 5 (no tests collected).