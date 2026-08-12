"""
TW Framework — HMR (Hot Module Replacement) (v0.9.08)

Save .tw file → browser updates without full reload. Like Next.js Fast Refresh.
"""

from __future__ import annotations
import json
import time
import hashlib
from typing import Dict, Set


HMR_CLIENT_SCRIPT = """
<script>
(function() {
    if (typeof WebSocket === "undefined") return;
    var ws = null;
    var reconnectTimer = null;

    function connect() {
        var protocol = window.location.protocol === "https:" ? "wss:" : "ws:";
        var url = protocol + "//" + window.location.host + "/__tw/hmr";
        ws = new WebSocket(url);
        ws.onopen = function() {
            console.log("[TW HMR] Connected");
            if (reconnectTimer) { clearInterval(reconnectTimer); reconnectTimer = null; }
        };
        ws.onmessage = function(event) {
            var msg = {};
            try { msg = JSON.parse(event.data); } catch(e) { return; }
            if (msg.type === "reload") {
                window.location.reload();
                return;
            }
            if (msg.type === "update") {
                console.log("[TW HMR] Update:", msg.file);
                if (msg.html) {
                    var target = document.querySelector(msg.selector || "[data-tw-page]");
                    if (target) {
                        target.innerHTML = msg.html;
                    } else {
                        window.location.reload();
                    }
                }
                if (msg.css) {
                    var style = document.getElementById("tw-hmr-" + msg.file);
                    if (!style) {
                        style = document.createElement("style");
                        style.id = "tw-hmr-" + msg.file;
                        document.head.appendChild(style);
                    }
                    style.textContent = msg.css;
                }
            }
        };
        ws.onclose = function() {
            if (!reconnectTimer) {
                reconnectTimer = setInterval(connect, 2000);
            }
        };
        ws.onerror = function() { ws.close(); };
    }
    connect();
})();
</script>
"""


class HMRManager:
    """Manages HMR state and WebSocket connections."""

    def __init__(self):
        self.connections: Set = set()
        self.file_hashes: Dict[str, str] = {}
        self.enabled = False

    def enable(self) -> None:
        self.enabled = True

    def disable(self) -> None:
        self.enabled = False

    def get_client_script(self) -> str:
        return HMR_CLIENT_SCRIPT

    def track_file(self, path: str, content: str) -> None:
        self.file_hashes[path] = hashlib.md5(content.encode("utf-8")).hexdigest()

    def has_changed(self, path: str, content: str) -> bool:
        h = hashlib.md5(content.encode("utf-8")).hexdigest()
        old = self.file_hashes.get(path)
        if old != h:
            self.file_hashes[path] = h
            return True
        return False

    def broadcast_update(self, file_path: str, html: str = None,
                         js: str = None, css: str = None, selector: str = None) -> None:
        if not self.enabled:
            return
        msg = json.dumps({"type": "update", "file": file_path, "html": html,
                          "js": js, "css": css, "selector": selector,
                          "timestamp": int(time.time() * 1000)})
        for ws in list(self.connections):
            try:
                ws.send(msg)
            except Exception:
                self.connections.discard(ws)

    def broadcast_reload(self) -> None:
        msg = json.dumps({"type": "reload", "timestamp": int(time.time() * 1000)})
        for ws in list(self.connections):
            try:
                ws.send(msg)
            except Exception:
                self.connections.discard(ws)


hmr_manager = HMRManager()
