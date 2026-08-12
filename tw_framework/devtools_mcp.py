"""
TW Framework - DevTools MCP (AI Debugging)

Implements:
6. Next.js DevTools MCP - Model Context Protocol for AI agents
"""

from __future__ import annotations
import json, time, logging, os
from dataclasses import dataclass, field
from typing import Any, Callable, Dict, List, Optional

logger = logging.getLogger(__name__)


@dataclass
class DevToolsLogEntry:
    """A log entry from browser or server."""
    source: str  # "browser" | "server"
    level: str  # "info" | "warn" | "error" | "debug"
    message: str
    timestamp: float = field(default_factory=time.time)
    route: str = ""
    stack_trace: str = ""


@dataclass
class AppContext:
    """Context about the app for AI agents."""
    active_route: str = ""
    routes: List[str] = field(default_factory=list)
    cache_status: Dict[str, Any] = field(default_factory=dict)
    rendering_mode: str = ""  # static | dynamic | streaming
    features_enabled: List[str] = field(default_factory=list)
    errors: List[Dict[str, Any]] = field(default_factory=list)


class DevToolsMCP:
    """Model Context Protocol integration for AI debugging.

    Provides AI agents with contextual insight about the app:
    1. Routing, caching, rendering behavior
    2. Unified logs (browser + server together)
    3. Automatic error access with detailed stack traces
    4. Page-aware context (understands active route)

    AI agents can use this to:
    - Diagnose issues
    - Explain behavior
    - Suggest fixes
    """

    def __init__(self):
        self._logs: List[DevToolsLogEntry] = []
        self._context = AppContext()
        self._error_log: List[Dict[str, Any]] = []
        self._max_logs = 1000
        self._connected = False

    def set_context(self, route: str = "", routes: Optional[List[str]] = None,
                    cache_status: Optional[Dict] = None,
                    rendering_mode: str = "",
                    features: Optional[List[str]] = None) -> None:
        """Set the current app context."""
        if route:
            self._context.active_route = route
        if routes:
            self._context.routes = routes
        if cache_status:
            self._context.cache_status = cache_status
        if rendering_mode:
            self._context.rendering_mode = rendering_mode
        if features:
            self._context.features_enabled = features

    def log(self, source: str, level: str, message: str,
            route: str = "", stack_trace: str = "") -> None:
        """Add a log entry from browser or server."""
        entry = DevToolsLogEntry(
            source=source, level=level, message=message,
            route=route, stack_trace=stack_trace,
        )
        self._logs.append(entry)
        if len(self._logs) > self._max_logs:
            self._logs = self._logs[-self._max_logs:]
        if level == "error":
            self._error_log.append({
                "message": message,
                "route": route,
                "stack": stack_trace,
                "timestamp": entry.timestamp,
            })

    def log_browser(self, level: str, message: str, **kwargs) -> None:
        self.log("browser", level, message, **kwargs)

    def log_server(self, level: str, message: str, **kwargs) -> None:
        self.log("server", level, message, **kwargs)

    def get_context(self) -> Dict[str, Any]:
        """Get current app context for AI agents."""
        return {
            "active_route": self._context.active_route,
            "total_routes": len(self._context.routes),
            "routes": self._context.routes[:20],
            "cache_status": self._context.cache_status,
            "rendering_mode": self._context.rendering_mode,
            "features_enabled": self._context.features_enabled,
            "error_count": len(self._error_log),
            "log_count": len(self._logs),
        }

    def get_logs(self, source: str = "", level: str = "",
                 route: str = "", limit: int = 50) -> List[Dict]:
        """Get filtered logs."""
        logs = self._logs
        if source:
            logs = [l for l in logs if l.source == source]
        if level:
            logs = [l for l in logs if l.level == level]
        if route:
            logs = [l for l in logs if l.route == route]
        return [{"source": l.source, "level": l.level, "message": l.message,
                 "route": l.route, "timestamp": l.timestamp,
                 "stack": l.stack_trace} for l in logs[-limit:]]

    def get_errors(self) -> List[Dict[str, Any]]:
        """Get all errors with stack traces."""
        return list(self._error_log)

    def get_diagnostic_summary(self) -> Dict[str, Any]:
        """Get a diagnostic summary for AI agents."""
        error_count = len(self._error_log)
        warn_count = sum(1 for l in self._logs if l.level == "warn")
        browser_logs = sum(1 for l in self._logs if l.source == "browser")
        server_logs = sum(1 for l in self._logs if l.source == "server")

        summary = {
            "active_route": self._context.active_route,
            "rendering_mode": self._context.rendering_mode,
            "total_logs": len(self._logs),
            "browser_logs": browser_logs,
            "server_logs": server_logs,
            "errors": error_count,
            "warnings": warn_count,
            "cache_status": self._context.cache_status,
            "features": self._context.features_enabled,
            "recent_errors": self._error_log[-5:],
        }

        # Add AI-friendly suggestions
        suggestions: List[str] = []
        if error_count > 0:
            suggestions.append("Check the recent errors — " + str(error_count) + " errors detected")
        if warn_count > 5:
            suggestions.append("High warning count (" + str(warn_count) + ") — investigate server logs")
        if self._context.rendering_mode == "dynamic" and not self._context.cache_status:
            suggestions.append("Dynamic rendering without cache — consider adding 'use cache' directive")
        if not self._context.features_enabled:
            suggestions.append("No features explicitly enabled — consider enabling PPR or Cache Components")

        summary["ai_suggestions"] = suggestions
        return summary

    def generate_mcp_protocol(self) -> Dict[str, Any]:
        """Generate MCP protocol response for AI agent consumption."""
        return {
            "protocol": "tw-devtools-mcp",
            "version": "1.0",
            "context": self.get_context(),
            "diagnostics": self.get_diagnostic_summary(),
            "logs": self.get_logs(limit=20),
            "errors": self.get_errors(),
        }

    def generate_client_script(self) -> str:
        """Generate JS that sends browser logs to the MCP server."""
        NL = chr(10)
        lines = [
            '<script>',
            '(function() {',
            '  var ws = null;',
            '  function connect() {',
            '    ws = new WebSocket("ws://" + location.host + "/__tw/mcp");',
            '    ws.onopen = function() { console.log("[MCP] Connected to DevTools MCP"); };',
            '    ws.onmessage = function(e) { var data = JSON.parse(e.data); handleCommand(data); };',
            '  }',
            '  function sendLog(level, message, stack) {',
            '    if (ws && ws.readyState === 1) {',
            '      ws.send(JSON.stringify({',
            '        type: "log", source: "browser", level: level,',
            '        message: message, route: location.pathname, stack: stack || ""',
            '      }));',
            '    }',
            '  }',
            '  // Intercept console methods',
            '  var origLog = console.log; var origWarn = console.warn; var origError = console.error;',
            '  console.log = function() { origLog.apply(console, arguments); sendLog("info", Array.from(arguments).join(" ")); };',
            '  console.warn = function() { origWarn.apply(console, arguments); sendLog("warn", Array.from(arguments).join(" ")); };',
            '  console.error = function() { origError.apply(console, arguments); sendLog("error", Array.from(arguments).join(" ")); };',
            '  // Intercept uncaught errors',
            '  window.addEventListener("error", function(e) {',
            '    sendLog("error", e.message, e.error ? e.error.stack : "");',
            '  });',
            '  // Intercept unhandled rejections',
            '  window.addEventListener("unhandledrejection", function(e) {',
            '    sendLog("error", "Unhandled rejection: " + e.reason, "");',
            '  });',
            '  function handleCommand(data) {',
            '    if (data.type === "get_context") {',
            '      ws.send(JSON.stringify({ type: "context", route: location.pathname }));',
            '    }',
            '  }',
            '  connect();',
            '})();',
            '</script>',
        ]
        return NL.join(lines)

    def get_stats(self) -> Dict[str, Any]:
        return {
            "connected": self._connected,
            "total_logs": len(self._logs),
            "errors": len(self._error_log),
            "browser_logs": sum(1 for l in self._logs if l.source == "browser"),
            "server_logs": sum(1 for l in self._logs if l.source == "server"),
        }


__all__ = ["DevToolsLogEntry", "AppContext", "DevToolsMCP"]
