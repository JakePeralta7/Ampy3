"""Plex SSO authentication routes.

Implements the PIN-based forwarding flow documented at
https://forums.plex.tv/t/authenticating-with-plex/609370
"""

import logging
import uuid
from datetime import UTC, datetime
from typing import Any

import httpx
from fastapi import APIRouter, Depends, HTTPException, Request
from fastapi.responses import JSONResponse, RedirectResponse
from pydantic import BaseModel

from src.app.auth.dependencies import SESSION_COOKIE, get_current_user
from src.app.auth.tokens import create_session, destroy_session
from src.app.db import AsyncSessionLocal
from src.app.models import Config
from src.app.services.audit import log_event
from src.app.settings import settings

logger = logging.getLogger(__name__)

router = APIRouter(prefix="/api/auth", tags=["auth"])

PLEX_TV_API = "https://plex.tv/api/v2"
PLEX_AUTH_URL = "https://app.plex.tv/auth"

_client_id_cache: str | None = None


async def _get_client_id() -> str:
    """Return a stable Plex client identifier (persisted in the config table)."""
    global _client_id_cache  # noqa: PLW0603
    if _client_id_cache:
        return _client_id_cache

    async with AsyncSessionLocal() as session:
        from sqlalchemy import select

        row = (
            await session.execute(select(Config).where(Config.key == "plex_client_id"))
        ).scalar_one_or_none()

        if row:
            _client_id_cache = row.value
            return _client_id_cache

        new_id = str(uuid.uuid4())
        session.add(Config(key="plex_client_id", value=new_id))
        await session.commit()
        _client_id_cache = new_id
        return new_id


async def _get_owner_id() -> str | None:
    """Return the stored owner plex_user_id, or ``None`` if unregistered."""
    async with AsyncSessionLocal() as session:
        from sqlalchemy import select

        row = (
            await session.execute(select(Config).where(Config.key == "owner_plex_user_id"))
        ).scalar_one_or_none()
        return row.value if row else None


async def get_owner_plex_token() -> str | None:
    """Return the owner's Plex token, or ``None`` if not stored."""
    async with AsyncSessionLocal() as session:
        from sqlalchemy import select

        row = (
            await session.execute(select(Config).where(Config.key == "owner_plex_token"))
        ).scalar_one_or_none()
        return row.value if row else None


async def get_plex_server_url() -> str | None:
    """Return the configured Plex Media Server URL, or ``None``."""
    async with AsyncSessionLocal() as session:
        from sqlalchemy import select

        row = (
            await session.execute(select(Config).where(Config.key == "plex_server_url"))
        ).scalar_one_or_none()
        return row.value if row else None


def _cookie_secure() -> bool:
    """Cookies must always use the Secure flag when auth is required."""
    return settings.require_auth or settings.app_env == "production"


# ── Schemas ───────────────────────────────────────────────────────────


class PlexResourceConnection(BaseModel):
    uri: str
    local: bool = False
    relay: bool = False
    status: int = 0


class PlexResource(BaseModel):
    name: str
    client_identifier: str
    connections: list[PlexResourceConnection]
    access_token: str
    owned: bool = False
    product: str = ""
    product_version: str = ""


class PlexResourcesResponse(BaseModel):
    servers: list[PlexResource]


class PlexSetupRequest(BaseModel):
    server_url: str
    token: str


# ── Routes ──────────────────────────────────────────────────────────────


@router.get("/plex/login")
async def plex_login(request: Request):
    """Begin Plex OAuth: create a PIN and redirect the user to plex.tv."""
    if not settings.require_auth:
        return RedirectResponse("/")

    client_id = await _get_client_id()

    async with httpx.AsyncClient(timeout=10.0) as client:
        resp = await client.post(
            f"{PLEX_TV_API}/pins",
            params={"strong": "true"},
            headers={
                "Accept": "application/json",
                "X-Plex-Client-Identifier": client_id,
                "X-Plex-Product": "Ampy3",
            },
        )
        resp.raise_for_status()
        pin = resp.json()

    pin_id = pin["id"]
    pin_code = pin["code"]

    base = settings.app_url.rstrip("/")
    forward_url = f"{base}/api/auth/plex/callback"

    auth_url = (
        f"{PLEX_AUTH_URL}#?"
        f"clientID={client_id}&"
        f"code={pin_code}&"
        f"forwardUrl={forward_url}&"
        f"context%5Bdevice%5D%5Bproduct%5D=Ampy3"
    )

    resp = RedirectResponse(auth_url)
    resp.set_cookie(
        "plex_pin_data",
        f"{pin_id}:{pin_code}",
        max_age=300,
        httponly=True,
        secure=_cookie_secure(),
        samesite="lax",
        path="/",
    )
    return resp


@router.get("/plex/callback")
async def plex_callback(
    request: Request,
):
    """Handle the OAuth callback from plex.tv."""
    if not settings.require_auth:
        return RedirectResponse("/")

    # ── 1. Retrieve the PIN credentials from the temporary cookie ──────
    pin_data = request.cookies.get("plex_pin_data") if request else None
    if not pin_data:
        return RedirectResponse("/login?error=missing_pin")

    try:
        pin_id_str, pin_code = pin_data.split(":", 1)
        pin_id = int(pin_id_str)
    except ValueError, TypeError:
        return RedirectResponse("/login?error=invalid_pin")

    # ── 2. Exchange the PIN for the user's access token ───────────────
    client_id = await _get_client_id()
    try:
        async with httpx.AsyncClient(timeout=10.0) as client:
            resp = await client.get(
                f"{PLEX_TV_API}/pins/{pin_id}",
                params={"code": pin_code},
                headers={
                    "Accept": "application/json",
                    "X-Plex-Client-Identifier": client_id,
                    "X-Plex-Product": "Ampy3",
                },
            )
            resp.raise_for_status()
            auth_token = resp.json().get("authToken")
    except Exception:
        logger.exception("Failed to exchange Plex PIN")
        return RedirectResponse("/login?error=token_exchange_failed")

    if not auth_token:
        return RedirectResponse("/login?error=auth_failed")

    # ── 3. Fetch user profile ─────────────────────────────────────────
    try:
        async with httpx.AsyncClient(timeout=10.0) as client:
            resp = await client.get(
                f"{PLEX_TV_API}/user",
                headers={
                    "Accept": "application/json",
                    "X-Plex-Token": auth_token,
                },
            )
            resp.raise_for_status()
            user_data = resp.json()
    except Exception:
        logger.exception("Failed to fetch Plex user profile")
        return RedirectResponse("/login?error=profile_fetch_failed")

    plex_user_id = str(user_data.get("id", ""))
    username = user_data.get("username", "")
    email = user_data.get("email")
    thumb = user_data.get("thumb")

    # ── 4. Owner check (first user = owner) ───────────────────────────
    owner_id = await _get_owner_id()

    if owner_id is None:
        # First user — register as owner and persist their Plex token
        async with AsyncSessionLocal() as session:
            session.add(Config(key="owner_plex_user_id", value=plex_user_id))
            session.add(Config(key="owner_plex_token", value=auth_token))
            await session.commit()
        logger.info("Owner registered: %s (%s)", username, plex_user_id)
        await log_event(
            "owner_registered",
            f"Owner registered: {username} (plex_user_id={plex_user_id})",
            resource_type="user",
            resource_id=plex_user_id,
        )
    elif owner_id != plex_user_id:
        logger.warning("Rejected login from non-owner: %s (%s)", username, plex_user_id)
        await log_event(
            "login_rejected",
            f"Login rejected: {username} (plex_user_id={plex_user_id}) is not the owner",
            resource_type="user",
            resource_id=plex_user_id,
        )
        return RedirectResponse("/login?error=not_authorized")

    # ── 5. Create server-side session ─────────────────────────────────
    user_profile = {
        "plex_user_id": plex_user_id,
        "username": username,
        "email": email,
        "thumb": thumb,
    }
    cookie_value = await create_session(
        user_data=user_profile,
        plex_token=auth_token,
        secret=settings.secret_key,
        ttl_hours=settings.session_ttl_hours,
    )

    resp = RedirectResponse("/")
    resp.set_cookie(
        SESSION_COOKIE,
        cookie_value,
        max_age=settings.session_ttl_hours * 3600,
        httponly=True,
        secure=_cookie_secure(),
        samesite="lax",
        path="/",
    )
    # Clear the temporary PIN cookie
    resp.delete_cookie("plex_pin_data", path="/")

    logger.info("User logged in: %s (%s)", username, plex_user_id)
    await log_event(
        "login",
        f"Login: {username} (plex_user_id={plex_user_id})",
        resource_type="user",
        resource_id=plex_user_id,
    )
    return resp


@router.get("/plex/resources", response_model=PlexResourcesResponse)
async def plex_resources(
    user: dict[str, Any] = Depends(get_current_user),  # noqa: B008
):
    """Discover the authenticated user's Plex Media Servers.

    Calls the Plex.tv resources API to list servers the user has access to.
    """
    plex_token = user.get("plex_token", "")
    if not plex_token:
        raise HTTPException(status_code=400, detail="No Plex token available")

    client_id = await _get_client_id()

    async with httpx.AsyncClient(timeout=15.0) as client:
        resp = await client.get(
            f"{PLEX_TV_API}/resources",
            headers={
                "Accept": "application/json",
                "X-Plex-Token": plex_token,
                "X-Plex-Client-Identifier": client_id,
            },
        )
        resp.raise_for_status()
        raw = resp.json()

    servers = []
    for r in raw or []:
        if r.get("product") != "Plex Media Server":
            continue
        connections = [
            PlexResourceConnection(
                uri=c["uri"],
                local=c.get("local", False),
                relay=c.get("relay", False),
                status=c.get("status", 0),
            )
            for c in r.get("connections", [])
        ]
        if not connections:
            continue
        servers.append(
            PlexResource(
                name=r.get("name", ""),
                client_identifier=r.get("clientIdentifier", ""),
                connections=connections,
                access_token=r.get("accessToken", ""),
                owned=r.get("owned", True),
                product=r.get("product", ""),
                product_version=r.get("productVersion", ""),
            )
        )

    return PlexResourcesResponse(servers=servers)


@router.post("/plex/setup")
async def plex_setup(
    body: PlexSetupRequest,
    user: dict[str, Any] = Depends(get_current_user),  # noqa: B008
):
    """Configure the Plex target from a discovered server.

    Saves the selected server URL and token so the PlexTarget factory
    can connect without manual configuration.
    """
    server_url = body.server_url.strip().rstrip("/")
    token = body.token.strip()

    if not server_url or not token:
        raise HTTPException(status_code=400, detail="server_url and token are required")

    async with AsyncSessionLocal() as session:
        from sqlalchemy import select

        for key, value in [("plex_host", server_url), ("plex_token", token)]:
            stmt = select(Config).where(Config.key == key)
            row = (await session.execute(stmt)).scalar_one_or_none()
            if row:
                row.value = value
                row.updated_at = datetime.now(UTC)
            else:
                session.add(Config(key=key, value=value, updated_at=datetime.now(UTC)))

        await session.commit()

    from src.app.services.target import TargetService

    TargetService.reset()

    await log_event(
        "plex_target_configured",
        f"Plex target configured via SSO setup: {server_url}",
        resource_type="target",
        resource_id="Plex",
    )

    return {"status": "ok"}


@router.get("/me")
async def auth_me(user: dict[str, Any] = Depends(get_current_user)):  # noqa: B008
    """Return the current authenticated user."""
    return {
        "plex_user_id": user["plex_user_id"],
        "username": user["username"],
        "email": user.get("email"),
        "thumb": user.get("thumb"),
        "require_auth": settings.require_auth,
    }


@router.post("/logout")
async def auth_logout(user: dict[str, Any] = Depends(get_current_user)):  # noqa: B008
    """Revoke the session server-side and clear the cookie."""
    session_id = user.get("session_id")
    if session_id:
        await destroy_session(session_id)

    await log_event(
        "logout",
        f"Logout: {user.get('username', 'unknown')}",
        resource_type="user",
        resource_id=user.get("plex_user_id"),
    )
    resp = JSONResponse({"status": "ok"})
    resp.delete_cookie(SESSION_COOKIE, path="/")
    return resp
