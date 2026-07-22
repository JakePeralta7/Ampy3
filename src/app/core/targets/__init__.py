"""Sync target adapters for media servers (Plex, Jellyfin, Navidrome, etc.).

All modules in this package are auto-imported so that ``@register_target``
decorators fire on startup.
"""
import importlib
import pkgutil

from src.app.core.targets.base import BaseTarget  # noqa: F401
from src.app.core.targets.registry import TargetRegistry, register_target  # noqa: F401

# Auto-import all modules to trigger @register_target registrations
for _importer, _name, _is_pkg in pkgutil.iter_modules(__path__):
    if not _is_pkg:
        importlib.import_module(f"{__name__}.{_name}")
