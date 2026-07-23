"""Re-export matching heuristics from :mod:`src.app.core.matching`.

This module is kept for backward compatibility.  New code should import
from ``src.app.core.matching`` directly.
"""

from src.app.core.matching import (  # noqa: F401
    _artist_similarity,
    _best_match,
    _extract_primary_artist,
    _match_titles,
    _normalize_album,
    _normalize_title,
)
