"""Centralized API router registration.

Imports and exports all API modules for clean app initialization.
Each module owns its own prefix and tags on the router.
"""

from fastapi import FastAPI

from src.app.api.audit import router as audit_router
from src.app.api.chat import router as chat_router
from src.app.api.match_rules import router as match_rules_router
from src.app.api.playlists import router as playlists_router
from src.app.api.plex_server import router as plex_server_router
from src.app.api.schedules import router as schedules_router
from src.app.api.settings import router as settings_router
from src.app.api.targets import router as targets_router
from src.app.auth.router import router as auth_router


def register_routers(app: FastAPI) -> None:
    """Register all API routers with the FastAPI application.

    Args:
        app: FastAPI application instance
    """
    app.include_router(auth_router)
    app.include_router(audit_router)
    app.include_router(chat_router)
    app.include_router(match_rules_router)
    app.include_router(playlists_router)
    app.include_router(plex_server_router)
    app.include_router(schedules_router)
    app.include_router(settings_router)
    app.include_router(targets_router)


__all__ = [
    "register_routers",
    "auth_router",
    "audit_router",
    "chat_router",
    "match_rules_router",
    "playlists_router",
    "plex_server_router",
    "schedules_router",
    "settings_router",
    "targets_router",
]
