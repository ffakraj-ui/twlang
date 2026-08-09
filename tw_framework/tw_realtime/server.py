"""
Server-side realtime handler for tw/realtime.

Integrates with the existing WebSocket implementation (websocket.py)
to provide a connection manager for realtime applications.
"""

from __future__ import annotations

import json
import logging
import threading
from dataclasses import dataclass, field
from typing import Any, Callable, Dict, List, Optional, Set

logger = logging.getLogger(__name__)


@dataclass
class ConnectedClient:
    """A connected WebSocket client."""
    connection: Any  # WebSocketConnection from websocket.py
    path: str
    channels: Set[str] = field(default_factory=set)
    metadata: Dict[str, Any] = field(default_factory=dict)


class ConnectionManager:
    """Manages WebSocket connections for realtime applications."""

    def __init__(self):
        self._connections: Dict[str, ConnectedClient] = {}  # client_id -> client
        self._channels: Dict[str, Set[str]] = {}  # channel -> set of client_ids
        self._lock = threading.RLock()

    def add_connection(self, client_id: str, connection: Any, path: str) -> ConnectedClient:
        """Register a new WebSocket connection."""
        with self._lock:
            client = ConnectedClient(connection=connection, path=path)
            self._connections[client_id] = client
            return client

    def remove_connection(self, client_id: str) -> None:
        """Remove a connection and clean up channel subscriptions."""
        with self._lock:
            client = self._connections.pop(client_id, None)
            if client:
                for channel in client.channels:
                    if channel in self._channels:
                        self._channels[channel].discard(client_id)
                        if not self._channels[channel]:
                            del self._channels[channel]

    def join_channel(self, client_id: str, channel: str) -> None:
        """Subscribe a client to a channel."""
        with self._lock:
            client = self._connections.get(client_id)
            if not client:
                return
            client.channels.add(channel)
            if channel not in self._channels:
                self._channels[channel] = set()
            self._channels[channel].add(client_id)

    def leave_channel(self, client_id: str, channel: str) -> None:
        """Unsubscribe a client from a channel."""
        with self._lock:
            client = self._connections.get(client_id)
            if not client:
                return
            client.channels.discard(channel)
            if channel in self._channels:
                self._channels[channel].discard(client_id)

    def broadcast(self, channel: str, message: Dict[str, Any], exclude: Optional[str] = None) -> int:
        """Broadcast a message to all clients in a channel. Returns count of recipients."""
        with self._lock:
            client_ids = self._channels.get(channel, set()).copy()
        count = 0
        for cid in client_ids:
            if cid == exclude:
                continue
            client = self._connections.get(cid)
            if client and client.connection:
                try:
                    client.connection.send_text(json.dumps(message))
                    count += 1
                except Exception as err:
                    logger.warning("Failed to send to client %s: %s", cid, err)
        return count

    def send_to(self, client_id: str, message: Dict[str, Any]) -> bool:
        """Send a message to a specific client."""
        with self._lock:
            client = self._connections.get(client_id)
        if not client or not client.connection:
            return False
        try:
            client.connection.send_text(json.dumps(message))
            return True
        except Exception:
            return False

    def get_connection_count(self) -> int:
        with self._lock:
            return len(self._connections)

    def get_channel_count(self, channel: str) -> int:
        with self._lock:
            return len(self._channels.get(channel, set()))


class RealtimeServer:
    """Server-side realtime handler that processes WebSocket messages."""

    def __init__(self):
        self.manager = ConnectionManager()
        self._handlers: Dict[str, Callable] = {}
        self._counter = 0
        self._counter_lock = threading.Lock()

    def register_handler(self, event_type: str, handler: Callable) -> None:
        self._handlers[event_type] = handler

    def handle_message(self, client_id: str, raw_message: str) -> Optional[Dict[str, Any]]:
        """Process an incoming WebSocket message."""
        try:
            msg = json.loads(raw_message)
        except json.JSONDecodeError:
            return {"type": "error", "data": {"message": "Invalid JSON"}}

        msg_type = msg.get("type", "")
        handler = self._handlers.get(msg_type)
        if handler:
            try:
                result = handler(client_id, msg.get("data", {}))
                return result
            except Exception as err:
                logger.exception("Handler error for event '%s'", msg_type)
                return {"type": "error", "data": {"message": str(err)}}

        if msg_type == "join":
            channel = msg.get("data", {}).get("channel", "")
            if channel:
                self.manager.join_channel(client_id, channel)
                return {"type": "joined", "data": {"channel": channel}}
        elif msg_type == "leave":
            channel = msg.get("data", {}).get("channel", "")
            if channel:
                self.manager.leave_channel(client_id, channel)
                return {"type": "left", "data": {"channel": channel}}
        elif msg_type == "broadcast":
            channel = msg.get("data", {}).get("channel", "")
            data = msg.get("data", {}).get("data", {})
            if channel:
                count = self.manager.broadcast(channel, {"type": "message", "data": data}, exclude=client_id)
                return {"type": "broadcasted", "data": {"recipients": count}}

        return {"type": "unknown", "data": {"type": msg_type}}

    def next_client_id(self) -> str:
        with self._counter_lock:
            self._counter += 1
            return f"client_{self._counter}"


__all__ = ["ConnectedClient", "ConnectionManager", "RealtimeServer"]
