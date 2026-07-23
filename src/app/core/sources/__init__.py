"""Music platform source adapters.

All modules in this package are auto-imported so that ``@register_source``
decorators fire on startup.
"""
import importlib
import pkgutil

# Auto-import all modules to trigger @register_source registrations
for _importer, _name, _is_pkg in pkgutil.iter_modules(__path__):
    if not _is_pkg:
        importlib.import_module(f"{__name__}.{_name}")
