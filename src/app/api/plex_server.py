"""Plex Media Server setup endpoints.

Enumerates the owner's Plex servers via plex.tv and lets them save
the server URL to the config table.
"""

import logging
import xml.etree.ElementTree as ET

import httpx
from fastapi import APIRouter, Depends, HTTPException
from pydantic import BaseModel

from src.app.auth.dependencies import get_current_user
from src.app.auth.router import get_owner_plex_token, get_plex_server_url
from src.app.db import AsyncSessionLocal
from src.app.models import Config
from src.app.services.audit import log_event

logger = logging.getLogger(__name__)

router = APIRouter(prefix="/api/plex", tags=["plex-server"])


class PlexServerOut(BaseModel):
    name: str
    host: str
    port: int
    protocol: str
    machine_identifier: str
    local: bool


class SaveServerRequest(BaseModel):
    server_url: str
    plex_token: str | None = None


# ── Enumerate servers ────────────────────────────────────────────────


@router.get("/servers")
async def list_plex_servers(user: dict = Depends(get_current_user)):  # noqa: B008
    """Return the list of Plex Media Servers the owner has access to."""
    token = await get_owner_plex_token()
    if not token:
        return {"servers": []}

    try:
        async with httpx.AsyncClient(timeout=10.0) as client:
            resp = await client.get(
                "https://plex.tv/api/resources",
                params={"includeIPv6": "1"},
                headers={
                    "X-Plex-Token": token,
                },
            )
            resp.raise_for_status()
        root = ET.fromstring(resp.text)
    except Exception as e:
        logger.exception("Failed to enumerate Plex servers from plex.tv")
        raise HTTPException(
            status_code=502,
            detail=f"Failed to reach plex.tv: {e}",
        ) from e

    servers = []
    for device in root.findall(".//Device"):
        if device.get("provides", "") != "server":
            continue
        for conn in device.findall("Connection"):
            servers.append(
                {
                    "name": device.get("name", "Unknown"),
                    "host": conn.get("address", ""),
                    "port": int(conn.get("port", "32400")),
                    "protocol": conn.get("protocol", "http"),
                    "machine_identifier": device.get("machineIdentifier", ""),
                    "local": conn.get("local", "0") == "1",
                }
            )

    return {"servers": servers}


# ── Get / save server config ─────────────────────────────────────────


@router.get("/server")
async def get_server_config(user: dict = Depends(get_current_user)):  # noqa: B008
    """Return the currently configured Plex server URL (if any)."""
    url = await get_plex_server_url()
    return {"server_url": url}


@router.post("/server")
async def save_server_config(
    body: SaveServerRequest,
    user: dict = Depends(get_current_user),  # noqa: B008
):
    """Save the Plex Media Server URL.

    Validates connectivity before persisting.
    """
    token = body.plex_token or await get_owner_plex_token()
    if not token:
        raise HTTPException(status_code=400, detail="Plex token is required")

    url = body.server_url.rstrip("/")

    # Quick connectivity check
    try:
        async with httpx.AsyncClient(timeout=5.0, verify=False) as client:
            resp = await client.get(
                url,
                headers={"X-Plex-Token": token},
            )
            resp.raise_for_status()
            ET.fromstring(resp.text)
    except Exception as e:
        raise HTTPException(
            status_code=400,
            detail=f"Could not connect to Plex server at {url}: {e}",
        ) from e

    async with AsyncSessionLocal() as session:
        from sqlalchemy import select

        row = (
            await session.execute(select(Config).where(Config.key == "plex_server_url"))
        ).scalar_one_or_none()

        if row:
            row.value = url
        else:
            session.add(Config(key="plex_server_url", value=url))

        if body.plex_token and not await get_owner_plex_token():
            token_row = (
                await session.execute(select(Config).where(Config.key == "owner_plex_token"))
            ).scalar_one_or_none()
            if token_row:
                token_row.value = body.plex_token
            else:
                session.add(Config(key="owner_plex_token", value=body.plex_token))

        await session.commit()

    logger.info("Plex server URL saved: %s", url)

    await log_event(
        event_type="plex.server_saved",
        summary=f"Plex server saved: {url}",
        resource_type="plex_server",
        resource_id=url,
    )

    return {"server_url": url}
