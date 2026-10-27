"""Shared utility for parsing trusted proxies configuration."""

import ipaddress
import json
import logging
from typing import Any

logger = logging.getLogger(__name__)


def parse_trusted_proxies(value: Any) -> list[str]:
    """Parse trusted proxies from comma-separated string or JSON array.

    Validates each entry as a valid CIDR or IP address.

    Args:
        value: String (comma-separated or JSON array) or list of strings

    Returns:
        List of validated CIDR/IP strings
    """
    if not isinstance(value, str):
        if isinstance(value, list):
            return [str(v).strip() for v in value if str(v).strip()]
        return value

    raw = value.strip()
    if not raw:
        return []

    if raw.startswith("["):
        try:
            parsed = json.loads(raw)
        except ValueError:
            logger.warning("trusted_proxies is not valid JSON — falling back to a plain list")
        else:
            items = [str(item).strip() for item in parsed if str(item).strip()]
            return _validate_cidr_items(items)

    items = [part.strip() for part in raw.split(",") if part.strip()]
    return _validate_cidr_items(items)


def _validate_cidr_items(items: list[str]) -> list[str]:
    """Validate a list of CIDR/IP strings."""
    validated = []
    for item in items:
        try:
            # Accept both CIDR (192.168.1.0/24) and bare IPs (192.168.1.1)
            # ip_network with strict=False accepts bare IPs as /32 or /128
            ipaddress.ip_network(item, strict=False)
            validated.append(item)
        except ValueError:
            logger.warning("Invalid CIDR in trusted_proxies, ignoring: %s", item)
    return validated
