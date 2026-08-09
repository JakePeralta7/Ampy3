# Schemas

Pydantic request/response models. Each router in [`app.api`][app.api] has a corresponding module under [`app.schemas`][app.schemas].

## Schemas package

::: app.schemas
    options:
      show_source: true

## Per-router schemas

::: app.schemas.common
    options:
      show_source: true

::: app.schemas.targets
    options:
      show_source: true

::: app.schemas.playlists
    options:
      show_source: true

::: app.schemas.syncs
    options:
      show_source: true

::: app.schemas.schedules
    options:
      show_source: true

::: app.schemas.match_rules
    options:
      show_source: true

::: app.schemas.settings
    options:
      show_source: true

::: app.schemas.explore
    options:
      show_source: true

::: app.schemas.audit
    options:
      show_source: true

## Where to look next

- [Reference → API](api.md) — the routers that consume these schemas