"""Explore content discovery system.

Plugins source discoverable music content (new releases, charts, moods)
from various platforms.  Auto-import ensures ``@register_explore_provider``
decorators fire at startup.
"""

import importlib
import pkgutil

# Import providers sub-package to trigger @register_explore_provider decorators
import src.app.core.explore.providers  # noqa: F401
from src.app.core.explore.base import ExploreProvider
from src.app.core.explore.models import ExploreItem, ExploreItemType, MoodCategory
from src.app.core.explore.registry import ExploreRegistry, register_explore_provider

for _importer, _name, _is_pkg in pkgutil.iter_modules(__path__):
    if not _is_pkg:
        importlib.import_module(f"{__name__}.{_name}")

__all__ = [
    "ExploreItem",
    "ExploreItemType",
    "ExploreProvider",
    "ExploreRegistry",
    "MoodCategory",
    "register_explore_provider",
]
