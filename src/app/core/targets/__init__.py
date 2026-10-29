"""Sync target adapters for media servers (Plex, Jellyfin, Navidrome, etc.).

All modules in this package are auto-imported so that ``@register_target``
decorators fire on startup.
"""

import importlib
import pkgutil

from src.app.core.targets.base import BaseTarget  # noqa: F401
from src.app.core.targets.registry import TargetRegistry, register_target  # noqa: F401

# Auto-import all modules *and* subpackages to trigger @target_factory /
# @register_target registrations. Targets may be a single module (base,
# plex_errors, ...) or a package (plex/, jellyfin/); skipping packages here
# leaves the registry empty, so never filter on ``_is_pkg``.
for _importer, _name, _is_pkg in pkgutil.iter_modules(__path__):
    importlib.import_module(f"{__name__}.{_name}")
