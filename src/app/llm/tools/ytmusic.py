from __future__ import annotations

from langchain_core.tools import tool

from src.app.core.sources.ytmusic import YouTubeMusicSource


@tool
async def search_youtube_music(query: str) -> dict:
    """Search YouTube Music for playlists matching the given query.

    Returns a list of matching playlist URLs and titles.
    """
    try:
        import json
        import subprocess

        cmd = [
            "yt-dlp",
            "--flat-playlist",
            "--dump-json",
            "--no-download",
            "--no-warnings",
            "--ignore-errors",
            f"ytsearch10:{query}",
        ]

        result = subprocess.run(cmd, capture_output=True, text=True, timeout=30)

        if result.returncode != 0 or not result.stdout.strip():
            return {
                "query": query,
                "playlists": [],
                "message": f"No results found for '{query}'",
            }

        import re

        playlists = []
        for line in result.stdout.strip().splitlines():
            if not line.strip():
                continue
            entry = json.loads(line)
            playlist_id = entry.get("playlist_id")
            if not playlist_id:
                continue
            valid_ids = (
                r"^(PL|OLAK5uy_|RD|RDCLAK5uy_|FL|LM|WL|UU|LL)"
                r"[A-Za-z0-9_-]+$"
            )
            if not re.match(valid_ids, playlist_id):
                continue
            playlists.append(
                {
                    "title": entry.get("title", "Unknown"),
                    "playlist_id": playlist_id,
                    "url": f"https://music.youtube.com/playlist?list={playlist_id}",
                    "description": entry.get("description", ""),
                    "track_count": entry.get("playlist_count", 0) or entry.get("n_entries", 0),
                }
            )

        return {
            "query": query,
            "playlists": playlists,
            "total_results": len(playlists),
            "message": f"Found {len(playlists)} playlists matching '{query}'",
        }
    except FileNotFoundError:
        return {
            "error": "yt-dlp not installed",
            "message": "Install yt-dlp to search YouTube Music",
            "query": query,
        }
    except Exception as e:
        return {
            "error": str(e),
            "message": f"Failed to search YouTube Music: {str(e)}",
            "query": query,
        }


@tool
async def get_ytmusic_playlist(playlist_url: str) -> dict:
    """Fetch tracks from a YouTube Music playlist URL.

    Args:
        playlist_url: Full YouTube Music playlist URL
            (e.g. https://music.youtube.com/playlist?list=PL...).
    """
    source = YouTubeMusicSource()
    playlist = await source.get_playlist(playlist_url)
    return {
        "title": playlist.title,
        "source_id": playlist.source_id,
        "source": playlist.source,
        "description": playlist.description,
        "track_count": len(playlist.tracks),
        "tracks": [
            {
                "title": t.title,
                "artist": t.artist_name,
                "album": t.album_name,
                "duration_ms": t.duration_ms,
            }
            for t in playlist.tracks
        ],
    }
