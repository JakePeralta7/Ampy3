# Sources and targets

Ampy3 is **pluggable at both ends** — any source that can produce a list of tracks can be wired in, and any media server that exposes a "playlist" concept can be a target. Both registries live in `src/app/core/`.

## Source registry

[`SourceRegistry`][app.core.sources.registry.SourceRegistry] is a simple class-level dictionary. Sources self-register with the [`@register_source`][app.core.sources.registry.register_source] decorator:

```python
from src.app.core.sources.registry import register_source
from src.app.core.sources.base import IPlatformSource

@register_source("youtube_music")
class YouTubeMusicSource(IPlatformSource):
    source_id = "youtube_music"
    display_name = "YouTube Music"

    async def get_playlist(self, url: str) -> list[TrackMetadata]: ...
    @classmethod
    def supports_url(cls, url: str) -> bool: ...
```

### Built-in sources

| ID | Module | Notes |
|----|--------|-------|
| `youtube_music` | [`app.core.sources.ytmusic`][app.core.sources.ytmusic] | Uses `ytmusicapi` + cookies for authenticated playlists. |
| `deezer` | [`app.core.sources.deezer`][app.core.sources.deezer] | Public playlists; no auth. |

Look up registered sources at runtime:

```python
from src.app.core.sources.registry import SourceRegistry
SourceRegistry.list_sources()
# [{'id': 'youtube_music', 'name': 'YouTube Music'}, ...]
```

### Adding a new source

1. Subclass [`IPlatformSource`][app.core.models.IPlatformSource].
2. Implement `get_playlist(url)`, `display_name`, `source_id`, and `supports_url(url)`.
3. Decorate with `@register_source("your_id")`.
4. Import the module from somewhere that gets loaded at startup (see how `app.core.sources.deezer` is imported in `app.api.playlists`).

The new source automatically appears in the **Add sync** dropdown.

## Target registry

[`TargetRegistry`][app.core.targets.registry.TargetRegistry] follows the same pattern but additionally accepts an **async factory** that builds a fully-initialised target from DB config:

```python
from src.app.core.targets.registry import register_target
from src.app.core.targets.base import BaseTarget

@register_target("plex", factory=create_plex_target)
class PlexTarget(BaseTarget):
    target_id = "plex"
    display_name = "Plex Media Server"
    ...
```

The factory is what reads `plex_host` / `plex_token` from the `Config` table and returns a connected `BaseTarget`. Use [`TargetService`][app.services.target.TargetService] for lazy (re)construction.

### Built-in targets

| ID | Module | Notes |
|----|--------|-------|
| `plex` | [`app.core.targets.plex`][app.core.targets.plex] | Uses `plexapi`. SSO-driven setup via `app.auth.router`. |
| `jellyfin` | [`app.core.targets.jellyfin`][app.core.targets.jellyfin] | Uses Jellyfin's REST API. |

### Adding a new target

1. Subclass [`BaseTarget`][app.core.targets.base.BaseTarget].
2. Implement `search(query) -> list[Track]`, `get_playlist(id)`, `create_playlist(name, tracks)`, etc.
3. Write a `create_your_target() -> BaseTarget` factory that reads its config.
4. Decorate with `@register_target("your_id", factory=create_your_target)`.
5. Add a "Connect" UI flow (or expose a settings API endpoint) that writes the target's config to `Config`.

The new target shows up in the **Setup wizard** immediately.

## URL detection

`SourceRegistry.detect(url)` walks all registered sources and returns the first whose `supports_url(url)` returns `True`. The web UI uses this to pre-select the source when you paste a playlist URL.

## Single source of truth

Both registries are class-level (`_sources`, `_targets`). That means:

- **Import side effects matter.** A source/target module must be imported somewhere that runs at startup — otherwise it won't be registered when a request lands.
- **Test isolation.** In tests, `SourceRegistry._sources.clear()` (and the equivalent for targets) resets state. `pytest` fixtures in `tests/conftest.py` use this.

## Where to look next

- [`app.core.sources`][app.core.sources] — source base + adapters
- [`app.core.targets`][app.core.targets] — target base + adapters
- [`app.services.target`][app.services.target] — lazy target singleton service
- [Sync pipeline](sync-pipeline.md) — how source + target fit together