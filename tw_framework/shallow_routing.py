"""
TW Framework - Shallow Routing

Implements:
26. Shallow Routing - window.history.pushState integration
"""

from __future__ import annotations

import json
import logging
from dataclasses import dataclass, field
from typing import Any, Callable, Dict, List, Optional
from urllib.parse import urlparse, parse_qs, urlencode
import urllib

logger = logging.getLogger(__name__)


@dataclass
class ShallowRouteEntry:
    """A shallow route history entry."""
    url: str
    path: str
    query: Dict[str, str] = field(default_factory=dict)
    state: Dict[str, Any] = field(default_factory=dict)
    title: str = ""
    timestamp: float = 0.0


class ShallowRouter:
    """Shallow routing using window.history.pushState.

    Shallow routing updates the URL without triggering a full page
    navigation or data refetch. Only the query parameters change,
    while the page component stays mounted.

    Use cases:
    - URL-based filtering/sorting without page reload
    - Modal/dialog state in URL
    - Tab state in URL
    - Pagination without refetch
    - Search query in URL

    Usage:
        router = ShallowRouter()
        router.push("/products?category=electronics&page=2")
        # URL changes but page doesn't reload
        # Component reads new query params and updates locally
    """

    def __init__(self):
        self._history: List[ShallowRouteEntry] = []
        self._current_index: int = -1
        self._listeners: List[Callable[[ShallowRouteEntry], None]] = []
        self._max_history: int = 50

    def push(self, url: str, state: Optional[Dict] = None,
             title: str = "") -> ShallowRouteEntry:
        """Push a new shallow route.

        Updates the URL via window.history.pushState without
        triggering a page navigation.
        """
        parsed = urlparse(url)
        query = {k: v[0] if v else "" for k, v in parse_qs(parsed.query).items()}

        entry = ShallowRouteEntry(
            url=url,
            path=parsed.path,
            query=query,
            state=state or {},
            title=title,
            timestamp=__import__("time").time(),
        )

        # Add to history
        self._history = self._history[:self._current_index + 1]
        self._history.append(entry)
        self._current_index += 1

        # Limit history size
        if len(self._history) > self._max_history:
            excess = len(self._history) - self._max_history
            self._history = self._history[excess:]
            self._current_index -= excess

        self._notify(entry)
        return entry

    def replace(self, url: str, state: Optional[Dict] = None,
               title: str = "") -> ShallowRouteEntry:
        """Replace the current shallow route (no history entry)."""
        parsed = urlparse(url)
        query = {k: v[0] if v else "" for k, v in parse_qs(parsed.query).items()}

        entry = ShallowRouteEntry(
            url=url,
            path=parsed.path,
            query=query,
            state=state or {},
            title=title,
            timestamp=__import__("time").time(),
        )

        if self._current_index >= 0:
            self._history[self._current_index] = entry
        else:
            self._history.append(entry)
            self._current_index = 0

        self._notify(entry)
        return entry

    def back(self) -> Optional[ShallowRouteEntry]:
        """Go back in shallow history."""
        if self._current_index <= 0:
            return None

        self._current_index -= 1
        entry = self._history[self._current_index]
        self._notify(entry)
        return entry

    def forward(self) -> Optional[ShallowRouteEntry]:
        """Go forward in shallow history."""
        if self._current_index >= len(self._history) - 1:
            return None

        self._current_index += 1
        entry = self._history[self._current_index]
        self._notify(entry)
        return entry

    def update_query(self, params: Dict[str, str],
                      merge: bool = True) -> ShallowRouteEntry:
        """Update only the query parameters without changing the path."""
        if self._current_index < 0:
            return self.push("/", state={"params": params})

        current = self._history[self._current_index]
        new_query = {**current.query, **params} if merge else dict(params)

        # Remove params with empty values
        new_query = {k: v for k, v in new_query.items() if v}

        query_str = urlencode(new_query)
        url = f"{current.path}?{query_str}" if query_str else current.path

        return self.push(url, state=current.state)

    def remove_query(self, keys: List[str]) -> ShallowRouteEntry:
        """Remove specific query parameters."""
        if self._current_index < 0:
            return self.push("/")

        current = self._history[self._current_index]
        new_query = {k: v for k, v in current.query.items() if k not in keys}

        query_str = urlencode(new_query)
        url = f"{current.path}?{query_str}" if query_str else current.path

        return self.push(url, state=current.state)

    def get_query(self, key: str = "", default: str = "") -> Any:
        """Get query parameter(s)."""
        if self._current_index < 0:
            return default

        entry = self._history[self._current_index]
        if key:
            return entry.query.get(key, default)
        return dict(entry.query)

    def get_state(self, key: str = "", default: Any = None) -> Any:
        """Get state value(s)."""
        if self._current_index < 0:
            return default

        entry = self._history[self._current_index]
        if key:
            return entry.state.get(key, default)
        return dict(entry.state)

    @property
    def current_url(self) -> str:
        """Get the current URL."""
        if self._current_index < 0:
            return "/"
        return self._history[self._current_index].url

    @property
    def current_path(self) -> str:
        """Get the current path."""
        if self._current_index < 0:
            return "/"
        return self._history[self._current_index].path

    @property
    def can_go_back(self) -> bool:
        return self._current_index > 0

    @property
    def can_go_forward(self) -> bool:
        return self._current_index < len(self._history) - 1

    def on_change(self, listener: Callable[[ShallowRouteEntry], None]) -> None:
        """Register a listener for route changes."""
        self._listeners.append(listener)

    def remove_listener(self, listener: Callable) -> None:
        if listener in self._listeners:
            self._listeners.remove(listener)

    def _notify(self, entry: ShallowRouteEntry) -> None:
        for listener in self._listeners:
            try:
                listener(entry)
            except Exception as e:
                logger.warning("Shallow router listener error: %s", e)

    def generate_push_state_js(self, url: str, state: Optional[Dict] = None) -> str:
        """Generate JavaScript for window.history.pushState."""
        state_json = json.dumps(state or {})
        return f"window.history.pushState({state_json}, '', '{url}');"

    def generate_replace_state_js(self, url: str, state: Optional[Dict] = None) -> str:
        """Generate JavaScript for window.history.replaceState."""
        state_json = json.dumps(state or {})
        return f"window.history.replaceState({state_json}, '', '{url}');"

    def generate_popstate_listener_js(self) -> str:
        """Generate JavaScript to listen for popstate events."""
        return (
            "window.addEventListener('popstate', function(event) {"
            "  var state = event.state || {};"
            "  var url = window.location.pathname + window.location.search;"
            "  document.dispatchEvent(new CustomEvent('tw:shallow-route', {"
            "    detail: { url: url, state: state }"
            "  }));"
            "});"
        )

    def get_history(self) -> List[Dict[str, Any]]:
        """Get full history for debugging."""
        return [
            {
                "url": e.url,
                "path": e.path,
                "query": e.query,
                "state": e.state,
                "timestamp": e.timestamp,
            }
            for e in self._history
        ]

    def get_stats(self) -> Dict[str, Any]:
        return {
            "history_length": len(self._history),
            "current_index": self._current_index,
            "can_go_back": self.can_go_back,
            "can_go_forward": self.can_go_forward,
            "listeners": len(self._listeners),
        }


__all__ = ["ShallowRouteEntry", "ShallowRouter"]
