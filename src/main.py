"""Main entry point for the Ampy3 API."""

import logging
from contextlib import asynccontextmanager
from pathlib import Path

from fastapi import FastAPI, Request
from fastapi.middleware.cors import CORSMiddleware
from fastapi.responses import FileResponse, JSONResponse
from fastapi.staticfiles import StaticFiles

from src.app.api import register_routers
from src.app.auth.tokens import purge_expired_sessions, verify_session
from src.app.db import init_db
from src.app.llm.ollama import health_check as ollama_health_check
from src.app.services import get_plex_client
from src.app.services.scheduler import SchedulerService
from src.app.settings import settings

logger = logging.getLogger(__name__)
logging.basicConfig(level=logging.INFO, format="%(levelname)s: %(message)s")

PUBLIC_PATHS = {
    "/api/auth/plex/login",
    "/api/auth/plex/callback",
}

SESSION_COOKIE = "ampy3_session"


# ── Lifespan (replaces deprecated on_event) ─────────────────────────────


@asynccontextmanager
async def lifespan(app: FastAPI):
    # Require SECRET_KEY when auth is enabled
    if settings.require_auth and not settings.secret_key:
        msg = (
            "SECRET_KEY must be set when REQUIRE_AUTH=true. "
            'Generate one with: python -c "import secrets; print(secrets.token_hex(32))"'
        )
        raise RuntimeError(msg)

    logger.info("Starting Ampy3 API...")

    # Initialize database
    try:
        await init_db()
        logger.info("Database initialized successfully.")
    except Exception as e:
        logger.warning("Could not initialize database on startup: %s", e)

    # Purge expired sessions on startup
    try:
        await purge_expired_sessions()
    except Exception as e:
        logger.warning("Could not purge expired sessions: %s", e)

    try:
        plex_client = await get_plex_client()
        sections = await plex_client.get_sections()
        if not sections:
            logger.warning("Plex Client started but returned no library sections.")
        else:
            logger.info("Plex Client initialized successfully (%d sections).", len(sections))
    except Exception as e:
        logger.warning("Could not initialize PlexClient on startup: %s", e)

    try:
        tags = await ollama_health_check()
        models = [m["name"] for m in tags.get("models", [])]
        logger.info(
            "Ollama connected: %s (models: %s)",
            settings.ollama_host,
            ", ".join(models) or "none pulled",
        )
    except Exception as e:
        logger.warning("Ollama health check failed (%s): %s", settings.ollama_host, e)

    try:
        await SchedulerService.start()
        logger.info("APScheduler started - scheduled syncs are now active")
    except Exception as e:
        logger.warning("Failed to start APScheduler: %s", e)

    yield

    # Shutdown
    try:
        await SchedulerService.stop()
    except Exception as e:
        logger.warning("Failed to stop APScheduler: %s", e)

    plex_client = await get_plex_client()
    await plex_client.close()
    logger.info("Ampy3 API shut down gracefully.")


# ── App ─────────────────────────────────────────────────────────────────

docs_url = "/docs" if settings.app_env != "production" else None
redoc_url = "/redoc" if settings.app_env != "production" else None
openapi_url = "/openapi.json" if settings.app_env != "production" else None

app = FastAPI(
    title="Ampy3 Sync API",
    description=(
        "Sync playlists from YouTube Music (and other sources) to Plex "
        "using MusicBrainz metadata IDs and AI-powered match rules."
    ),
    version="1.0.0",
    redirect_slashes=False,
    docs_url=docs_url,
    redoc_url=redoc_url,
    openapi_url=openapi_url,
    lifespan=lifespan,
    openapi_tags=[
        {"name": "auth", "description": "Plex SSO authentication"},
        {"name": "chat", "description": "AI chat agent invocations and conversation history"},
        {
            "name": "playlists",
            "description": "Plex playlist listing, search, sync, and track management",
        },
        {
            "name": "scheduled-syncs",
            "description": "Scheduled sync CRUD and manual trigger actions",
        },
        {"name": "match-rules", "description": "Music matching rule configuration and testing"},
        {"name": "settings", "description": "Runtime configuration (Plex, Ollama, yt-dlp)"},
        {"name": "audit", "description": "Audit log querying"},
    ],
)

# ── CORS ────────────────────────────────────────────────────────────────

if settings.require_auth:
    if not settings.app_url:
        raise RuntimeError("APP_URL must be set when REQUIRE_AUTH=true")
    cors_origins = [settings.app_url]
else:
    cors_origins = ["*"]

app.add_middleware(
    CORSMiddleware,
    allow_origins=cors_origins,
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)


# ── Session middleware ──────────────────────────────────────────────────


@app.middleware("http")
async def session_middleware(request: Request, call_next):
    """Extract and validate the session cookie on every request.

    When ``REQUIRE_AUTH=false`` this is a no-op.  When enabled, every
    ``/api/*`` request (except public paths) must carry a valid signed
    cookie.  The decoded user dict is stored on ``request.state.user``.
    """
    request.state.user = None

    if not settings.require_auth:
        return await call_next(request)

    path = request.url.path

    # Only enforce on API routes
    if not path.startswith("/api/"):
        return await call_next(request)

    # Allow public auth endpoints
    if path in PUBLIC_PATHS:
        return await call_next(request)

    token = request.cookies.get(SESSION_COOKIE)
    if not token:
        return JSONResponse(status_code=401, content={"detail": "unauthenticated"})

    user = await verify_session(token, settings.secret_key)
    if user is None:
        return JSONResponse(status_code=401, content={"detail": "unauthenticated"})

    request.state.user = user
    return await call_next(request)


# ── Routers ─────────────────────────────────────────────────────────────

register_routers(app)

# ── Static files / SPA ──────────────────────────────────────────────────

web_dist_path = Path(__file__).parent.parent / "web" / "dist"
if web_dist_path.exists():
    app.mount("/assets", StaticFiles(directory=web_dist_path / "assets"), name="assets")

    @app.get("/{path:path}")
    async def serve_spa(path: str):
        """Serve SPA - return index.html for any non-API routes."""
        if path.startswith("api/"):
            raise JSONResponse(status_code=404, content={"detail": "Not found"})
        file_path = web_dist_path / path
        if file_path.is_file():
            return FileResponse(file_path)
        return FileResponse(
            web_dist_path / "index.html",
            headers={"Cache-Control": "no-store, no-cache, must-revalidate"},
        )
