# Configuration

Ampy3 has two categories of configuration:

1. **Deployment environment variables** (required at container startup) — only `DATABASE_USERNAME`, `DATABASE_PASSWORD`, and `APP_URL`.
2. **Runtime configuration** (managed via the web UI, stored in the database) — security settings, target credentials, YouTube Music auth, and network/proxy settings.

On first boot, the setup wizard walks you through initial security configuration. Subsequent changes are made in the **Settings** pages (Sources, Targets, Network).

## Quick reference: Deployment env vars

| Variable | Required | Description |
|----------|----------|-------------|
| `DATABASE_USERNAME` | **Yes** | Postgres username. |
| `DATABASE_PASSWORD` | **Yes** | Postgres password. |
| `APP_URL` | **Yes** | Public URL used for OAuth redirects and CORS. |
| `APP_BIND` | No | Host bind for the API (`127.0.0.1` by default; use `0.0.0.0` for LAN access). |
| `APP_PORT` | No | Container port (default `8000`). |
| `APP_ENV` | No | Environment label (`production` or `development`). Default: `production`. |

## Quick reference: Celery / Valkey (override if using external broker)

| Variable | Default | Description |
|----------|---------|-------------|
| `CELERY_BROKER_URL` | `redis://valkey:6379/0` | Celery broker (Valkey/Redis). |
| `CELERY_RESULT_BACKEND` | `redis://valkey:6379/1` | Celery result backend. |
| `CELERY_WORKER_CONCURRENCY` | `1` | Worker prefork count. ≥1. |
| `CELERY_LOG_LEVEL` | `info` | Worker log level (`debug`/`info`/`warning`/`error`/`critical`). |
| `LOG_FORMAT` | `json` | Log output format, `json` (python-json-logger) or `console`. |
| `SOURCE_PLAYLIST_CACHE_TTL_SECONDS` | `300` | TTL for cached source playlist fetches (syncs). ≥1. |
| `EXPLORE_CACHE_TTL_SECONDS` | `900` | TTL for cached Explore content (home, moods, search). ≥1. |
| `YT_DLP_TIMEOUT` | `300` | Per-request YouTube Music fetch timeout in seconds. |

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
EXPLORE_CACHE_TTL_SECONDS=1800
```

## Section: YouTube Music

YouTube Music playlists are fetched with the `ytmusicapi` library. Authentication (optional) is configured through the **Settings → Sources** page in the web UI: paste the ytmusicapi browser/auth JSON there and it is stored in the app database — no file mounts or cookie env vars.

`YT_DLP_TIMEOUT` sets the per-request fetch timeout:

```bash
YT_DLP_TIMEOUT=600
```

## Section: Auth (Plex SSO)

Plex SSO is configured via the setup wizard on first boot. When authentication is enabled, CORS is restricted to `APP_URL` and the web UI redirects unauthenticated users to a Plex SSO flow. Sessions are signed with a key stored in the database.

To change authentication settings after setup, use the **Settings → Config** page in the web UI.

See [Auth](../guides/auth.md) for the full flow.

## Section: App

```bash
APP_ENV=production
DEBUG=false
```

`DEBUG=true` enables verbose error responses from FastAPI — useful in development, **never** in production.

## Section: Reverse proxy

When Ampy3 is served through a reverse proxy, every request reaches the app from the proxy's IP. The Plex PIN endpoint rate-limits by client IP (10 attempts per IP per 5 minutes), so without proper configuration every client behind the proxy shares a single bucket and one user can lock out everyone else.

**Proxy settings are now managed in the web UI**: Settings → Network.

To enable proxy header reading:

1. Go to **Settings → Network** in the web UI
2. Check "Behind a reverse proxy"
3. Enter your proxy's CIDR ranges (e.g., `10.0.0.0/8`, `192.168.0.0/16`)
4. Click "Save settings"
5. **Restart the container** for the changes to take effect

The app will then read `X-Forwarded-For` headers only from requests originating from the trusted proxy IPs, allowing the rate limiter to work correctly.

### Example configurations

**Docker Compose with a local nginx proxy:**

```bash
# Add to .env or docker-compose.yml environment
APP_BIND=0.0.0.0
```

Then in Settings → Network:
- Enable "Behind a reverse proxy"
- Add `172.17.0.1/32` (or your docker bridge IP) and `127.0.0.1/32`

**Behind Cloudflare:**

Enable proxy mode and add Cloudflare's IP ranges:

```
104.16.0.0/13
104.24.0.0/14
172.64.0.0/13
```

(See [Cloudflare IP ranges](https://developers.cloudflare.com/fundamentals/get-started/reference/network-ports/#ip-addresses) for the current list.)

### Security considerations

- Leave the proxy setting **disabled** (the default) when the app is directly reachable from the internet — enabling proxy header reading without a proper IP allow-list is equivalent to letting any client spoof their IP and bypass the rate limiter.
- Always configure `TRUSTED_PROXIES` when enabling proxy mode — an empty list means the header is not trusted.
- The app validates that requests come from a trusted proxy before reading `X-Forwarded-For`. This prevents spoofing attacks.

## Local development overrides

There is no `tests/conftest.py` in this repo — each test sets the env vars it needs directly (see [`tests/test_db_initialization.py`](https://github.com/JakePeralta7/Ampy3/blob/main/tests/test_db_initialization.py) for the pattern). When running locally without Docker, export at least these before launching Uvicorn / Celery:

```bash
export CELERY_BROKER_URL=redis://localhost:6379/0
export CELERY_RESULT_BACKEND=redis://localhost:6379/1
```

See [Local setup](../development/local-setup.md) for the full dev workflow.