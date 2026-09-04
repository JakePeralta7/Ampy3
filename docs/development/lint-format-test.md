# Lint, format & test

The repo uses **Ruff (lint + format), mypy, and pytest** on the backend and **Biome** on the frontend. CI (`.github/workflows/ci.yml`) enforces `ruff check`, `ruff format --check`, Biome, `tsc --noEmit`, and pytest on PRs against `main`. `mypy` is configured `strict` in `pyproject.toml` but only run locally. There are no pre-commit hooks.

## Python — Ruff format

```bash
# Format the codebase
ruff format src/ tests/

# Verify (no changes) — useful in CI
ruff format --check src/ tests/
```

Line length is **100**, target version is **py314** (see `pyproject.toml`). Ruff handles both linting and formatting.

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
pnpm install --frozen-lockfile
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
ruff format --check src/ tests/
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