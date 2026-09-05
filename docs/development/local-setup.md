# Local setup

This page walks through running Ampy3 end-to-end on your laptop, without Docker, so you can iterate quickly on backend or frontend code.

## Prerequisites

- **Python** 3.12+ (project targets 3.14 per `pyproject.toml`)
- **Node.js** 26 and **pnpm** 11 (see `web/package.json` for the exact pinned version)
- **Postgres** 16 reachable from your laptop (or run it in Docker: `docker run -d --name ampy3-pg -p 5432:5432 -e POSTGRES_USER=ampy3 -e POSTGRES_PASSWORD=ampy3 -e POSTGRES_DB=ampy3 postgres:16-alpine`)
- **Valkey** (or Redis) reachable from your laptop: `docker run -d --name ampy3-valkey -p 6379:6379 valkey/valkey:7.2-alpine`

## Backend setup

```bash
git clone https://github.com/JakePeralta7/Ampy3
cd Ampy3

# Create a virtualenv (uv, poetry, or stdlib — pick your favourite)
python -m venv .venv
source .venv/bin/activate          # Windows: .venv\Scripts\Activate.ps1

# Install with dev + docs extras
pip install -e ".[dev,docs]"

# Set PYTHONPATH — the package lives under src/, not at the repo root
export PYTHONPATH=$PWD/src         # Windows PowerShell: $env:PYTHONPATH = "$PWD\src"

# Point at your local Valkey
export CELERY_BROKER_URL=redis://localhost:6379/0
export CELERY_RESULT_BACKEND=redis://localhost:6379/1

# Apply migrations
python migrate.py upgrade

# Run the API
uvicorn main:app --host 0.0.0.0 --port 8000 --reload

# In a second terminal, run a Celery worker
export PYTHONPATH=$PWD/src         # and the same CELERY_BROKER_URL
celery -A app.worker.app worker --loglevel=info --concurrency=1
```

!!! danger "`PYTHONPATH` is required"
    The package layout is `src/app/...`, so without `PYTHONPATH=$PWD/src` you'll see `ModuleNotFoundError: No module named 'app'`. The Dockerfile sets this for you automatically; you have to set it yourself when running locally.

!!! tip "PowerShell users"
    ```powershell
    $env:PYTHONPATH = "$PWD\src"
    ```

## Frontend setup

In a third terminal:

```bash
cd web
pnpm install --frozen-lockfile
pnpm run dev
```

Vite serves the React UI on `http://localhost:5173` and proxies `/api` to your Uvicorn on `:8000`. No CORS configuration needed in development.

## API key / auth in dev

`REQUIRE_AUTH` defaults to `false`. Leave it that way locally — the UI will skip the Plex SSO wizard and you can connect a Plex/Jellyfin target directly.

If you want to test the auth flow locally:

```bash
export REQUIRE_AUTH=true
export APP_URL=http://localhost:8000
export SECRET_KEY=$(openssl rand -hex 32)        # any non-empty value works in dev
```

Then visit `http://localhost:8000/api/auth/plex/login` to start the Plex SSO flow.

## Verifying everything is wired up

```bash
# API health
curl http://localhost:8000/health

# Swagger UI (dev only)
open http://localhost:8000/docs

# Celery worker ping
docker exec ampy3-valkey redis-cli ping
celery -A app.worker.app inspect ping -d celery@$(hostname)
```

## Common dev workflow

| Task | Command |
|------|---------|
| Format code | `ruff format src/ tests/` |
| Lint | `ruff check src/ tests/` |
| Run tests | `pytest` |
| Type-check | `mypy src/` |
| Frontend lint | `cd web && pnpm run lint` |
| Frontend build | `cd web && pnpm run build` |
| Build docs locally | `mkdocs serve` |

See [Lint, format & test](lint-format-test.md) for details.

## Resetting the dev DB

```bash
# Wipe and recreate
docker exec ampy3-pg dropdb -U ampy3 ampy3 --if-exists
docker exec ampy3-pg createdb -U ampy3 ampy3
python migrate.py bootstrap          # creates schema from ORM + seeds default match rules
```

## IDE setup

- **VS Code**: Python + Pylance + Ruff extension; TypeScript + Biome extension. Set `"python.analysis.extraPaths": ["src"]` in `.vscode/settings.json`.
- **PyCharm**: mark `src/` as a Sources root.

## Where to look next

- [Architecture](architecture.md) — what's actually in the repo and why
- [Lint, format & test](lint-format-test.md) — keep CI green
- [Contributing](contributing.md) — branch / PR conventions