# Sources and targets

Ampy3 is **pluggable at both ends** — any source that can produce a list of tracks can be wired in, and any media server that exposes a "playlist" concept can be a target. Both registries live in `src/app/core/`.

## Source registry

[`SourceRegistry`][app.core.sources.registry.SourceRegistry] is a simple class-level dictionary. Sources self-register with the [`@register_source`][app.core.sources.registry.register_source] decorator:

```python
from src.app.core.sources.registry import register_source
from src.app.core.models import IPlatformSource, PlaylistMetadata

@register_source("youtube_music")
class YouTubeMusicSource(IPlatformSource):
    source_id = "youtube_music"
    display_name = "YouTube Music"

    async def get_playlist(self, playlist_url: str) -> PlaylistMetadata: ...
    @classmethod
    def supports_url(cls, url: str) -> bool: ...
```

### Built-in sources

| ID | Module | Notes |
|----|--------|-------|
| `youtube_music` | [`app.core.sources.ytmusic`][app.core.sources.ytmusic] | Uses `ytmusicapi`; optional auth via Settings → Sources. |
| `deezer` | [`app.core.sources.deezer`][app.core.sources.deezer] | Public playlists; no auth. |

Look up registered sources at runtime:

```python
from src.app.core.sources.registry import SourceRegistry
SourceRegistry.list_sources()
# [{'id': 'youtube_music', 'name': 'YouTube Music'}, ...]
```

### Adding a new source

1. Subclass [`IPlatformSource`][app.core.models.IPlatformSource] (defined in `app.core.models`).
2. Implement `get_playlist(playlist_url) -> PlaylistMetadata` and `supports_url(url)` (classmethod). Override `get_playlist_cache_identifier` if you want a non-default cache key.
3. Set class attributes `source_id` and `display_name`.
4. Decorate with `@register_source("your_id")`.
5. Import the module from somewhere that gets loaded at startup (see how `app.core.sources.deezer` is imported in `app.api.playlists`).

The new source automatically appears in the **Add sync** dropdown.

## Target registry

[`TargetRegistry`][app.core.targets.registry.TargetRegistry] follows the same pattern but additionally accepts an **async factory** that builds a fully-initialised target from DB config. The bundled Plex/Jellyfin targets use the direct `register(...)` call rather than the decorator, so here's the canonical pattern from `app/core/targets/plex.py`:

```python
from src.app.core.targets.base import BaseTarget
from src.app.core.targets.registry import TargetRegistry

TARGET_PLEX = "Plex"  # case-sensitive!

async def _create_plex_target() -> "PlexTarget":
    # Read plex_host / plex_token from the config table and build a connected instance.
    ...

class PlexTarget(BaseTarget):
    target_id: ClassVar[str] = TARGET_PLEX
    display_name: ClassVar[str] = TARGET_PLEX

    async def search_library(self, *, title, artist, album) -> list[dict]: ...
    async def get_playlist_details(self, playlist_id: str) -> dict | None: ...
    async def create_playlist(self, name: str, item_ids: list[str]) -> str: ...

# Register at module load (the @register_target decorator exists too and works).
TargetRegistry.register(TARGET_PLEX, PlexTarget, factory=_create_plex_target)
```

The factory is what reads `plex_host` / `plex_token` from the `config` table and returns a connected `BaseTarget`. Use [`TargetService`][app.services.target.TargetService] for construction. Note that `TargetService` does **not** cache the constructed instance today — every call to `get_target_async(target_id)` builds a fresh instance via the factory.

### Built-in targets

| ID | Module | Notes |
|----|--------|-------|
| `Plex` | [`app.core.targets.plex`][app.core.targets.plex] | Uses `plexapi`. SSO-driven setup via `app.auth.router`. Registered with `TargetRegistry.register(TARGET_PLEX, PlexTarget, factory=_create_plex_target)`. |
| `Jellyfin` | [`app.core.targets.jellyfin`][app.core.targets.jellyfin] | Uses Jellyfin's REST API. Registered the same way with `TARGET_JELLYFIN`. |

!!! note "Case-sensitive target IDs"
    Both target IDs are **PascalCase** — `Plex` and `Jellyfin`, defined in `src/app/constants.py` as `TARGET_PLEX` and `TARGET_JELLYFIN`. The matching constants are case-sensitive.

### Adding a new target

1. Subclass [`BaseTarget`][app.core.targets.base.BaseTarget].
2. Implement `search_library(...)`, `get_playlist_details(...)`, `create_playlist(...)`, etc. See the `plex.py` reference for the full set of methods to override.
3. Write an `async def _create_your_target() -> YourTarget` factory that reads its config from the DB.
4. Register via `TargetRegistry.register(TARGET_ID, YourTarget, factory=_create_your_target)` at module load time (see `plex.py` for the pattern). The `@register_target` decorator also exists and works — pick whichever fits your style.
5. Add a "Connect" UI flow (or expose a settings API endpoint) that writes the target's config to the `config` table.

The new target shows up in the **Setup wizard** immediately.

## URL detection

`SourceRegistry.detect(url)` walks all registered sources and returns the first whose `supports_url(url)` returns `True`. The web UI uses this to pre-select the source when you paste a playlist URL.

## Single source of truth

Both registries are class-level (`_sources`, `_targets`). That means:

- **Import side effects matter.** A source/target module must be imported somewhere that runs at startup — otherwise it won't be registered when a request lands.
- **Test isolation.** In tests, `SourceRegistry._sources.clear()` (and the equivalent for targets) resets state. Pytest fixtures in `tests/` use this.

## Where to look next

- [`app.core.sources`][app.core.sources] — source base + adapters
- [`app.core.targets`][app.core.targets] — target base + adapters
- [`app.services.target`][app.services.target] — lazy target singleton service
- [Sync pipeline](sync-pipeline.md) — how source + target fit together