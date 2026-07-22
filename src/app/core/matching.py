"""Title and artist matching heuristics for track resolution.

These are generic string-comparison utilities used by the node-graph match
engine.  They have no dependency on any specific media server.
"""

import logging

logger = logging.getLogger(__name__)


def _normalize_title(title: str) -> str:
    if not title:
        return ""
    title = title.replace("\u2018", "'").replace("\u2019", "'")
    title = title.replace("\u201c", '"').replace("\u201d", '"')
    title = title.replace("\u2013", "-").replace("\u2014", "-")
    return title.lower().strip()


def _extract_primary_artist(artist: str) -> str:
    if not artist:
        return ""
    return artist.strip()


def _normalize_album(album: str) -> str:
    if not album:
        return ""
    album = album.replace("\u2018", "'").replace("\u2019", "'")
    album = album.replace("\u201c", '"').replace("\u201d", '"')
    album = album.replace("\u2013", "-").replace("\u2014", "-")
    return album.lower().strip()


def _match_titles(search: str, candidate: str) -> float:
    """Return similarity score 0.0-1.0 between two song titles.

    Strategy, in order:
    1. Exact normalized match -> 1.0
    2. One is a substring of the other -> 0.9
    3. Token-level Jaccard similarity with subset boost
    """
    s = _normalize_title(search)
    c = _normalize_title(candidate)
    if not s and not c:
        return 1.0
    if not s or not c:
        return 0.0
    if s == c:
        return 1.0
    if s in c or c in s:
        return 0.9

    s_tokens = set(s.split())
    c_tokens = set(c.split())
    intersection = s_tokens & c_tokens
    union = s_tokens | c_tokens
    jaccard = len(intersection) / len(union)

    if s_tokens <= c_tokens or c_tokens <= s_tokens:
        return jaccard * 0.9 + 0.1

    return jaccard


def _artist_similarity(search_artist: str, candidate_artist: str) -> float:
    """Return similarity score 0.0-1.0 between two artist names.

    Strategy:
    1. Exact match after normalization -> 1.0
    2. Token-level Jaccard similarity
    3. Substring containment (handles channel names like
       'thekillersmusic' -> 'The Killers')
    """
    if not search_artist or not candidate_artist:
        return 0.5

    a = _extract_primary_artist(search_artist).lower().strip()
    b = _extract_primary_artist(candidate_artist).lower().strip()

    if not a and not b:
        return 1.0
    if not a or not b:
        return 0.5

    if a == b:
        return 1.0

    a_tokens = a.split()
    b_tokens = b.split()

    intersection = [t for t in a_tokens if t in b_tokens]
    if intersection:
        return len(intersection) / max(len(a_tokens), len(b_tokens))

    for ta in a_tokens:
        if len(ta) >= 3 and ta in b:
            return 0.3
    for tb in b_tokens:
        if len(tb) >= 3 and tb in a:
            return 0.3

    return 0.0


def _best_match(
    search_title: str,
    candidates: list[dict],
    threshold: float = 0.75,
    search_artist: str | None = None,
) -> dict | None:
    """Find the best matching track from a list of candidates.

    When search_artist is provided, uses a combined title + artist
    similarity score to avoid matching the right song by the wrong artist.

    Args:
        search_title: Title to search for
        candidates: List of track dicts with 'title' field
        threshold: Minimum similarity score to consider a match
        search_artist: Optional source artist name for artist-aware matching

    Returns:
        Best matching track dict if score >= threshold, None otherwise
    """
    if not search_title or not candidates:
        return None

    best_match = None
    best_score = 0.0

    for candidate in candidates:
        candidate_title = candidate.get("title", "")
        if not candidate_title:
            continue
        title_score = _match_titles(search_title, candidate_title)
        if search_artist:
            candidate_artist = candidate.get("artist_name", "")
            artist_score = _artist_similarity(search_artist, candidate_artist)
            score = 0.6 * title_score + 0.4 * artist_score
        else:
            score = title_score
        if score > best_score:
            best_score = score
            best_match = candidate

    if best_score >= threshold and best_match:
        logger.info(
            "Matched '%s' -> '%s' score=%.2f",
            search_title,
            best_match.get("title"),
            best_score,
        )
        return best_match

    return None
