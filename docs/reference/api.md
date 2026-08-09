# API reference

The FastAPI app exposes every route under `/api/*`. The live Swagger UI is at `/docs` (development only) and the raw OpenAPI schema at `/openapi.json` (also dev-only).

This page indexes the auto-generated reference for each router.

## Routers

| Tag | Router | Purpose |
|-----|--------|---------|
| `auth` | [`app.auth.router`][app.auth.router] | Plex SSO login/callback, session, `/me`, `/logout` |
| `audit` | [`app.api.audit`][app.api.audit] | Audit log querying |
| `explore` | [`app.api.explore`][app.api.explore] | Explore providers, charts, moods |
| `match-rules` | [`app.api.match_rules`][app.api.match_rules] | Rule CRUD + canvas test runner |
| `playlists` | [`app.api.playlists`][app.api.playlists] | Source/target playlist listing, sync triggers |
| `scheduled-syncs` | [`app.api.schedules`][app.api.schedules] | Scheduled sync CRUD |
| `settings` | [`app.api.settings`][app.api.settings] | Runtime configuration |
| `syncs` | [`app.api.syncs`][app.api.syncs] | Manual sync triggers and sync history |
| `targets` | [`app.api.targets`][app.api.targets] | Available sync target platforms |

All routers are mounted in [`register_routers`][app.api.register_routers] (called from [`main.py`](https://github.com/JakePeralta7/Ampy3/blob/main/src/main.py)).

## App object

The FastAPI app is constructed in `src/main.py`. The full source is browsable in the repository — visit `/docs` at runtime for an interactive explorer, or read the auto-generated router references below.

The `app/api` package centralises router registration — see [`register_routers`][app.api.register_routers] below.

## Router registry

::: app.api
    options:
      show_source: true
      members:
        - register_routers
        - auth_router
        - audit_router
        - match_rules_router
        - playlists_router
        - schedules_router
        - settings_router
        - syncs_router
        - targets_router
        - explore_router

## Auto-generated endpoints

The FastAPI app is mounted on `app = FastAPI(...)` inside [`main.py`](https://github.com/JakePeralta7/Ampy3/blob/main/src/main.py). Visit `/docs` at runtime for an interactive explorer; the pages below cover the underlying router functions in detail.

::: app.auth.router
    options:
      show_source: true
      members:
        - plex_login
        - plex_callback
        - plex_resources
        - plex_setup
        - auth_me
        - auth_logout

::: app.api.targets
    options:
      show_source: true

::: app.api.playlists
    options:
      show_source: true

::: app.api.schedules
    options:
      show_source: true

::: app.api.syncs
    options:
      show_source: true

::: app.api.match_rules
    options:
      show_source: true

::: app.api.explore
    options:
      show_source: true

::: app.api.audit
    options:
      show_source: true

::: app.api.settings
    options:
      show_source: true

## CORS & auth

- When `REQUIRE_AUTH=true`, all `/api/*` routes (except `/api/auth/plex/login` and `/api/auth/plex/callback`) require a valid session cookie. See [Auth](../guides/auth.md).
- When `REQUIRE_AUTH=false`, every route is reachable without auth — `get_current_user` returns a synthetic admin.

## Where to look next

- [Reference → Services](services.md)
- [Reference → Worker](worker.md)
- [Reference → Core](core.md)
- [Auth](../guides/auth.md)