"""Helpers for the stored YouTube Music (ytmusicapi) authentication payload.

The browser headers JSON pasted in the Sources UI is stored in the ``config``
table under the ``ytmusic_auth`` key. These helpers load it at the point of
use (mirroring the Plex/Jellyfin target factories) and normalise it into the
flat headers dict that ``ytmusicapi`` accepts directly, so no temp file on
disk is required (avoiding container permission issues).
"""

from __future__ import annotations

import json
import logging
from typing import Any

from ytmusicapi import YTMusic

from src.app.settings import settings

logger = logging.getLogger(__name__)


def _stored_ytmusic_auth() -> str:
    """Return the auth payload from the DB ``config`` table, if any.

    Returns ``""`` when the row is absent or the DB is unreachable, so
    callers can fall back to the env-seeded singleton.
    """
    from sqlalchemy import select

    from src.app.db import SessionLocal
    from src.app.models import Config

    db = SessionLocal()
    try:
        result = db.execute(select(Config).where(Config.key == "ytmusic_auth"))
        row = result.scalar_one_or_none()
        if row is not None:
            return row.value or ""
    except Exception:
        logger.warning("Could not load ytmusic_auth from DB; falling back to env config")
    finally:
        db.close()
    return ""


def _normalize_auth_payload(payload: dict[str, Any]) -> dict[str, Any]:
    """Return the flat headers dict that ``ytmusicapi`` expects.

    ``YTMusic(auth=dict)`` treats the dict as the request headers themselves
    (see ``auth/auth_parse.py``), so a pasted browser ``headers_raw.json`` is
    already in the right shape. The nested ``{"headers": {...}}`` format is
    still accepted for backward compatibility.
    """
    headers = payload.get("headers")
    if isinstance(headers, dict):
        return headers
    return payload


def get_ytmusic_auth() -> dict[str, Any] | None:
    """Return the configured ytmusicapi auth payload as a flat headers dict.

    Returns ``None`` when unset or malformed. Invalid JSON is logged and
    treated as unauthenticated rather than raised, so extraction degrades to
    the anonymous path instead of breaking syncs.
    """
    raw = _stored_ytmusic_auth()
    if not raw:
        raw = settings.ytmusic_auth
    if not raw:
        return None
    try:
        parsed = json.loads(raw)
    except ValueError:
        logger.warning("Stored YTMusic auth is not valid JSON; treating as unauthenticated")
        return None
    if not isinstance(parsed, dict):
        logger.warning("Stored YTMusic auth is not a JSON object; treating as unauthenticated")
        return None
    return _normalize_auth_payload(parsed)


def validate_ytmusic_auth(raw: str) -> None:
    """Verify a ytmusicapi auth payload by calling a logged-in endpoint.

    Raises ``ValueError`` when the payload is malformed or does not
    authenticate to a YouTube Music account.
    """
    if not raw:
        raise ValueError("No authentication payload provided.")
    try:
        payload = json.loads(raw)
    except ValueError as exc:
        raise ValueError("Authentication payload is not valid JSON.") from exc
    if not isinstance(payload, dict):
        raise ValueError("Authentication payload must be a JSON object.")

    client = YTMusic(auth=_normalize_auth_payload(payload))
    info = client.get_account_info()
    if not info or not info.get("accountName"):
        raise ValueError("The provided credentials do not authenticate to a YouTube Music account.")
