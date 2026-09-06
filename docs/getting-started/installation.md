# Installation

Ampy3 ships as a Docker Compose stack with five services: `web`, `worker`, `postgres`, and `valkey`. Everything you need — API, Celery worker, database, and broker — comes up with one command.

## Prerequisites

- **Docker** 24+ and **Docker Compose** v2 (`docker compose ...`)
- A **Plex** or **Jellyfin** server reachable from the Ampy3 host
- (Optional) A **YouTube Music** session if you want authenticated playlists — configure it later from the UI (Settings → Sources)

## Docker Compose (recommended)

```bash
git clone https://github.com/JakePeralta7/Ampy3
cd Ampy3
docker compose up --build -d
```

The API is served on `http://localhost:8000` by default. The first request walks you through selecting your Plex/Jellyfin server.

!!! tip "Custom host port"
    Override the host port by exporting `APP_PORT` before `up`:
    ```bash
    APP_PORT=9000 docker compose up --build -d
    ```

## Bare metal (advanced)

You can run the API and worker directly against a local Postgres + Valkey. This is mainly useful for development — production deployments should use the Compose stack.

### Backend

```bash
# from the repo root
pip install -e ".[dev]"

# PYTHONPATH must include src/ — the Dockerfile sets this, you must set it locally too.
export PYTHONPATH=$PWD/src

# Apply migrations against your database
python migrate.py upgrade

# Run the API (FastAPI + Uvicorn)
uvicorn main:app --host 0.0.0.0 --port 8000

# In another shell, run a Celery worker
celery -A app.worker.app worker --loglevel=info --concurrency=1
```

!!! warning "PYTHONPATH must include `src/`"
    The package layout is `src/app/...`, not `app/...`. Forgetting `PYTHONPATH=$PWD/src` is the most common cause of `ModuleNotFoundError: No module named 'app'` on local installs.

### Frontend

```bash
cd web
pnpm install --frozen-lockfile
pnpm run dev      # http://localhost:5173 — Vite proxies /api to :8000
```

For a production bundle, build with `pnpm run build` and let the API serve `web/dist/` (see [SPA serving](../development/architecture.md#spa-serving)).

## YouTube Music authentication (optional)

YouTube Music playlists can be fetched anonymously, but playlists that require an authenticated session (or personalised Explore content) need auth. There is **no cookie file to mount** — instead, open **Settings → Sources** in the web UI and paste the ytmusicapi browser/auth JSON from your YouTube Music session. It is stored in the app database and used by both the sync source and the Explore provider.

For a how-to on producing that JSON, see the [ytmusicapi setup guide](https://ytmusicapi.readthedocs.io/en/latest/setup/browser.html).

## Verifying the install

```bash
curl http://localhost:8000/health
# {"status":"ok",...}
```

Open `http://localhost:8000` — you should see the Plex/Jellyfin setup wizard. Continue to [First sync](first-sync.md) once a target is configured.

## Updating

```bash
git pull
docker compose pull
docker compose up --build -d
```

Migrations run automatically at API startup via `init_db()` in `src/app/db.py`.

## Uninstalling

```bash
docker compose down            # stop + remove containers
docker compose down -v         # also drop postgres_data volume (DESTRUCTIVE)
```