"""
WebSocket Connection Manager.

Manages multiple concurrent WebSocket connections for Twilio media streams.
"""
import logging
import asyncio
from typing import Dict, Optional
from datetime import datetime
from fastapi import WebSocket

logger = logging.getLogger(__name__)


class ConnectionManager:
    """
    Manages WebSocket connections for Twilio media streams.

    Handles:
    - Connection lifecycle (connect, disconnect)
    - Message routing to voice sessions
    - Connection tracking and monitoring
    - Cleanup on disconnect
    """

    def __init__(self):
        """Initialize connection manager."""
        self.active_connections: Dict[str, WebSocket] = {}
        self.connection_metadata: Dict[str, dict] = {}
        self._lock = asyncio.Lock()

    async def connect(self, call_id: str, websocket: WebSocket) -> None:
        """
        Register a new WebSocket connection.

        Args:
            call_id: Unique call identifier
            websocket: WebSocket connection
        """
        await websocket.accept()

        async with self._lock:
            self.active_connections[call_id] = websocket
            self.connection_metadata[call_id] = {
                "connected_at": datetime.utcnow(),
                "message_count": 0,
                "last_activity": datetime.utcnow(),
            }

        logger.info(f"WebSocket connected: call_id={call_id}, total_connections={len(self.active_connections)}")

    async def disconnect(self, call_id: str) -> None:
        """
        Unregister a WebSocket connection.

        Args:
            call_id: Call identifier
        """
        async with self._lock:
            if call_id in self.active_connections:
                del self.active_connections[call_id]

            if call_id in self.connection_metadata:
                metadata = self.connection_metadata[call_id]
                duration = (datetime.utcnow() - metadata["connected_at"]).total_seconds()
                logger.info(
                    f"WebSocket disconnected: call_id={call_id}, "
                    f"duration={duration:.2f}s, messages={metadata['message_count']}"
                )
                del self.connection_metadata[call_id]

        logger.info(f"Total active connections: {len(self.active_connections)}")

    async def send_text(self, call_id: str, message: str) -> bool:
        """
        Send text message to WebSocket.

        Args:
            call_id: Call identifier
            message: Message to send

        Returns:
            True if sent successfully
        """
        websocket = self.active_connections.get(call_id)
        if not websocket:
            logger.warning(f"Cannot send message: WebSocket not found for call_id={call_id}")
            return False

        try:
            await websocket.send_text(message)
            await self._update_activity(call_id)
            return True
        except Exception as e:
            logger.error(f"Error sending text message: {e}")
            await self.disconnect(call_id)
            return False

    async def send_json(self, call_id: str, data: dict) -> bool:
        """
        Send JSON message to WebSocket.

        Args:
            call_id: Call identifier
            data: Data to send

        Returns:
            True if sent successfully
        """
        websocket = self.active_connections.get(call_id)
        if not websocket:
            logger.warning(f"Cannot send JSON: WebSocket not found for call_id={call_id}")
            return False

        try:
            await websocket.send_json(data)
            await self._update_activity(call_id)
            return True
        except Exception as e:
            logger.error(f"Error sending JSON message: {e}")
            await self.disconnect(call_id)
            return False

    async def send_bytes(self, call_id: str, data: bytes) -> bool:
        """
        Send binary message to WebSocket.

        Args:
            call_id: Call identifier
            data: Binary data to send

        Returns:
            True if sent successfully
        """
        websocket = self.active_connections.get(call_id)
        if not websocket:
            logger.warning(f"Cannot send bytes: WebSocket not found for call_id={call_id}")
            return False

        try:
            await websocket.send_bytes(data)
            await self._update_activity(call_id)
            return True
        except Exception as e:
            logger.error(f"Error sending binary message: {e}")
            await self.disconnect(call_id)
            return False

    def is_connected(self, call_id: str) -> bool:
        """
        Check if WebSocket is connected.

        Args:
            call_id: Call identifier

        Returns:
            True if connected
        """
        return call_id in self.active_connections

    def get_connection_count(self) -> int:
        """
        Get number of active connections.

        Returns:
            Number of active connections
        """
        return len(self.active_connections)

    def get_connection_metadata(self, call_id: str) -> Optional[dict]:
        """
        Get metadata for a connection.

        Args:
            call_id: Call identifier

        Returns:
            Connection metadata or None
        """
        return self.connection_metadata.get(call_id)

    async def _update_activity(self, call_id: str) -> None:
        """
        Update last activity timestamp.

        Args:
            call_id: Call identifier
        """
        if call_id in self.connection_metadata:
            self.connection_metadata[call_id]["last_activity"] = datetime.utcnow()
            self.connection_metadata[call_id]["message_count"] += 1

    async def cleanup_inactive(self, timeout_seconds: int = 300) -> int:
        """
        Clean up inactive connections.

        Args:
            timeout_seconds: Inactivity timeout

        Returns:
            Number of connections cleaned up
        """
        now = datetime.utcnow()
        inactive_calls = []

        async with self._lock:
            for call_id, metadata in self.connection_metadata.items():
                inactive_duration = (now - metadata["last_activity"]).total_seconds()
                if inactive_duration > timeout_seconds:
                    inactive_calls.append(call_id)

        # Disconnect inactive connections
        for call_id in inactive_calls:
            logger.warning(f"Cleaning up inactive connection: call_id={call_id}")
            await self.disconnect(call_id)

        return len(inactive_calls)


# Global connection manager instance
_connection_manager: Optional[ConnectionManager] = None


def get_connection_manager() -> ConnectionManager:
    """
    Get global connection manager instance (singleton).

    Returns:
        ConnectionManager instance
    """
    global _connection_manager
    if _connection_manager is None:
        _connection_manager = ConnectionManager()
    return _connection_manager
