---
hide:
  - navigation
  - toc
---

# Ampy3

**Sync YouTube Music playlists to Plex or Jellyfin — matched against your media library.**

[![CI](https://github.com/JakePeralta7/Ampy3/actions/workflows/ci.yml/badge.svg?branch=main)](https://github.com/JakePeralta7/Ampy3/actions/workflows/ci.yml)
[![Read the Docs](https://img.shields.io/readthedocs/ampy3)](https://ampy3.readthedocs.io/)

Ampy3 turns YouTube Music playlists into first-class playlists in your self-hosted media server. For every source track, it searches your Plex or Jellyfin library using a configurable rule graph — scoring candidates by title, artist, and album similarity and keeping the best match above a threshold. A MusicBrainz lookup node is also available when you need canonical MB IDs.

<div class="grid cards" markdown>

-   :material-rocket-launch:{ .lg .middle } **Quick start**

    ---

    Up and running in one `docker compose` command — see [Installation](getting-started/installation.md).

    [:octicons-arrow-right-24: Install now](getting-started/installation.md)

-   :material-tune:{ .lg .middle } **Configuration**

    ---

    Every env var Ampy3 reads, with defaults and descriptions — see [Configuration](getting-started/configuration.md).

    [:octicons-arrow-right-24: Configure](getting-started/configuration.md)

-   :material-book-open-page-variant:{ .lg .middle } **Guides**

    ---

    How the sync pipeline, match rules, and Explore discovery actually work.

    [:octicons-arrow-right-24: Read the guides](guides/sync-pipeline.md)

-   :material-api:{ .lg .middle } **API reference**

    ---

    Auto-generated from Python docstrings across `app.api`, `app.services`, `app.worker`, and more.

    [:octicons-arrow-right-24: Browse the API](reference/api.md)

</div>

## Why Ampy3?

!!! info "Metadata-first, not URL-first"
    Most sync tools copy YouTube URLs verbatim and end up with messy libraries. Ampy3 looks every track up on MusicBrainz and adds the canonical release to Plex/Jellyfin — so you get accurate tags, artwork, and gapless playback.

- **Plug-and-play Docker stack** — `postgres`, `valkey`, API, Celery worker, and the web UI in one `docker compose up`.
- **Tunable match rules** — adjust confidence thresholds and the search/compare logic from the UI; rules are YAML DAGs you can edit.
- **Auditable runs** — every sync writes per-track outcomes to the audit log.
- **Discover & sync** — the Explore page surfaces charts, moods, and new releases across your sources for one-click syncing.

## Screenshots

![Plex server setup](assets/screenshots/plex-setup.png)
![Dashboard](assets/screenshots/dashboard.png)
![Syncs](assets/screenshots/syncs.png)
![Adding a sync schedule](assets/screenshots/sync-create.png)
![Explore](assets/screenshots/explore.png)
![Audit log](assets/screenshots/audit.png)
![Settings — Config](assets/screenshots/settings.png)
![Settings — Targets](assets/screenshots/settings-targets.png)
![Settings — Match rules](assets/screenshots/settings-matching.png)

On first launch Ampy3 walks you through selecting your Plex or Jellyfin server. Other pages (Dashboard, Syncs, Explore, Audit Log, Settings) unlock once a target server is configured.

## Stack

| Layer    | Tech                                                          |
|----------|---------------------------------------------------------------|
| Backend  | Python / FastAPI + Celery workers                            |
| Frontend | React / TypeScript / Tailwind (Vite)                          |
| Infra    | Docker Compose, PostgreSQL 16, Valkey (Redis-compatible)     |
| Matching | Target library search (Plex/Jellyfin) + MusicBrainz as an optional node |

## Next steps

<div class="grid cards" markdown>

-   :material-download:{ .lg .middle } **Install**

    ---

    [getting-started/installation.md](getting-started/installation.md)

-   :material-flag-checkered:{ .lg .middle } **First sync**

    ---

    [getting-started/first-sync.md](getting-started/first-sync.md)

-   :material-cog-outline:{ .lg .middle } **Architecture**

    ---

    [development/architecture.md](development/architecture.md)

</div>