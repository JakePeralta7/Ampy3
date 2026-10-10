"""Server URL validation for sync targets.

Target configuration accepts user-supplied base URLs that are used for
authenticated HTTP clients. To avoid credential-forwarding/SSRF primitives,
URLs are constrained to http(s) with an explicit hostname before they are
ever used to construct a client.
"""

from urllib.parse import parse_qs, urlparse, urlsplit


class InvalidServerUrlError(ValueError):
    """Raised when a target server URL does not pass validation."""


def source_id_from_url(url: str) -> str:
    """Extract the exact playlist id from a source playlist URL.

    Handles both known shapes — the query form (YouTube Music
    ``/playlist?list=PLabc``) and the path form (Deezer
    ``/playlist/123456``). Returns ``""`` when neither is present; ids are
    never substring-matched.
    """
    parts = urlsplit(url)
    values = parse_qs(parts.query).get("list")
    if values:
        return values[0]
    segments = [segment for segment in parts.path.split("/") if segment]
    if len(segments) >= 2 and segments[-2] == "playlist":
        return segments[-1]
    return ""


def validate_server_url(url: str, *, field: str = "url") -> str:
    """Validate and return a normalized target server URL.

    Enforces http/https scheme and a non-empty hostname; rejects userinfo,
    query strings, and fragments. A trailing slash is preserved so callers
    can ``rstrip("/")`` as they already do.

    Raises:
        InvalidServerUrlError: if the URL is malformed or uses a disallowed
            shape.
    """
    stripped = url.strip()
    if not stripped:
        raise InvalidServerUrlError(f"{field} must not be empty")

    try:
        parsed = urlparse(stripped)
    except ValueError as exc:
        raise InvalidServerUrlError(f"{field} is not a valid URL") from exc

    if parsed.scheme not in ("http", "https"):
        raise InvalidServerUrlError(f"{field} must be an http(s) URL")
    if not parsed.hostname:
        raise InvalidServerUrlError(f"{field} must include a hostname")
    if parsed.username is not None or parsed.password is not None:
        raise InvalidServerUrlError(f"{field} must not contain user credentials")
    if parsed.query:
        raise InvalidServerUrlError(f"{field} must not contain a query string")
    if parsed.fragment:
        raise InvalidServerUrlError(f"{field} must not contain a fragment")

    return stripped
