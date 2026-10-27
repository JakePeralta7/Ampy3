"""Plex SSO request/response schemas."""

from pydantic import BaseModel


class PlexResourceConnection(BaseModel):
    uri: str
    local: bool = False
    relay: bool = False
    status: int = 0


class PlexResource(BaseModel):
    name: str
    client_identifier: str
    connections: list[PlexResourceConnection]
    owned: bool = False
    product: str = ""
    product_version: str = ""


class PlexResourcesResponse(BaseModel):
    servers: list[PlexResource]


class PlexSetupRequest(BaseModel):
    server_url: str
    client_identifier: str
