"""WebSocket endpoints for real-time sync and pipeline updates."""

import logging
from typing import Any

from fastapi import APIRouter
from fastapi.websockets import WebSocket
from sqlalchemy import select

from src.app.auth.dependencies import SESSION_COOKIE
from src.app.auth.tokens import verify_session
from src.app.db import AsyncSessionLocal
from src.app.models import ScheduledPlaylistSync
from src.app.services.crypto import get_session_signing_key
from src.app.services.websocket_manager import get_websocket_manager
from src.app.settings import settings

logger = logging.getLogger(__name__)

# Custom WebSocket close codes (4000-4999 range)
WS_CLOSE_UNAUTHORIZED = 4001
WS_CLOSE_INVALID_SYNC_ID = 4002
WS_CLOSE_FORBIDDEN = 4003

router = APIRouter(tags=["realtime"])


async def _reject(websocket: WebSocket, code: int, reason: str) -> None:
    """Close a socket with a meaningful close code.

    A close frame can only be delivered *after* the handshake. Closing before
    ``accept()`` makes the ASGI server reject the handshake with a plain HTTP
    403 and the client never sees the close code — the custom codes below
    would be dead letters.
    """
    try:
        await websocket.accept()
    except Exception as e:
        logger.debug(f"WebSocket accept failed (expected if already closed): {e}")
        return
    try:
        await websocket.close(code=code, reason=reason)
    except Exception as e:
        logger.debug(f"WebSocket close failed: {e}")


async def _authenticate(websocket: WebSocket) -> dict[str, Any] | None:
    """Resolve the user behind a WebSocket connection.

    Mirrors :func:`src.app.auth.dependencies.get_current_user`: when
    ``REQUIRE_AUTH`` is disabled a stub ``local`` user is returned, otherwise
    the session cookie must carry a valid session. Returns ``None`` when the
    connection is not authorized.
    """
    if not settings.require_auth:
        return {
            "plex_user_id": "local",
            "username": "local",
            "email": None,
            "thumb": None,
            "plex_token": "",
        }

    try:
        user = await verify_session(
            websocket.cookies.get(SESSION_COOKIE, ""), get_session_signing_key()
        )
    except Exception:
        return None

    return user or None


@router.websocket("/api/v1/ws/syncs")
async def websocket_syncs(websocket: WebSocket):
    """WebSocket endpoint for real-time sync updates.

    Clients connect here to receive live updates about sync status changes,
    creation, deletion, and manual triggers.

    Message types sent to clients:
    - sync_updated: A sync's status or fields changed
    - sync_created: A new sync was created
    - sync_deleted: A sync was deleted

    Requires authentication via session cookie.
    """
    # Extract and validate session before accepting connection
    user = await _authenticate(websocket)

    if not user:
        await _reject(websocket, WS_CLOSE_UNAUTHORIZED, "Unauthorized")
        return

    manager = get_websocket_manager()
    try:
        await manager.connect(websocket, "syncs", user_id=user["plex_user_id"])
        logger.info(f"Client {user['plex_user_id']} connected to syncs WebSocket")
        while True:
            # Keep the connection alive by listening for messages
            # In practice, clients don't send data on this endpoint, but we keep
            # the connection open and wait
            await websocket.receive_text()
    except Exception as e:
        logger.warning(f"WebSocket error in /ws/syncs: {e}")
        await manager.disconnect(websocket)


@router.websocket("/api/v1/ws/pipeline/{sync_id}")
async def websocket_pipeline(websocket: WebSocket, sync_id: str):
    """WebSocket endpoint for real-time pipeline updates.

    Clients connect here to receive live updates about a specific sync's
    pipeline execution, including stage changes and track matching progress.

    Path parameters:
    - sync_id: The UUID of the scheduled sync to monitor

    Message types sent to clients:
    - pipeline_stage_changed: The pipeline moved to a new stage
    - track_matched: A track was matched to a target (progress update)
    - pipeline_error: An error occurred during pipeline execution
    - pipeline_complete: The pipeline finished execution

    Requires authentication via session cookie. Only the sync owner can access.
    """
    # Extract and validate session before accepting connection
    user = await _authenticate(websocket)

    if not user:
        await _reject(websocket, WS_CLOSE_UNAUTHORIZED, "Unauthorized")
        return

    # Verify user owns this sync
    if not sync_id.isdigit():
        await _reject(websocket, WS_CLOSE_INVALID_SYNC_ID, "Invalid sync ID")
        return

    sync_id_int = int(sync_id)
    if sync_id_int <= 0:
        await _reject(websocket, WS_CLOSE_INVALID_SYNC_ID, "Invalid sync ID")
        return

    async with AsyncSessionLocal() as session:
        sync = await session.execute(
            select(ScheduledPlaylistSync).where(ScheduledPlaylistSync.id == sync_id_int)
        )
        sync = sync.scalar_one_or_none()

        if not sync or sync.user_id != user["plex_user_id"]:
            await _reject(websocket, WS_CLOSE_FORBIDDEN, "Forbidden")
            return

    manager = get_websocket_manager()
    subscription_type = f"pipeline_{sync_id}"
    try:
        await manager.connect(websocket, subscription_type, user_id=user["plex_user_id"])
        logger.info(
            f"Client {user['plex_user_id']} connected to pipeline WebSocket for sync {sync_id}"
        )
        while True:
            # Keep the connection alive
            await websocket.receive_text()
    except Exception as e:
        logger.warning(f"WebSocket error in /ws/pipeline/{sync_id}: {e}")
        await manager.disconnect(websocket)
