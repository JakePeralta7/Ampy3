# Sync pipeline

When you click **Run now** (or when the scheduler fires), Ampy3 runs a Celery task that drives a [`SyncPipeline`][app.worker.pipeline.SyncPipeline]. The pipeline composes [`SyncPhase`][app.worker.phases.SyncPhase] instances — each phase handles one stage of the work, and phases are pluggable.

## High-level flow

```mermaid
sequenceDiagram
    participant UI as Web UI
    participant API as FastAPI
    participant Celery
    participant Fetch as FetchPhase
    participant Match as MatchPhase
    participant Finalize as FinalizePhase
    participant Plex as Plex / Jellyfin

    UI->>API: POST /api/syncs/{id}/run
    API->>Celery: enqueue run_sync
    Celery->>Fetch: 1. fetch_source()
    Fetch-->>Celery: tracks + playlist metadata
    loop per target
        Celery->>Match: 2. run_target() (MatchPhase)
        Match->>Plex: search by MusicBrainz ID
        Plex-->>Match: candidate ratings / items
        Match-->>Celery: per-track match result
        Celery->>Finalize: 3. FinalizePhase
        Finalize->>Plex: create / update playlist
    end
    Celery-->>API: SyncRun status = completed
```

## Phase 1: FetchPhase

**Lives in:** [`app.worker.phases.FetchPhase`][app.worker.phases.FetchPhase]

- Pulls the source playlist through the appropriate [`IPlatformSource`][app.core.models.IPlatformSource] (YouTube Music, Deezer, …)
- Persists every track to the `PlaylistTrack` table (de-duplicated on source + external ID)
- **Runs once per sync invocation**, shared across all configured targets

The phase takes `source_url`, `source`, optional `schedule_id`, and `target_ids` in its input data dict.

## Phase 2: MatchPhase

**Lives in:** [`app.worker.phases.MatchPhase`][app.worker.phases.MatchPhase]

- For each track, calls [`MatchEngine`][app.core.services.matcher.MatchEngine] to find the best MusicBrainz release
- Loads the active match-rule set from the DB (`get_active_rules_sync`)
- Writes a `SyncRunTrack` row per track with the resulting `MatchResult`
- **Runs once per target**

See [Metadata matching](metadata-matching.md) for how the rules work.

## Phase 3: FinalizePhase

**Lives in:** [`app.worker.phases.FinalizePhase`][app.worker.phases.FinalizePhase]

- Computes the diff between Plex/Jellyfin and the desired playlist
- Creates the playlist if missing, then adds/removes items to match the source order
- Writes `SyncRunTrackTarget` rows for per-target outcomes
- Updates the `SyncRun` status

## `SyncContext`

[`SyncContext`][app.worker.context.SyncContext] is the per-run bag of state passed between phases: `sync_id`, `target_id`, the source URL, the matched tracks, and so on. It's constructed once per target and reused across phases.

## Phase composition

`SyncPipeline` accepts a custom `phases` list — by default `[MatchPhase(), FinalizePhase()]` (Fetch is called separately via `SyncPipeline.fetch_source()`). This makes it easy to:

- Add a **`ReMatchPhase`** for "re-evaluate only" runs that don't re-fetch.
- Add a **`DryRunPhase`** that stops after matching, so you can preview what *would* happen.
- Swap the order — e.g. `[FinalizePhase(), MatchPhase()]` for "force-write without re-matching".

See [`SyncPipeline`][app.worker.pipeline.SyncPipeline] for the composition API.

## Error handling

Each phase returns a [`PhaseResult`][app.worker.phases.PhaseResult] with `success`, `data`, and `error` fields. A failing phase short-circuits the pipeline and marks the `SyncRun` as failed; partial work is rolled back where possible.

Per-track failures do **not** fail the whole sync — they're recorded against the `SyncRunTrack` and surfaced in the [audit log](../operations/monitoring.md).

## Where to look next

- [`app.worker.pipeline`][app.worker.pipeline] — pipeline orchestration
- [`app.worker.phases`][app.worker.phases] — phase ABC + concrete phases
- [`app.worker.matcher`][app.worker.matcher] — legacy single-target matcher (still used by some Explore workflows)
- [Explore](explore.md) — DAG-style alternative to the linear pipeline