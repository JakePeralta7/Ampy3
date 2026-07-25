from __future__ import annotations

from langchain_core.tools import tool

from src.app.services import get_plex_client
from src.app.services.audit import log_event_sync
from src.app.tasks import sync_playlists_task


@tool
async def search_plex_playlists(query: str) -> list[dict]:
    """Search Plex Media Server for playlists matching the given query text."""
    plex_client = await get_plex_client()
    return await plex_client.search_playlists(query)


@tool
async def list_plex_playlists() -> str:
    """List all playlists available in the user's Plex library."""
    plex_client = await get_plex_client()
    results = await plex_client.search_playlists("")
    if not results:
        return "No playlists found in your Plex library."
    lines = [f"- {p.get('title', p.get('name', 'Unnamed'))}" for p in results]
    return "Your Plex playlists:\n" + "\n".join(lines)


@tool
async def sync_playlist_to_plex(playlist_url: str, source: str = "youtube_music") -> str:
    """Trigger a background sync job to import a playlist into Plex.

    Requires a full YouTube Music playlist URL (e.g. https://music.youtube.com/playlist?list=PL...).
    Use search_youtube_music first to find the URL.

    Args:
        playlist_url: Full YouTube Music playlist URL to sync.
        source: The source platform (default: youtube_music).
    """
    task = sync_playlists_task.delay(playlist_url, source)
    return f"Sync started. Task ID: {task.id}. Poll /v1/status/{task.id} for progress."


@tool
async def search_plex_library(query: str = "", artist: str = "", genre: str = "") -> list[dict]:
    """Search the user's Plex music library for tracks by title, artist, or genre.

    Use this to find tracks that already exist in Plex when researching music or creating playlists.
    At least one parameter should be provided. Returns track details including plex_id, title,
    artist_name, album_name, and duration_ms.

    Args:
        query: Track title to search for (e.g. "Bohemian Rhapsody").
            Leave empty to search by artist/genre only.
        artist: Optional artist name to narrow results (e.g. "Queen")
        genre: Optional genre to filter by (e.g. "Electronic",
            "Jazz", "Rock"). Searches Plex genre tags.
    """
    plex_client = await get_plex_client()
    return await plex_client.search_library(title=query, artist=artist, genre=genre)


@tool
async def create_plex_playlist(title: str, track_descriptions: list[dict]) -> str:
    """Create a new playlist in Plex from a list of track descriptions or plex_ids.

    If a track description includes 'plex_id', uses it directly. Otherwise,
    searches the Plex library by title/artist.

    Args:
        title: The name for the new playlist
        track_descriptions: List of dicts with 'title' and 'artist',
            and optionally 'plex_id'.
            Use plex_id when you already know the exact track
            from a prior Plex search.
            Example: [{"title": "Bohemian Rhapsody", "artist": "Queen"},
            {"title": "Bye Bye Bye", "artist": "*NSYNC",
            "plex_id": "97300"}]
    """
    import json

    from src.app.core.plex.matching import _extract_primary_artist, _fuzzy_match

    plex_client = await get_plex_client()
    matched_items = []
    unmatched_tracks = []

    for desc in track_descriptions:
        if desc.get("plex_id"):
            matched_items.append(
                {
                    "plex_id": desc["plex_id"],
                    "title": desc.get("title", ""),
                    "artist_name": desc.get("artist", ""),
                }
            )
        else:
            # Extract primary artist from comma-separated artist names
            artist = _extract_primary_artist(desc.get("artist", ""))
            results = await plex_client.search_library(
                title=desc.get("title", ""),
                artist=artist,
                album=desc.get("album", ""),
            )
            if results:
                matched_items.append(results[0])
            else:
                # Try fuzzy matching as fallback when no exact matches found
                all_library = await plex_client.search_library(artist=artist)
                fuzzy_match = _fuzzy_match(desc.get("title", ""), all_library, threshold=0.70)
                if fuzzy_match:
                    matched_items.append(fuzzy_match)
                else:
                    unmatched_tracks.append(
                        f"{desc.get('artist', 'Unknown')} - {desc.get('title', 'Unknown')}"
                    )

    if not matched_items:
        return "No matching tracks found in your Plex library for any of the given descriptions."

    existing = await plex_client.get_plist_by_name(title)
    if existing:
        success = await plex_client.update_plist_in_place(existing["rating_key"], matched_items)
        if not success:
            return f"Failed to update existing playlist '{title}'."
        result_msg = (
            f"Updated existing playlist '{title}' with "
            f"{len(matched_items)}/{len(track_descriptions)}"
            f" tracks matched."
        )
    else:
        playlist_id = await plex_client.create_plist_from_results(title, matched_items)
        if not playlist_id:
            return "Failed to create playlist."
        result_msg = (
            f"Created playlist '{title}' with "
            f"{len(matched_items)}/{len(track_descriptions)}"
            f" tracks matched."
            f" Playlist ID: {playlist_id}."
        )

    if unmatched_tracks:
        result_msg += "\n\nTracks not found in your Plex library:\n"
        for track in unmatched_tracks:
            result_msg += f"- {track}\n"

    log_event_sync(
        event_type="plex.playlist_created",
        resource_type="playlist",
        summary=f"LLM created/updated playlist '{title}' with {len(matched_items)} tracks",
    )

    return result_msg


@tool
async def add_tracks_to_plex_playlist(playlist_id: str, track_descriptions: list[dict]) -> str:
    """Add tracks to an existing Plex playlist.

    For each track description, searches the Plex library for a matching track
    and adds it to the specified playlist.

    Args:
        playlist_id: The Plex playlist rating_key to add tracks to
        track_descriptions: List of dicts with at minimum 'title', optionally 'artist'.
            Example: [{"title": "Bohemian Rhapsody", "artist": "Queen"}, ...]
    """
    from src.app.core.plex.matching import _extract_primary_artist

    plex_client = await get_plex_client()
    matched_plex_ids = []
    for desc in track_descriptions:
        # Extract primary artist from comma-separated artist names
        artist = _extract_primary_artist(desc.get("artist", ""))
        results = await plex_client.search_library(
            title=desc.get("title", ""),
            artist=artist,
            album=desc.get("album", ""),
        )
        if results:
            matched_plex_ids.append(results[0]["plex_id"])

    if not matched_plex_ids:
        return "No matching tracks found in your Plex library for any of the given descriptions."

    added = await plex_client.add_items_to_playlist(playlist_id, matched_plex_ids)

    log_event_sync(
        event_type="plex.playlist_items_added",
        resource_type="playlist",
        resource_id=playlist_id,
        summary=f"LLM added {added}/{len(track_descriptions)} tracks to playlist {playlist_id}",
    )

    return f"Added {added}/{len(track_descriptions)} tracks to playlist."


@tool
async def get_plex_playlist_tracks(playlist_id: str) -> list[dict]:
    """Retrieve all tracks in a Plex playlist.

    Args:
        playlist_id: The Plex playlist rating_key
    """
    plex_client = await get_plex_client()
    return await plex_client.get_items_in_playlist(playlist_id)


@tool
async def delete_plex_playlist(playlist_id: str) -> str:
    """Delete a playlist from Plex by its ID.

    Args:
        playlist_id: The Plex playlist rating_key to delete
    """
    plex_client = await get_plex_client()
    success = await plex_client.delete_plist(playlist_id)

    log_event_sync(
        event_type="plex.playlist_deleted",
        resource_type="playlist",
        resource_id=playlist_id,
        summary=f"LLM deleted playlist {playlist_id}",
    )

    if success:
        return f"Playlist {playlist_id} deleted successfully."
    return f"Failed to delete playlist {playlist_id}."


@tool
async def get_sync_status(task_id: str) -> dict:
    """Check the current status of a previously triggered sync task.

    Args:
        task_id: The Celery task ID returned from sync_playlist_to_plex.
    """
    from celery.result import AsyncResult

    from src.app.tasks import celery_app as app

    result = AsyncResult(task_id, app=app)
    return {
        "task_id": task_id,
        "status": result.status,
        "ready": result.ready(),
        "failed": result.failed(),
        "result": result.result if result.ready() else None,
    }
