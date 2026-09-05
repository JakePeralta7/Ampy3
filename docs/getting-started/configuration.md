# Configuration

All Ampy3 configuration is read from **environment variables**. There are no `.env` template files — env vars are the single source of truth, consumed by the Pydantic `Settings` singleton in `src/app/settings.py`.

## Quick reference

| Variable | Default | Description |
|----------|---------|-------------|
| `POSTGRES_PASSWORD` | _(required in Docker)_ | Postgres password for the Compose stack. `docker compose` fails to start if unset. It becomes part of the database DSN verbatim, so stick to letters, digits, `-` and `_` (URL-reserved chars like `/` would break the connection). |
| `CELERY_BROKER_URL` | `redis://valkey:6379/0` | Celery broker (Valkey/Redis). |
| `CELERY_RESULT_BACKEND` | `redis://valkey:6379/1` | Celery result backend. |
| `CELERY_WORKER_CONCURRENCY` | `1` | Worker prefork count. ≥1. |
| `CELERY_LOG_LEVEL` | `info` | Celery log level. |
| `SOURCE_PLAYLIST_CACHE_TTL_SECONDS` | `300` | TTL for cached source playlist fetches. ≥1. |
| `YT_DLP_COOKIES` | _(empty)_ | Path to a Netscape-format `cookies.txt`. Defaults to `/app/cookies/cookies.txt` inside the container. |
| `YT_DLP_TIMEOUT` | `300` | Per-request `yt-dlp` timeout in seconds. |
| `REQUIRE_AUTH` | `false` | When `true`, only `APP_URL` is allowed by CORS and Plex SSO is enforced. |
| `PLEX_CLIENT_ID` | _(empty)_ | OAuth client identifier for Plex SSO (only used when `REQUIRE_AUTH=true`). |
| `APP_URL` | `http://localhost:8000` | Public URL used for OAuth redirects and CORS. |
| `SECRET_KEY` | _(empty)_ | Session-signing key. **Required when `REQUIRE_AUTH=true`** — the app refuses to start otherwise (fail-closed). Generate with `openssl rand -hex 32`. |
| `SESSION_TTL_HOURS` | `168` | Session lifetime in hours (default = 1 week). |
| `APP_ENV` | `development` | Free-form env label, surfaced in logs. |
| `DEBUG` | `false` | Enable verbose error pages. |

## Section: Database

In Docker, the PostgreSQL DSN is built automatically from `POSTGRES_PASSWORD` — no extra configuration needed. Two SQLAlchemy engines are created from it:

- **Async** (`asyncpg`) — used by FastAPI request handlers
- **Sync** (`psycopg2-binary`) — used by Celery workers

When running locally (no Docker), the default DSN `postgresql://ampy3:ampy3@localhost:5432/ampy3` applies; see [Local setup](../development/local-setup.md).

!!! danger "Don't mix session factories"
    FastAPI routes get an `AsyncSession` via the `get_async_session()` dependency in [`src/app/db.py`][app.db]. Celery tasks get a `Session` via [`session_scope`][app.worker.session.session_scope] (or `get_sync_session()`). Using an async session inside a Celery task will deadlock; using a sync session inside an async route will block the event loop.

## Section: Celery / Valkey

Valkey is a Redis-compatible broker. The Compose stack runs Valkey on a private network; you only need to override these if you point Ampy3 at an external broker.

```bash
CELERY_BROKER_URL=redis://valkey.internal:6379/0
CELERY_RESULT_BACKEND=redis://valkey.internal:6379/1
CELERY_WORKER_CONCURRENCY=2          # tune based on CPU + Plex/Jellyfin rate limits
CELERY_LOG_LEVEL=info                # debug for verbose task logs
SOURCE_PLAYLIST_CACHE_TTL_SECONDS=900
```

## Section: yt-dlp

`yt-dlp` is the workhorse for fetching YouTube Music (and other) playlists.

```bash
YT_DLP_COOKIES=/etc/ampy3/cookies.txt
YT_DLP_TIMEOUT=600
```

If `YT_DLP_COOKIES` is unset, the API and worker default to `/app/cookies/cookies.txt` — the path mounted from the host's `cookies/` directory (see [Installation → YouTube Music cookies](installation.md#youtube-music-cookies)).

## Section: Auth (Plex SSO)

When `REQUIRE_AUTH=true`:

- CORS is restricted to `APP_URL` (instead of `*`)
- The web UI redirects unauthenticated users to a Plex SSO flow handled by `src/app/auth/`
- Sessions are signed with `SECRET_KEY`

```bash
REQUIRE_AUTH=true
PLEX_CLIENT_ID=ampy3-docs-example
APP_URL=https://ampy3.example.com
SECRET_KEY=$(openssl rand -hex 32)
SESSION_TTL_HOURS=72
```

!!! warning "`SECRET_KEY` is required when `REQUIRE_AUTH=true`"
    An empty `SECRET_KEY` with auth enabled will refuse to start sessions. Generate a fresh one per deployment and never commit it.

See [Auth](../guides/auth.md) for the full flow.

## Section: App

```bash
APP_ENV=production
DEBUG=false
```

`DEBUG=true` enables verbose error responses from FastAPI — useful in development, **never** in production.

## Local development overrides

There is no `tests/conftest.py` in this repo — each test sets the env vars it needs directly (see [`tests/test_db_initialization.py`](https://github.com/JakePeralta7/Ampy3/blob/main/tests/test_db_initialization.py) for the pattern). When running locally without Docker, export at least these before launching Uvicorn / Celery:

```bash
export CELERY_BROKER_URL=redis://localhost:6379/0
export CELERY_RESULT_BACKEND=redis://localhost:6379/1
```

See [Local setup](../development/local-setup.md) for the full dev workflow.