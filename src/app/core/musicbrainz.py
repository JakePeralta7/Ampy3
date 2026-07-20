"""MusicBrainz resolver for metadata matching."""
from __future__ import annotations

import logging
import re
import urllib.parse

import requests

logger = logging.getLogger(__name__)


class MusicBrainzResolver:
    """Resolves track names to MusicBrainz recordings/artist/releases via the web service API."""

    BASE_URL = "https://musicbrainz.org/ws/2"

    def __init__(self, user_agent: str = "ampy3/0.1.0"):
        self.headers = {"User-Agent": user_agent}

    def _get(self, endpoint: str, params: dict) -> dict:
        url = f"{self.BASE_URL}/{endpoint}"
        query = params.get('query', '')
        logger.info(f"[MusicBrainz] Searching {endpoint} with query: {query}")
        resp = requests.get(url, params=params, headers=self.headers, timeout=15)
        resp.raise_for_status()
        result = resp.json()
        # Log result counts for debugging
        result_key = f"{endpoint}s" if endpoint != "release" else "releases"
        result_count = len(result.get(result_key, []))
        logger.info(f"[MusicBrainz] Found {result_count} {endpoint} results")
        return result

    def search_recording(
        self, title: str, artist: str | None = None, duration_ms: int | None = None
    ) -> dict | None:
        rec_params = {"recording": title, "fmt": "json", "limit": 5}
        if artist:
            rec_params["arid"] = artist  # placeholder - will use discogs approach

        search_params = {"query": f"rec:{title} {artist or ''}", "fmt": "json"}
        result = self._get("recording", search_params)
        recordings = result.get("recordings", [])
        if not recordings:
            return None

        best = self._best_match(recordings, title, artist, duration_ms)
        return best

    def lookup_artist(self, name: str) -> dict | None:
        result = self._get("artist", {"query": f"artist:{name}", "fmt": "json"})
        artists = result.get("artists", [])
        return artists[0] if artists else None

    def lookup_release_group(
        self, title: str, artist_name: str | None = None
    ) -> dict | None:
        query = f"releasetitle:{title}"
        if artist_name:
            query += f' artist:"{artist_name}"'
        result = self._get("release-group", {"query": query, "fmt": "json"})
        groups = result.get("release-group-list", [])
        return groups[0] if groups else None

    def search_by_tag(self, tag: str, entity: str = "artist", limit: int = 10) -> list[dict]:
        """Search MusicBrainz by genre/style tag.

        Use this to find artists, releases, or recordings by genre (e.g. "chillout",
        "ambient", "downtempo", "lo-fi", "jazz").

        Args:
            tag: The genre tag to search for (e.g. "chillout", "ambient", "lo-fi")
            entity: Type to search: "artist", "release", or "recording"
            limit: Maximum number of results (max 25)

        Returns:
            List of matching entities with id, name, and type-specific fields
        """
        result = self._get(entity, {"query": f"tag:{tag}", "fmt": "json", "limit": min(limit, 25)})
        items = []
        key = f"{entity}s" if entity != "release" else "releases"
        for item in result.get(key, []):
            entry = {"id": item.get("id"), "name": item.get("name") or item.get("title", "")}
            if entity == "artist":
                entry.update({
                    "type": item.get("type"),
                    "country": item.get("country"),
                    "disambiguation": item.get("disambiguation", ""),
                })
            elif entity == "release":
                entry.update({
                    "artist": self._artist_name(item.get("artist-credit")),
                    "date": item.get("date", ""),
                    "track_count": len(item.get("media", [])) > 0 and item["media"][0].get("track-count", 0) or 0,
                })
            elif entity == "recording":
                entry.update({
                    "artist": self._artist_name(item.get("artist-credit")),
                    "duration_ms": item.get("length", 0),
                })
            items.append(entry)
        return items

    def search_artists(self, query: str, limit: int = 10) -> list[dict]:
        """Search MusicBrainz for artists matching the query.

        Args:
            query: Artist name to search for
            limit: Maximum number of results (max 25)

        Returns:
            List of artist dicts with id, name, type, country, disambiguation, tags
        """
        result = self._get("artist", {"query": f"artist:{query}", "fmt": "json", "limit": min(limit, 25)})
        artists = []
        for a in result.get("artists", []):
            artists.append({
                "id": a.get("id"),
                "name": a.get("name"),
                "type": a.get("type"),
                "country": a.get("country"),
                "disambiguation": a.get("disambiguation", ""),
                "tags": [t.get("name") for t in a.get("tags", []) if t.get("name")],
            })
        return artists

    def search_releases(self, query: str, artist: str = "", limit: int = 10) -> list[dict]:
        """Search MusicBrainz for releases/albums matching the query.

        Args:
            query: Release title or search terms
            artist: Optional artist name to narrow results
            limit: Maximum number of results (max 25)

        Returns:
            List of release dicts with id, title, artist, date, track_count
        """
        q = f"release:{query}"
        if artist:
            q += f" AND artist:{artist}"
        result = self._get("release", {"query": q, "fmt": "json", "limit": min(limit, 25)})
        releases = []
        for r in result.get("releases", []):
            releases.append({
                "id": r.get("id"),
                "title": r.get("title"),
                "artist": self._artist_name(r.get("artist-credit")),
                "date": r.get("date", ""),
                "track_count": len(r.get("media", [])) > 0 and r["media"][0].get("track-count", 0) or 0,
                "status": r.get("status"),
            })
        return releases

    def search_recordings(self, query: str, artist: str = "", limit: int = 10) -> list[dict]:
        """Search MusicBrainz for recordings/tracks matching the query.

        Args:
            query: Recording title to search for
            artist: Optional artist name to narrow results
            limit: Maximum number of results (max 25)

        Returns:
            List of recording dicts with id, title, artist, duration_ms
        """
        q = f"recording:{query}"
        if artist:
            q += f" AND artist:{artist}"
        result = self._get("recording", {"query": q, "fmt": "json", "limit": min(limit, 25)})
        recordings = []
        for rec in result.get("recordings", []):
            recordings.append({
                "id": rec.get("id"),
                "title": rec.get("title"),
                "artist": self._artist_name(rec.get("artist-credit")),
                "duration_ms": rec.get("length", 0),
                "video": rec.get("video", False),
            })
        return recordings

    def get_artist_releases(self, artist_mbid: str, limit: int = 25) -> list[dict]:
        """Get all releases for an artist by their MusicBrainz ID.

        Args:
            artist_mbid: MusicBrainz artist ID
            limit: Maximum number of results (max 50)

        Returns:
            List of release dicts with id, title, date, track_count
        """
        result = self._get("artist", {
            "id": artist_mbid,
            "fmt": "json",
            "includes": "releases",
            "limit": min(limit, 50),
        })
        releases = []
        for r in result.get("releases", []):
            releases.append({
                "id": r.get("id"),
                "title": r.get("title"),
                "date": r.get("date", ""),
                "track_count": len(r.get("media", [])) > 0 and r["media"][0].get("track-count", 0) or 0,
                "status": r.get("status"),
                "type": r.get("release-group", {}).get("primary-type") if isinstance(r.get("release-group"), dict) else "",
            })
        return releases

    def get_release_tracks(self, release_mbid: str) -> list[dict]:
        """Get all tracks in a release by its MusicBrainz ID.

        Args:
            release_mbid: MusicBrainz release ID

        Returns:
            List of track dicts with id, title, artist, duration_ms, track_number
        """
        result = self._get("release", {
            "id": release_mbid,
            "fmt": "json",
            "includes": "recordings",
        })
        tracks = []
        for media in result.get("media", []):
            for t in media.get("tracks", []):
                rec = t.get("recording", {})
                if not isinstance(rec, dict):
                    continue
                tracks.append({
                    "id": rec.get("id"),
                    "title": rec.get("title"),
                    "artist": self._artist_name(rec.get("artist-credit")),
                    "duration_ms": rec.get("length", 0),
                    "track_number": t.get("number") or t.get("position", 0),
                })
        return tracks

    def lookup_release(self, mbid: str) -> dict | None:
        try:
            return self._get("release", {"id": mbid, "fmt": "json", "includes": ["recordings", "artists"]})
        except requests.RequestException as exc:
            logger.warning("Failed to lookup release %s: %s", mbid, exc)
            return None

    @staticmethod
    def _artist_name(artist_credit: list | None) -> str:
        """Extract the primary artist name from a MusicBrainz artist-credit list."""
        if not isinstance(artist_credit, list) or not artist_credit:
            return ""
        ac = artist_credit[0]
        if isinstance(ac, dict):
            a = ac.get("artist", {})
            return a.get("name", "") if isinstance(a, dict) else str(a)
        return str(ac) if ac else ""

    @staticmethod
    def _normalize(text: str) -> str:
        text = text.lower().strip()
        text = re.sub(r"[()\[\]\-]", "", text)
        text = re.sub(r"\s+", " ", text)
        return text.strip()

    def _best_match(
        self, recordings: list[dict], title: str, artist: str | None, duration_ms: int | None
    ) -> dict | None:
        norm_title = self._normalize(title)
        norm_artist = self._normalize(artist) if artist else ""
        scored: list[tuple[int, dict]] = []
        for rec in recordings:
            score = 0
            rec_title = rec.get("title", "") or ""
            rec_norm = self._normalize(rec_title)
            if norm_title == rec_norm:
                score += 10
            elif norm_title.startswith(rec_norm) or rec_norm.startswith(norm_title):
                score += 5

            rec_artist = self._artist_name(rec.get("artist-credit"))
            if rec_artist:
                if norm_artist and self._normalize(rec_artist) == norm_artist:
                    score += 5
                elif norm_artist in rec_artist or rec_artist in norm_artist:
                    score += 2

            if duration_ms and rec.get("length"):
                ratio = min(duration_ms, rec["length"]) / max(duration_ms, rec["length"])
                if ratio > 0.90:
                    score += 3

            scored.append((score, rec))

        scored.sort(key=lambda x: x[0], reverse=True)
        return scored[0][1] if scored and scored[0][0] > 0 else (recordings[0] if recordings else None)
