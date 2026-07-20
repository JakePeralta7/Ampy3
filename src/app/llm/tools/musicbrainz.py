from __future__ import annotations

from langchain_core.tools import tool

from src.app.core.musicbrainz import MusicBrainzResolver

mb = MusicBrainzResolver()


@tool
async def search_mb_by_tag(tag: str, entity: str = "artist") -> list[dict]:
    """Search MusicBrainz by genre/style tag to find ARTISTS.

    Use this to find artists by genre (e.g. "chillout", "ambient", "downtempo",
    "lo-fi", "jazz", "electronic"). This is the best way to discover music in a
    particular style when you don't have a specific artist in mind.

    For playlist creation, always use entity="artist" (the default). Do NOT search
    for "recording" by tag — recordings found this way rarely match Plex library
    entries. Instead, find artists first, then search Plex by artist name.

    Args:
        tag: The genre tag (e.g. "chillout", "ambient", "lo-fi", "downtempo")
        entity: What to search. Always use "artist" for playlist creation.
            Can also be "release" or "recording" for non-playlist research. (default: "artist")
    """
    return mb.search_by_tag(tag, entity)


@tool
async def search_mb_artists(query: str) -> list[dict]:
    """Search MusicBrainz for artists by name.

    Use this to find artist details, get their MusicBrainz ID, and explore their discography.
    Returns artist info including id, name, type, country, and genre tags.

    Args:
        query: Artist name to search for (e.g. "Queen", "Radiohead")
    """
    return mb.search_artists(query)


@tool
async def search_mb_releases(query: str, artist: str = "") -> list[dict]:
    """Search MusicBrainz for releases/albums by title and optionally artist.

    Use this to find albums, EPs, and other releases when researching music.
    Returns release details including id, title, artist, release date, and track count.

    Args:
        query: Release title or search terms (e.g. "A Night at the Opera")
        artist: Optional artist name to narrow results (e.g. "Queen")
    """
    return mb.search_releases(query, artist)


@tool
async def search_mb_recordings(query: str, artist: str = "") -> list[dict]:
    """Search MusicBrainz for recordings/tracks by title and optionally artist.

    Use this to find specific songs and their metadata when researching music.
    Returns recording details including id, title, artist, and duration.

    Args:
        query: Recording title to search for (e.g. "Bohemian Rhapsody")
        artist: Optional artist name to narrow results (e.g. "Queen")
    """
    return mb.search_recordings(query, artist)


@tool
async def get_mb_artist_releases(artist_mbid: str) -> list[dict]:
    """Get all releases for an artist using their MusicBrainz ID.

    Use this to explore an artist's full discography after finding their ID via search_mb_artists.
    Returns a list of releases with title, date, track count, and type (album, single, etc.).

    Args:
        artist_mbid: The MusicBrainz artist ID (e.g. "0383dadf-2a4e-4d10-a46a-e9e041da8eb3")
    """
    return mb.get_artist_releases(artist_mbid)


@tool
async def get_mb_release_tracks(release_mbid: str) -> list[dict]:
    """Get all tracks in a release/album by its MusicBrainz ID.

    Use this to see the full track listing of an album after finding its ID via search_mb_releases.
    Returns tracks with id, title, artist, duration, and track number.

    Args:
        release_mbid: The MusicBrainz release ID (e.g. "b2c6cc82-5ea1-4d23-8c5b-4d3e5c5b5a5b")
    """
    return mb.get_release_tracks(release_mbid)
