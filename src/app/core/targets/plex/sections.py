"""Plex library sections operations."""

import logging
import xml.etree.ElementTree as ET
from typing import Any

import httpx

from src.app.core.targets.plex.client import PlexClient

logger = logging.getLogger(__name__)


class PlexSectionsManager:
    """Handles library sections operations for Plex."""

    def __init__(self, client: PlexClient) -> None:
        self._client = client

    async def get_sections(self) -> list[dict[str, Any]]:
        """Lists all library sections available in Plex."""
        try:
            response = await self._client.client.get("/library/sections")
            response.raise_for_status()
            root = ET.fromstring(response.text)
            sections = []
            for dir_elem in root.findall(".//Directory"):
                sections.append(
                    {
                        "key": dir_elem.get("key"),
                        "title": dir_elem.get("title"),
                        "type": dir_elem.get("type"),
                        "agent": dir_elem.get("agent"),
                    }
                )
            return sections
        except httpx.HTTPStatusError as e:
            self._client._log_plex_error("get_sections", e)
            return []
        except ET.ParseError as e:
            logger.error("XML parse error in get_sections: %s", e)
            return []
