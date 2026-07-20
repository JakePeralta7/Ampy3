"""Plex SSO authentication routes.

Implements the PIN-based forwarding flow documented at
https://forums.plex.tv/t/authenticating-with-plex/609370
"""

import logging
import secrets
import uuid
from datetime import UTC, datetime, timedelta

import httpx
from fastapi import APIRouter, Depends, Request
from fastapi.responses import JSONResponse, RedirectResponse

from src.app.auth.dependencies import SESSION_COOKIE, get_current_user
from src.app.auth.tokens import sign_session
from src.app.db import AsyncSessionLocal
from src.app.models import AuditLog, Config
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

        row = (await session.execute(
            select(Config).where(Config.key == "plex_client_id")
        )).scalar_one_or_none()

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

        row = (await session.execute(
            select(Config).where(Config.key == "owner_plex_user_id")
        )).scalar_one_or_none()
        return row.value if row else None


async def get_owner_plex_token() -> str | None:
    """Return the owner's Plex token, or ``None`` if not stored."""
    async with AsyncSessionLocal() as session:
        from sqlalchemy import select

        row = (await session.execute(
            select(Config).where(Config.key == "owner_plex_token")
        )).scalar_one_or_none()
        return row.value if row else None


async def get_plex_server_url() -> str | None:
    """Return the configured Plex Media Server URL, or ``None``."""
    async with AsyncSessionLocal() as session:
        from sqlalchemy import select

        row = (await session.execute(
            select(Config).where(Config.key == "plex_server_url")
        )).scalar_one_or_none()
        return row.value if row else None


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
        secure=settings.app_env == "production",
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
    except (ValueError, TypeError):
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

    # ── 5. Sign session cookie ────────────────────────────────────────
    session_payload = {
        "plex_user_id": plex_user_id,
        "username": username,
        "email": email,
        "thumb": thumb,
        "plex_token": auth_token,
    }
    token = sign_session(session_payload, settings.secret_key, settings.session_ttl_hours)

    resp = RedirectResponse("/")
    resp.set_cookie(
        SESSION_COOKIE,
        token,
        max_age=settings.session_ttl_hours * 3600,
        httponly=True,
        secure=settings.app_env == "production",
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


@router.get("/me")
async def auth_me(user: dict = Depends(get_current_user)):  # noqa: B008
    """Return the current authenticated user."""
    return {
        "plex_user_id": user["plex_user_id"],
        "username": user["username"],
        "email": user.get("email"),
        "thumb": user.get("thumb"),
    }


@router.post("/logout")
async def auth_logout(user: dict = Depends(get_current_user)):  # noqa: B008
    """Clear the session cookie."""
    await log_event(
        "logout",
        f"Logout: {user.get('username', 'unknown')}",
        resource_type="user",
        resource_id=user.get("plex_user_id"),
    )
    resp = JSONResponse({"status": "ok"})
    resp.delete_cookie(SESSION_COOKIE, path="/")
    return resp
