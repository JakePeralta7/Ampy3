"""WebSocket endpoints for real-time sync and pipeline updates."""

import logging

from fastapi import APIRouter, WebSocketException, status
from fastapi.websockets import WebSocket

from src.app.services.websocket_manager import get_websocket_manager

logger = logging.getLogger(__name__)

router = APIRouter(tags=["realtime"])


@router.websocket("/api/v1/ws/syncs")
async def websocket_syncs(websocket: WebSocket):
    """WebSocket endpoint for real-time sync updates.

    Clients connect here to receive live updates about sync status changes,
    creation, deletion, and manual triggers.

    Message types sent to clients:
    - sync_updated: A sync's status or fields changed
    - sync_created: A new sync was created
    - sync_deleted: A sync was deleted
    """
    manager = get_websocket_manager()
    try:
        await manager.connect(websocket, "syncs")
        logger.info("Client connected to syncs WebSocket")
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
    """
    manager = get_websocket_manager()
    subscription_type = f"pipeline_{sync_id}"
    try:
        await manager.connect(websocket, subscription_type)
        logger.info(f"Client connected to pipeline WebSocket for sync {sync_id}")
        while True:
            # Keep the connection alive
            await websocket.receive_text()
    except Exception as e:
        logger.warning(f"WebSocket error in /ws/pipeline/{sync_id}: {e}")
        await manager.disconnect(websocket)
