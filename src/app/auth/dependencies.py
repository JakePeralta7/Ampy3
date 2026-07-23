"""FastAPI dependency for extracting the current user from the session."""

from fastapi import HTTPException, Request

from src.app.settings import settings

SESSION_COOKIE = "ampy3_session"


def get_current_user(request: Request) -> dict:
    """Return the authenticated user dict set by the session middleware.

    Raises ``401`` if auth is required and no valid session is present.

    When ``REQUIRE_AUTH=false`` this always returns a stub user so that
    routes never need to guard against ``None``.
    """
    if not settings.require_auth:
        return {
            "plex_user_id": "local",
            "username": "local",
            "email": None,
            "thumb": None,
            "plex_token": "",
        }

    user = getattr(request.state, "user", None)
    if user is None:
        raise HTTPException(status_code=401, detail="unauthenticated")
    return user
