# Contributing

Thanks for taking the time to improve Ampy3. The repo is a small, focused project — please keep contributions aligned with the existing patterns.

## Code of conduct

Be kind, assume good faith, and keep technical disagreement focused on the code. There is no formal CoC file in this repo; the standard open-source norms apply.

## Branching

- Fork or branch from `main`
- Use a short, descriptive branch name: `fix/plex-timeout`, `feat/jellyfin-playlists`, `docs/auth-flow`
- One logical change per branch — easier to review, easier to revert

## Commit messages

This repo doesn't enforce a convention. Recommended:

```
<scope>: <imperative summary>

<body explaining why, not what>
```

`<scope>` is usually the affected module (`worker`, `auth`, `docs`, `infra`, …). Keep the summary under ~70 chars.

## Coding conventions

These are baked into the existing code — please follow them.

- **Python 3.14**, line length 100, Black + Ruff + mypy strict.
- **Async in FastAPI routes**, **sync in Celery tasks**. Don't mix.
- **Type hints everywhere** — `mypy --strict` is on.
- **Pydantic** for all request/response shapes — see `src/app/schemas/`.
- **SQLAlchemy 2.0** `mapped_column` / `Mapped[...]` style — see `src/app/models.py`.
- **Registry pattern** for sources, targets, nodes, and explore providers — see [Sources and targets](../guides/sources-and-targets.md).
- **No comments** unless they explain something non-obvious. The code should read like prose.
- **`F401` is intentionally ignored** — don't fight it for new modules. If you genuinely don't need an import, remove it; otherwise leave the `# noqa: F401`.

## Secrets

**Never commit secrets.** This includes:

- Plex tokens (`plex_token`, `owner_plex_token`)
- `SECRET_KEY` values
- `cookies/cookies.txt` (the directory *must* exist but must not contain a real cookie file in git)
- Database passwords, even for dev

If you accidentally commit one, rotate it immediately and use `git filter-repo` or BFG to scrub history — don't just amend.

## Pull request workflow

1. Open a PR against `main`
2. CI runs (lint + tests) — if it doesn't pass, the PR isn't mergeable
3. Request review from a maintainer
4. Squash-merge once approved

PR description should answer:

- **What** does this change?
- **Why** is it needed? (link the issue if there is one)
- **How** did you test it? (commands run, screenshots for UI changes)
- Any **breaking changes** or follow-ups?

## Testing

- Add or update tests for any behavioural change
- Don't add tests for cosmetic refactors
- Use the existing fixtures in `tests/` and `tests/__pycache__/`
- Async tests don't need `@pytest.mark.asyncio` — `asyncio_mode = "auto"`

## Adding a registry plugin

If you're adding a new source, target, explore provider, or node:

1. Subclass the corresponding ABC.
2. Decorate with the appropriate `@register_*` decorator.
3. Import the module from a place that runs at startup (see how existing modules do it).
4. Document the new plugin in the relevant guide page.

## Documentation

If your change adds a user-facing feature or changes behaviour:

- Update the relevant page under `docs/guides/` or `docs/operations/`.
- If you added a public Python API, add a docstring — `mkdocstrings` will pull it into the reference section automatically.

To preview docs locally:

```bash
pip install -e ".[docs]"
mkdocs serve
```

## Release process

There is no formal release process yet. Tags are cut manually from `main`; Docker images are built from those tags.

## Where to look next

- [Local setup](local-setup.md)
- [Architecture](architecture.md)
- [Lint, format & test](lint-format-test.md)