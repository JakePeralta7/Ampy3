# Worker

Everything that runs **inside a Celery worker process** lives under [`app.worker`][app.worker]. The worker uses the **sync** SQLAlchemy session and `psycopg2`.

## Top-level

::: app.worker
    options:
      show_source: true

## Celery app

::: app.worker.app
    options:
      show_source: true
      members:
        - celery_app

## Tasks

::: app.worker.tasks
    options:
      show_source: true

## Pipeline

::: app.worker.pipeline
    options:
      show_source: true

## Phases

::: app.worker.phases
    options:
      show_source: true

## Matcher (legacy)

::: app.worker.matcher
    options:
      show_source: true

## Playlist sync

::: app.worker.playlist_sync
    options:
      show_source: true

## Session helpers

::: app.worker.session
    options:
      show_source: true

## Context

::: app.worker.context
    options:
      show_source: true

## Where to look next

- [Sync pipeline](../guides/sync-pipeline.md) — conceptual walkthrough
- [Reference → Core](core.md)
- [Reference → Services](services.md)