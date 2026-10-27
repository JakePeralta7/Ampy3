"""Thin client for the plex.tv API used by the SSO login and setup flow."""

from __future__ import annotations

import logging
from typing import Any

import httpx

from src.app.schemas.auth import PlexResource, PlexResourceConnection

logger = logging.getLogger(__name__)

PLEX_TV_API = "https://plex.tv/api/v2"
PLEX_AUTH_URL = "https://app.plex.tv/auth"
PLEX_PRODUCT = "Ampy3"


def _headers(client_id: str | None = None, token: str | None = None) -> dict[str, str]:
    """Build the headers plex.tv expects for a client/token pair."""
    headers = {"Accept": "application/json"}
    if client_id:
        headers["X-Plex-Client-Identifier"] = client_id
        headers["X-Plex-Product"] = PLEX_PRODUCT
    if token:
        headers["X-Plex-Token"] = token
    return headers


async def create_pin(client_id: str) -> dict[str, Any]:
    """Create a strong PIN for the forwarding login flow."""
    async with httpx.AsyncClient(timeout=10.0) as client:
        resp = await client.post(
            f"{PLEX_TV_API}/pins",
            params={"strong": "true"},
            headers=_headers(client_id),
        )
        resp.raise_for_status()
        return resp.json()


async def exchange_pin(client_id: str, pin_id: int, pin_code: str) -> dict[str, Any]:
    """Poll the PIN for the authenticated user's token payload."""
    async with httpx.AsyncClient(timeout=10.0) as client:
        resp = await client.get(
            f"{PLEX_TV_API}/pins/{pin_id}",
            params={"code": pin_code},
            headers=_headers(client_id),
        )
        resp.raise_for_status()
        return resp.json()


async def fetch_user_profile(auth_token: str) -> dict[str, Any]:
    """Return the authenticated Plex user's profile."""
    async with httpx.AsyncClient(timeout=10.0) as client:
        resp = await client.get(
            f"{PLEX_TV_API}/user",
            headers=_headers(token=auth_token),
        )
        resp.raise_for_status()
        return resp.json()


async def fetch_resources(plex_token: str, client_id: str) -> list[dict[str, Any]]:
    """Return the raw plex.tv resource list visible to *plex_token*."""
    async with httpx.AsyncClient(timeout=15.0) as client:
        resp = await client.get(
            f"{PLEX_TV_API}/resources",
            headers=_headers(client_id, plex_token),
        )
        resp.raise_for_status()
        return resp.json() or []


def build_auth_url(client_id: str, pin_code: str, forward_url: str) -> str:
    """Build the plex.tv forwarding URL the browser is redirected to."""
    return (
        f"{PLEX_AUTH_URL}#?"
        f"clientID={client_id}&"
        f"code={pin_code}&"
        f"forwardUrl={forward_url}&"
        f"context%5Bdevice%5D%5Bproduct%5D={PLEX_PRODUCT}"
    )


def media_server_resources(raw: list[dict[str, Any]]) -> list[PlexResource]:
    """Map the raw resource payload to the servers the UI may offer."""
    servers = []
    for resource in raw or []:
        if resource.get("product") != "Plex Media Server":
            continue
        connections = [
            PlexResourceConnection(
                uri=conn["uri"],
                local=conn.get("local", False),
                relay=conn.get("relay", False),
                status=conn.get("status", 0),
            )
            for conn in resource.get("connections", [])
        ]
        if not connections:
            continue
        servers.append(
            PlexResource(
                name=resource.get("name", ""),
                client_identifier=resource.get("clientIdentifier", ""),
                connections=connections,
                owned=resource.get("owned", True),
                product=resource.get("product", ""),
                product_version=resource.get("productVersion", ""),
            )
        )
    return servers


def find_resource(
    raw: list[dict[str, Any]], client_identifier: str
) -> tuple[str, list[dict[str, Any]]]:
    """Return ``(access_token, connections)`` for the selected server."""
    for resource in raw or []:
        if resource.get("clientIdentifier") == client_identifier:
            return resource.get("accessToken", ""), resource.get("connections", [])
    return "", []


def candidate_server_urls(server_url: str, connections: list[dict[str, Any]]) -> list[str]:
    """Return the submitted URL followed by the server's advertised URLs (deduplicated)."""
    urls = [server_url]
    for conn in connections:
        uri = str(conn.get("uri", "")).rstrip("/")
        if uri and uri != server_url:
            urls.append(uri)
    # Deduplicate preserving order
    return list(dict.fromkeys(urls))
