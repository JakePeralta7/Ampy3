# Lint, format & test

The repo uses **Black + Ruff + mypy + pytest** on the backend and **Biome** on the frontend. None of these are enforced by pre-commit hooks or CI in this repo today — you're expected to run them locally.

## Python — Black

```bash
# Format the codebase
black src/ tests/ alembic/ migrate.py

# Verify (no changes) — useful in CI
black --check src/ tests/ alembic/ migrate.py
```

Line length is **100**, target version is **py314** (see `pyproject.toml`).

## Python — Ruff

```bash
ruff check src/ tests/

# Apply auto-fixes
ruff check --fix src/ tests/
```

Enabled rule sets: `E, F, I, N, W, UP, B, SIM`. `F401` (unused imports) is **intentionally ignored**.

## Python — mypy

```bash
mypy src/
```

`strict = true` is on. A few third-party libs (`celery.*`, `apscheduler.*`, `celery.result`) are ignored via `[[tool.mypy.overrides]]` in `pyproject.toml`.

## Python — pytest

```bash
pytest                       # all tests
pytest tests/test_db_initialization.py
pytest -k "match"            # by name pattern
pytest --co                  # collect-only, no run
```

`asyncio_mode = "auto"` is set in `pyproject.toml` — async tests don't need `@pytest.mark.asyncio`.

## Frontend — Biome

```bash
cd web
pnpm install
pnpm run lint                # biome check
pnpm run format              # biome format --write
pnpm run build               # tsc + vite build
pnpm run dev                 # Vite dev server on :5173
```

Biome config lives at `web/biome.json` — space indent, line width 100. Several accessibility rules are disabled; see the config for the exact list.

## Pre-commit checklist

Before opening a PR:

```bash
# Python
black --check src/ tests/ alembic/ migrate.py
ruff check src/ tests/
mypy src/
pytest

# Frontend
cd web && pnpm run lint && pnpm run build
```

## Where to look next

- [Local setup](local-setup.md)
- [Architecture](architecture.md)
- [Contributing](contributing.md)