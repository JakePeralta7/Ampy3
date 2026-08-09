# ORM models

SQLAlchemy 2.0 mapped models. There are two layers:

- [`app.models`][app.models] — operational tables (sync runs, schedules, audit log, match rules, config)
- Domain dataclasses (`TrackMetadata`, source/target interfaces) live in [`app.core.models`][app.core.models] — see [Reference → Core](core.md) for that.

## Operational models

::: app.models
    options:
      show_source: true

## Where to look next

- [Reference → Schemas](schemas.md) — request/response shapes
- [Reference → Core](core.md) — how domain models are used