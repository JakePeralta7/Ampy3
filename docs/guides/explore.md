# Explore

The **Explore** page lets you discover music across all your configured sources from a single UI — charts, moods, new releases, mood/genre playlists, and search — and one-click-sync anything you find. It runs on its own plugin registry, separate from "sync sources" and from the match-rule node graph.

!!! info "Explore is **not** a node graph"
    Confusingly, Ampy3 has three independent registries:

    - **Sources** — playlist fetchers (used by syncs). See [Sources & targets](sources-and-targets.md).
    - **Targets** — media servers (used by syncs). See [Sources & targets](sources-and-targets.md).
    - **Explore providers** — content discovery (charts, moods, search). See below.
    - **Match-rule nodes** — matching primitives (separate from Explore entirely). See [Metadata matching](metadata-matching.md#built-in-node-types).

    Explore does **not** compose DAGs of fetch/match/transform nodes; it's a discovery UI backed by platform-specific providers.

## Provider registry

[`ExploreRegistry`][app.core.explore.registry.ExploreRegistry] works exactly like `SourceRegistry` — same decorator pattern:

```python
from src.app.core.explore.registry import register_explore_provider
from src.app.core.explore.base import ExploreProvider

@register_explore_provider("youtube_music")
class YTMusicExploreProvider(ExploreProvider):
    provider_id = "youtube_music"
    display_name = "YouTube Music"
    anonymous = False  # requires cookies / OAuth
    ...
```

### Built-in providers

| ID | Module | Auth |
|----|--------|------|
| `youtube_music` | [`app.core.explore.providers.ytmusic`][app.core.explore.providers.ytmusic] | Required |
| `deezer` | [`app.core.explore.providers.deezer`][app.core.explore.providers.deezer] | Anonymous |

### `anonymous` providers

Some providers (like Deezer) can serve charts/moods without any user authentication. They set `anonymous = True` and are available to all users, regardless of whether `REQUIRE_AUTH=true`.

## What providers return

Every provider implements **five** async methods returning typed models from [`app.core.explore.models`][app.core.explore.models]:

| Method | Returns |
|--------|---------|
| `get_home()` | [`ExploreHome`][app.core.explore.models.ExploreHome] — sections for the home page. |
| `get_charts()` | [`ChartsBundle`][app.core.explore.models.ChartsBundle] — top songs/artists/videos. |
| `get_moods()` | `list[`[`MoodCategory`][app.core.explore.models.MoodCategory]`]` — mood/genre categories. |
| `get_mood_playlists(mood_id)` | `list[`[`ExploreItem`][app.core.explore.models.ExploreItem]`]` — playlists for a given mood/genre. |
| `search_playlists(query)` | `list[`[`ExploreItem`][app.core.explore.models.ExploreItem]`]` — search results. |

Each section is a stream of [`ExploreItem`][app.core.explore.models.ExploreItem]s that the UI renders as a card grid. The "Sync to Plex" button on each card turns it into a regular [sync pipeline](sync-pipeline.md) run.

## Explore DAG nodes?

There are none. The **match-rule canvas** (see [Metadata matching](metadata-matching.md#built-in-node-types)) is the only DAG-style composition surface in Ampy3. Its `search` and `compare` nodes work against the target library and a `TrackMetadata`; they don't draw from Explore providers. If you want to build a custom graph that combines discovery + matching, write a node that imports an Explore provider directly and emits [`TrackMetadata`][app.core.models.TrackMetadata].

## Adding an Explore provider

1. Subclass [`ExploreProvider`][app.core.explore.base.ExploreProvider].
2. Implement all five abstract methods (`get_home`, `get_charts`, `get_moods`, `get_mood_playlists`, `search_playlists`).
3. Set class attributes `provider_id`, `display_name`, `anonymous`.
4. Decorate with `@register_explore_provider("your_id")`.
5. Import the module from a place that runs at startup (mirrors how `app.core.explore.providers.deezer` is imported).

It will appear in the Explore page automatically.

## Where to look next

- [`app.core.explore`][app.core.explore] — provider base + registry + models
- [`app.core.explore.providers`][app.core.explore.providers] — built-in adapters
- [`app.api.explore`][app.api.explore] — REST endpoints backing the Explore UI
- [Metadata matching](metadata-matching.md#built-in-node-types) — the actual DAG node system