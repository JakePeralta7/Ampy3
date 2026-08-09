# API reference

The FastAPI app exposes every route under `/api/v1/*` for the public REST surface and `/api/auth/*` for Plex SSO. The live Swagger UI is at `/docs` (only when `APP_ENV != "production"`) and the raw OpenAPI schema at `/openapi.json` (same condition).

This page indexes the auto-generated reference for each router.

## URL conventions

- All public REST endpoints live under `/api/v1/...` (see each router's `prefix`).
- Plex SSO endpoints live under `/api/auth/...` and are exempt from session validation in `PUBLIC_PATHS`.
- The session middleware in [`src/main.py`](https://github.com/JakePeralta7/Ampy3/blob/main/src/main.py) protects every `/api/*` route when `REQUIRE_AUTH=true`.

## Routers

| Tag | Router | Prefix | Purpose |
|-----|--------|--------|---------|
| `auth` | [`app.auth.router`][app.auth.router] | `/api/auth` | Plex SSO login/callback, session, `/me`, `/logout` |
| `audit` | [`app.api.audit`][app.api.audit] | `/api/v1/audit` | Audit log querying |
| `explore` | [`app.api.explore`][app.api.explore] | `/api/v1/explore` | Explore providers, charts, moods, search |
| `match-rules` | [`app.api.match_rules`][app.api.match_rules] | `/api/v1/match-rules` | Rule CRUD, reorder, test runner |
| `playlists` | [`app.api.playlists`][app.api.playlists] | `/api/v1/playlists` | Source/target playlist listing and search |
| `scheduled-syncs` | [`app.api.schedules`][app.api.schedules] | `/api/v1/schedules` | Scheduled sync CRUD + bulk actions + manual trigger |
| `settings` | [`app.api.settings`][app.api.settings] | `/api/v1/settings` | Runtime configuration |
| `syncs` | [`app.api.syncs`][app.api.syncs] | `/api/v1/syncs` | Manual sync trigger, status, history, diff |
| `targets` | [`app.api.targets`][app.api.targets] | `/api/v1/targets` | Available sync target platforms |

All routers are mounted in [`register_routers`][app.api.register_routers] (called from [`src/main.py`](https://github.com/JakePeralta7/Ampy3/blob/main/src/main.py)).

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

The FastAPI app is mounted on `app = FastAPI(...)` inside [`src/main.py`](https://github.com/JakePeralta7/Ampy3/blob/main/src/main.py). Visit `/docs` at runtime for an interactive explorer; the pages below cover the underlying router functions in detail.

### Auth

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

### Targets

::: app.api.targets
    options:
      show_source: true

### Playlists

::: app.api.playlists
    options:
      show_source: true

### Schedules

::: app.api.schedules
    options:
      show_source: true

### Syncs

::: app.api.syncs
    options:
      show_source: true

### Match rules

::: app.api.match_rules
    options:
      show_source: true

### Explore

::: app.api.explore
    options:
      show_source: true

### Audit

::: app.api.audit
    options:
      show_source: true

### Settings

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