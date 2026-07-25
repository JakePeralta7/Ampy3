"""HMAC-signed session IDs with server-side storage.

The cookie value is: a random session ID + "." + HMAC-SHA256 signature.
All session data (including plex_token) lives in the database — the
cookie never carries sensitive information.
"""

import hashlib
import hmac
import secrets
from datetime import UTC, datetime, timedelta

from sqlalchemy import delete, select

from src.app.db import AsyncSessionLocal
from src.app.models import UserSession

SESSION_ID_BYTES = 32


def _sign(session_id: str, secret: str) -> str:
    """Return an HMAC-SHA256 hex signature for the session ID."""
    return hmac.new(secret.encode(), session_id.encode(), hashlib.sha256).hexdigest()


def create_session_id(secret: str) -> str:
    """Generate a cryptographically random session ID and sign it.

    Returns ``session_id.signature`` — the value stored in the cookie.
    """
    session_id = secrets.token_hex(SESSION_ID_BYTES)
    sig = _sign(session_id, secret)
    return f"{session_id}.{sig}"


def verify_session_id(cookie_value: str, secret: str) -> str | None:
    """Verify the cookie signature and return the session ID, or ``None``."""
    try:
        session_id, sig = cookie_value.rsplit(".", 1)
    except ValueError:
        return None

    expected_sig = _sign(session_id, secret)
    if not hmac.compare_digest(sig, expected_sig):
        return None

    return session_id


async def create_session(
    user_data: dict,
    plex_token: str,
    secret: str,
    ttl_hours: int = 168,
) -> str:
    """Persist session data in the DB and return a signed cookie value."""
    session_id = secrets.token_hex(SESSION_ID_BYTES)

    async with AsyncSessionLocal() as db:
        db.add(
            UserSession(
                id=session_id,
                plex_user_id=user_data["plex_user_id"],
                username=user_data["username"],
                email=user_data.get("email"),
                thumb=user_data.get("thumb"),
                plex_token=plex_token,
                expires_at=datetime.now(UTC) + timedelta(hours=ttl_hours),
            )
        )
        await db.commit()

    sig = _sign(session_id, secret)
    return f"{session_id}.{sig}"


async def verify_session(cookie_value: str, secret: str) -> dict | None:
    """Verify the cookie and load session data from the DB.

    Returns the user dict if the session is valid and not expired,
    ``None`` otherwise.
    """
    session_id = verify_session_id(cookie_value, secret)
    if session_id is None:
        return None

    async with AsyncSessionLocal() as db:
        row = (
            await db.execute(select(UserSession).where(UserSession.id == session_id))
        ).scalar_one_or_none()

        if row is None:
            return None

        if row.expires_at < datetime.now(UTC):
            await db.execute(delete(UserSession).where(UserSession.id == session_id))
            await db.commit()
            return None

        return {
            "plex_user_id": row.plex_user_id,
            "username": row.username,
            "email": row.email,
            "thumb": row.thumb,
            "plex_token": row.plex_token,
            "session_id": row.id,
        }


async def destroy_session(session_id: str) -> None:
    """Delete a session from the database (server-side revocation)."""
    async with AsyncSessionLocal() as db:
        await db.execute(delete(UserSession).where(UserSession.id == session_id))
        await db.commit()


async def purge_expired_sessions() -> None:
    """Remove all expired sessions from the database."""
    async with AsyncSessionLocal() as db:
        await db.execute(delete(UserSession).where(UserSession.expires_at < datetime.now(UTC)))
        await db.commit()
