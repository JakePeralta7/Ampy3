"""Metadata providers package.

Auto-registers built-in providers on import.
"""
from src.app.core.providers.base import BaseMetadataProvider  # noqa: F401
from src.app.core.providers.musicbrainz import MusicBrainzProvider  # noqa: F401
from src.app.core.providers.registry import (  # noqa: F401
    ProviderRegistry,
    get_provider,
    register_provider,
)

# Auto-register the MusicBrainz provider on first import.
register_provider(MusicBrainzProvider())
