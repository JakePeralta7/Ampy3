# Core domain

The `app.core` package holds the **domain logic** — the parts that don't know they're running inside FastAPI or Celery.

## Top-level

::: app.core
    options:
      show_source: true

## Models

::: app.core.models
    options:
      show_source: true

## Matching

Pure scoring helpers — no I/O. Used by both the legacy matcher and the rule-graph engine.

::: app.core.matching
    options:
      show_source: true

## MusicBrainz client

::: app.core.musicbrainz
    options:
      show_source: true

## Sources

::: app.core.sources
    options:
      show_source: true

### Source adapters

::: app.core.sources.ytmusic
    options:
      show_source: true

::: app.core.sources.deezer
    options:
      show_source: true

### Registry

::: app.core.sources.registry
    options:
      show_source: true

## Targets

::: app.core.targets
    options:
      show_source: true

### Target adapters

::: app.core.targets.plex
    options:
      show_source: true

::: app.core.targets.jellyfin
    options:
      show_source: true

### Base + registry

::: app.core.targets.base
    options:
      show_source: true

::: app.core.targets.registry
    options:
      show_source: true

## Node handlers

The match-rule graph executor pulls handlers from here.

::: app.core.nodes
    options:
      show_source: true

::: app.core.nodes.base
    options:
      show_source: true

::: app.core.nodes.registry
    options:
      show_source: true

### Individual handlers

::: app.core.nodes.search
    options:
      show_source: true

::: app.core.nodes.matching
    options:
      show_source: true

::: app.core.nodes.musicbrainz
    options:
      show_source: true

::: app.core.nodes.similarity
    options:
      show_source: true

::: app.core.nodes.transform
    options:
      show_source: true

::: app.core.nodes.logic
    options:
      show_source: true

::: app.core.nodes.io
    options:
      show_source: true

## Explore

::: app.core.explore
    options:
      show_source: true

### Providers

::: app.core.explore.providers
    options:
      show_source: true

::: app.core.explore.providers.ytmusic
    options:
      show_source: true

::: app.core.explore.providers.deezer
    options:
      show_source: true

### Models

::: app.core.explore.models
    options:
      show_source: true

### Base + registry

::: app.core.explore.base
    options:
      show_source: true

::: app.core.explore.registry
    options:
      show_source: true

## Match engine service

::: app.core.services
    options:
      show_source: true

::: app.core.services.matcher
    options:
      show_source: true

## Providers (metadata)

::: app.core.providers
    options:
      show_source: true

::: app.core.providers.base
    options:
      show_source: true

::: app.core.providers.musicbrainz
    options:
      show_source: true

::: app.core.providers.registry
    options:
      show_source: true

## Where to look next

- [Metadata matching](../guides/metadata-matching.md)
- [Sources and targets](../guides/sources-and-targets.md)
- [Explore](../guides/explore.md)