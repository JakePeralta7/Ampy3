"""WebSocket connection manager for real-time sync/pipeline updates."""

from __future__ import annotations

import asyncio
import json
import logging
from collections.abc import Callable
from typing import Any

from fastapi import WebSocket

logger = logging.getLogger(__name__)


class WebSocketConnectionManager:
    """Manages WebSocket connections and broadcasts messages to subscribers.

    Tracks active connections per subscription type (e.g., syncs, pipeline).
    Handles reconnections, stale connections, and cleanup on disconnect.
    """

    def __init__(self):
        """Initialize the connection manager with empty connection maps."""
        # subscription_type -> set of WebSocket connections
        self._subscriptions: dict[str, set[WebSocket]] = {}
        # WebSocket -> subscription types (for cleanup on disconnect)
        self._connection_subscriptions: dict[WebSocket, set[str]] = {}
        self._lock = asyncio.Lock()

    async def connect(self, websocket: WebSocket, subscription_type: str) -> None:
        """Accept and register a WebSocket connection.

        Args:
            websocket: The WebSocket connection to register
            subscription_type: The subscription category (e.g., 'syncs', 'pipeline_{sync_id}')
        """
        await websocket.accept()
        async with self._lock:
            if subscription_type not in self._subscriptions:
                self._subscriptions[subscription_type] = set()
            self._subscriptions[subscription_type].add(websocket)
            if websocket not in self._connection_subscriptions:
                self._connection_subscriptions[websocket] = set()
            self._connection_subscriptions[websocket].add(subscription_type)
            count = len(self._subscriptions[subscription_type])
            logger.debug(f"WebSocket connected to '{subscription_type}' ({count} total)")

    async def disconnect(self, websocket: WebSocket) -> None:
        """Remove a WebSocket connection from all subscriptions.

        Args:
            websocket: The WebSocket connection to disconnect
        """
        async with self._lock:
            if websocket in self._connection_subscriptions:
                for subscription_type in self._connection_subscriptions[websocket]:
                    self._subscriptions[subscription_type].discard(websocket)
                    if not self._subscriptions[subscription_type]:
                        del self._subscriptions[subscription_type]
                del self._connection_subscriptions[websocket]
        logger.debug("WebSocket disconnected")

    async def broadcast(
        self,
        subscription_type: str,
        message_type: str,
        data: dict[str, Any],
    ) -> None:
        """Broadcast a message to all subscribers of a subscription type.

        Args:
            subscription_type: The subscription category to broadcast to
            message_type: The type of message (e.g., 'sync_updated', 'pipeline_stage_changed')
            data: The data payload to send
        """
        payload = {
            "type": message_type,
            "data": data,
        }
        message_json = json.dumps(payload)

        async with self._lock:
            connections = list(self._subscriptions.get(subscription_type, set()))

        disconnected = []
        for websocket in connections:
            try:
                await websocket.send_text(message_json)
            except Exception as e:
                logger.warning(f"Failed to send message to WebSocket: {e}")
                disconnected.append(websocket)

        # Clean up disconnected sockets
        for websocket in disconnected:
            await self.disconnect(websocket)

    async def send_to_connection(
        self,
        websocket: WebSocket,
        message_type: str,
        data: dict[str, Any],
    ) -> None:
        """Send a message to a specific WebSocket connection.

        Args:
            websocket: The WebSocket connection to send to
            message_type: The type of message
            data: The data payload to send
        """
        payload = {
            "type": message_type,
            "data": data,
        }
        message_json = json.dumps(payload)

        try:
            await websocket.send_text(message_json)
        except Exception as e:
            logger.warning(f"Failed to send message to WebSocket: {e}")
            await self.disconnect(websocket)

    def get_connection_count(self, subscription_type: str) -> int:
        """Get the number of active connections for a subscription type.

        Args:
            subscription_type: The subscription category

        Returns:
            The number of active connections
        """
        return len(self._subscriptions.get(subscription_type, set()))

    async def close_all(self) -> None:
        """Close all active WebSocket connections gracefully."""
        async with self._lock:
            connections = [
                ws for subscription_set in self._subscriptions.values()
                for ws in subscription_set
            ]
        for websocket in connections:
            try:
                await websocket.close()
            except Exception as e:
                logger.warning(f"Error closing WebSocket: {e}")
        async with self._lock:
            self._subscriptions.clear()
            self._connection_subscriptions.clear()


# Global singleton instance
_manager: WebSocketConnectionManager | None = None


def get_websocket_manager() -> WebSocketConnectionManager:
    """Get the global WebSocket connection manager singleton.

    Returns:
        The WebSocket connection manager instance
    """
    global _manager
    if _manager is None:
        _manager = WebSocketConnectionManager()
    return _manager


def reset_websocket_manager() -> None:
    """Reset the WebSocket connection manager (for testing)."""
    global _manager
    _manager = None
