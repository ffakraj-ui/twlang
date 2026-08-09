"""Tests for tw/realtime realtime features."""
import pytest
import sys
import os

sys.path.insert(0, os.path.join(os.path.dirname(__file__), ".."))

from tw_framework.tw_realtime.client import RealtimeClient, RealtimeConnection
from tw_framework.tw_realtime.server import ConnectionManager, RealtimeServer


class TestRealtimeClient:
    def test_connect_creates_connection(self):
        client = RealtimeClient()
        conn = client.connect("/api/events")
        assert conn.path == "/api/events"
        assert conn.auto_reconnect is True

    def test_connect_reuses_existing(self):
        client = RealtimeClient()
        conn1 = client.connect("/api/events")
        conn2 = client.connect("/api/events")
        assert conn1 is conn2

    def test_disconnect(self):
        client = RealtimeClient()
        client.connect("/api/events")
        client.disconnect("/api/events")
        assert "/api/events" not in client.get_connections()

    def test_get_client_configs(self):
        client = RealtimeClient()
        client.connect("/api/events")
        client.connect("/api/chat")
        configs = client.get_client_configs()
        assert len(configs) == 2

    def test_connection_on_handler(self):
        conn = RealtimeConnection(path="/api/events")
        received = []
        unsub = conn.on("message", lambda data: received.append(data))
        assert len(received) == 0  # No messages yet

    def test_to_client_config(self):
        conn = RealtimeConnection(path="/ws", auto_reconnect=True)
        config = conn.to_client_config()
        assert config["path"] == "/ws"
        assert config["autoReconnect"] is True


class TestConnectionManager:
    def test_add_and_remove_connection(self):
        mgr = ConnectionManager()
        mgr.add_connection("c1", None, "/ws")
        assert mgr.get_connection_count() == 1
        mgr.remove_connection("c1")
        assert mgr.get_connection_count() == 0

    def test_join_leave_channel(self):
        mgr = ConnectionManager()
        mgr.add_connection("c1", None, "/ws")
        mgr.join_channel("c1", "chat")
        assert mgr.get_channel_count("chat") == 1
        mgr.leave_channel("c1", "chat")
        assert mgr.get_channel_count("chat") == 0

    def test_broadcast_to_empty_channel(self):
        mgr = ConnectionManager()
        count = mgr.broadcast("nonexistent", {"type": "message"})
        assert count == 0


class TestRealtimeServer:
    def test_register_handler(self):
        server = RealtimeServer()
        server.register_handler("custom", lambda cid, data: {"type": "ok"})
        assert server._handlers["custom"] is not None

    def test_handle_join_message(self):
        server = RealtimeServer()
        client_id = server.next_client_id()
        server.manager.add_connection(client_id, None, "/ws")
        result = server.handle_message(client_id, '{"type": "join", "data": {"channel": "chat"}}')
        assert result["type"] == "joined"
        assert result["data"]["channel"] == "chat"

    def test_handle_unknown_message(self):
        server = RealtimeServer()
        result = server.handle_message("c1", '{"type": "unknown_type"}')
        assert result["type"] == "unknown"

    def test_handle_invalid_json(self):
        server = RealtimeServer()
        result = server.handle_message("c1", "not json")
        assert result["type"] == "error"


class TestRealtimeRuntime:
    def test_get_realtime_runtime_js(self):
        from tw_framework.tw_realtime.runtime import get_realtime_runtime_js
        js = get_realtime_runtime_js()
        assert "__tw.realtime" in js
        assert "connect" in js
        assert "WebSocket" in js
