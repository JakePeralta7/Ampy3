from __future__ import annotations

from typing import Any

from langchain_core.tools import tool

from src.app.constants import DEFAULT_SOURCE, DEFAULT_TARGET
from src.app.services import get_sync_target
from src.app.services.audit import log_event_sync
from src.app.worker.tasks import sync_playlists_task


@tool
async def search_plex_playlists(query: str) -> list[dict[str, Any]]:
    """Search Plex Media Server for playlists matching the given query text."""
    target = await get_sync_target(DEFAULT_TARGET)
    return await target.search_playlists(query)


@tool
async def list_plex_playlists() -> str:
    """List all playlists available in the user's Plex library."""
    target = await get_sync_target(DEFAULT_TARGET)
    results = await target.search_playlists("")
    if not results:
        return "No playlists found in your Plex library."
    lines = [f"- {p.get('title', p.get('name', 'Unnamed'))}" for p in results]
    return "Your Plex playlists:\n" + "\n".join(lines)


@tool
async def sync_playlist_to_plex(playlist_url: str, source: str = DEFAULT_SOURCE) -> str:
    """Trigger a background sync job to import a playlist into Plex.

    Requires a full YouTube Music playlist URL (e.g. https://music.youtube.com/playlist?list=PL...).
    Use search_youtube_music first to find the URL.

    Args:
        playlist_url: Full YouTube Music playlist URL to sync.
        source: The source platform (default: youtube_music).
    """
    task = sync_playlists_task.delay(playlist_url, source, DEFAULT_TARGET)  # type: ignore[attr-defined]
    return f"Sync started. Task ID: {task.id}. Poll /v1/status/{task.id} for progress."


@tool
async def search_plex_library(
    query: str = "", artist: str = "", genre: str = ""
) -> list[dict[str, Any]]:
    """Search the user's Plex music library for tracks by title, artist, or genre.

    Use this to find tracks that already exist in Plex when researching music or creating playlists.
    At least one parameter should be provided. Returns track details including item_id, title,
    artist_name, album_name, and duration_ms.

    Args:
        query: Track title to search for (e.g. "Bohemian Rhapsody").
            Leave empty to search by artist/genre only.
        artist: Optional artist name to narrow results (e.g. "Queen")
        genre: Optional genre to filter by (e.g. "Electronic",
            "Jazz", "Rock"). Searches Plex genre tags.
    """
    target = await get_sync_target(DEFAULT_TARGET)
    return await target.search_library(title=query, artist=artist, genre=genre)


@tool
async def create_plex_playlist(title: str, track_descriptions: list[dict[str, Any]]) -> str:
    """Create a new playlist in Plex from a list of track descriptions or item_ids.

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

    from src.app.core.matching import _best_match, _extract_primary_artist

    target = await get_sync_target(DEFAULT_TARGET)
    matched_items = []
    unmatched_tracks = []

    for desc in track_descriptions:
        if desc.get("plex_id"):
            matched_items.append(
                {
                    "item_id": desc["plex_id"],
                    "title": desc.get("title", ""),
                    "artist_name": desc.get("artist", ""),
                }
            )
        else:
            artist = _extract_primary_artist(desc.get("artist", ""))
            results = await target.search_library(
                title=desc.get("title", ""),
                artist=artist,
                album=desc.get("album", ""),
            )
            if results:
                matched_items.append(results[0])
            else:
                all_library = await target.search_library(artist=artist)
                fuzzy_match = _best_match(desc.get("title", ""), all_library, threshold=0.70)
                if fuzzy_match:
                    matched_items.append(fuzzy_match)
                else:
                    unmatched_tracks.append(
                        f"{desc.get('artist', 'Unknown')} - {desc.get('title', 'Unknown')}"
                    )

    if not matched_items:
        return "No matching tracks found in your Plex library for any of the given descriptions."

    existing = await target.get_playlist_by_name(title)
    if existing:
        success = await target.update_playlist(existing["rating_key"], matched_items)
        if not success:
            return f"Failed to update existing playlist '{title}'."
        result_msg = (
            f"Updated existing playlist '{title}' with "
            f"{len(matched_items)}/{len(track_descriptions)}"
            f" tracks matched."
        )
    else:
        playlist_id = await target.create_playlist(title, matched_items)
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
async def add_tracks_to_plex_playlist(
    playlist_id: str, track_descriptions: list[dict[str, Any]]
) -> str:
    """Add tracks to an existing Plex playlist.

    For each track description, searches the Plex library for a matching track
    and adds it to the specified playlist.

    Args:
        playlist_id: The Plex playlist rating_key to add tracks to
        track_descriptions: List of dicts with at minimum 'title', optionally 'artist'.
            Example: [{"title": "Bohemian Rhapsody", "artist": "Queen"}, ...]
    """
    from src.app.core.matching import _extract_primary_artist

    target = await get_sync_target(DEFAULT_TARGET)
    matched_item_ids = []
    for desc in track_descriptions:
        artist = _extract_primary_artist(desc.get("artist", ""))
        results = await target.search_library(
            title=desc.get("title", ""),
            artist=artist,
            album=desc.get("album", ""),
        )
        if results:
            matched_item_ids.append(results[0]["item_id"])

    if not matched_item_ids:
        return "No matching tracks found in your Plex library for any of the given descriptions."

    added = await target.add_items_to_playlist(playlist_id, matched_item_ids)

    log_event_sync(
        event_type="plex.playlist_items_added",
        resource_type="playlist",
        resource_id=playlist_id,
        summary=f"LLM added {added}/{len(track_descriptions)} tracks to playlist {playlist_id}",
    )

    return f"Added {added}/{len(track_descriptions)} tracks to playlist."


@tool
async def get_plex_playlist_tracks(playlist_id: str) -> list[dict[str, Any]]:
    """Retrieve all tracks in a Plex playlist.

    Args:
        playlist_id: The Plex playlist rating_key
    """
    target = await get_sync_target(DEFAULT_TARGET)
    return await target.get_items_in_playlist(playlist_id)


@tool
async def delete_plex_playlist(playlist_id: str) -> str:
    """Delete a playlist from Plex by its ID.

    Args:
        playlist_id: The Plex playlist rating_key to delete
    """
    target = await get_sync_target(DEFAULT_TARGET)
    success = await target.delete_playlist(playlist_id)

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
async def get_sync_status(task_id: str) -> dict[str, Any]:
    """Check the current status of a previously triggered sync task.

    Args:
        task_id: The Celery task ID returned from sync_playlist_to_plex.
    """
    from celery.result import AsyncResult

    from src.app.worker.app import celery_app as app

    result = AsyncResult(task_id, app=app)
    return {
        "task_id": task_id,
        "status": result.status,
        "ready": result.ready(),
        "failed": result.failed(),
        "result": result.result if result.ready() else None,
    }
