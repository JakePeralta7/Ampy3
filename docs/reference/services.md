# Services

The `app.services` package holds the **lazy singletons** the API and worker share. Everything is accessed through the factories in [`app.services`][app.services] — never instantiate these directly.

## Why lazy singletons?

Each service talks to an external system (Celery broker, Valkey cache, target media server). We want:

- **One instance per process** (don't open new Valkey connections on every request)
- **Late construction** (no work at import time — keeps tests fast and imports safe)
- **Trivial reset** in tests (drop the singleton, the next call rebuilds)

The pattern is implemented in [`ServiceBase`][app.services.base.ServiceBase].

## Service container

::: app.services
    options:
      show_source: true
      members:
        - get_celery_app
        - get_valkey_client
        - get_sync_target
        - list_sync_targets
        - reset_services

## Built-in services

### Celery

::: app.services.celery
    options:
      show_source: true
      members:
        - CeleryService

### Valkey

::: app.services.valkey
    options:
      show_source: true
      members:
        - ValkeyService

### Sync target

::: app.services.target
    options:
      show_source: true
      members:
        - TargetService

### Scheduler

::: app.services.scheduler
    options:
      show_source: true
      members:
        - SchedulerService

### Audit

::: app.services.audit
    options:
      show_source: true
      members:
        - log_event
        - log_event_sync

### Base

::: app.services.base
    options:
      show_source: true

## Where to look next

- [Architecture](../development/architecture.md#servicecontainer-lazy-singletons)
- [Reference → API](api.md)
- [Reference → Worker](worker.md)