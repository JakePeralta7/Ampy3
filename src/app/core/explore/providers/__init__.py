"""Explore provider plugin implementations.

Auto-imports all modules so that ``@register_explore_provider``
decorators in sub-modules fire on startup.
"""

import importlib
import pkgutil

for _importer, _name, _is_pkg in pkgutil.iter_modules(__path__):
    if not _is_pkg:
        importlib.import_module(f"{__name__}.{_name}")
