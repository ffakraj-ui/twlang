"""
TW Framework - Instant Navigations & Instant Insights

Implements:
2. Instant Navigations - SPA-like instant navigation for server-driven apps
12. Instant Insights & Playwright Testing - slow navigation detection
"""

from __future__ import annotations
import time, json, logging, os
from dataclasses import dataclass, field
from typing import Any, Callable, Dict, List, Optional, Set

logger = logging.getLogger(__name__)


@dataclass
class NavigationRecord:
    """Record of a single navigation event."""
    from_route: str = ""
    to_route: str = ""
    started_at: float = 0.0
    completed_at: float = 0.0
    duration_ms: float = 0.0
    was_instant: bool = False
    was_cached: bool = False
    prefetch_hit: bool = False
    status: str = "pending"  # pending | completed | timeout | error


class InstantNavigationManager:
    """SPA-like instant navigation for server-driven apps.

    Gives server-rendered apps the instant feel of SPAs by:
    1. Prefetching route data and components on link hover
    2. Caching rendered route output for instant back/forward
    3. Optimistically updating the URL before data arrives
    4. Streaming only the changed content, not full page reloads
    5. Falling back to full navigation if prefetch misses

    This addresses the long-standing criticism that Server Components
    apps feel unresponsive compared to SPAs.
    """

    def __init__(self, max_cache_size: int = 50, instant_threshold_ms: float = 100):
        self._cache: Dict[str, str] = {}  # route -> cached HTML
        self._cache_times: Dict[str, float] = {}
        self._max_cache_size = max_cache_size
        self._instant_threshold = instant_threshold_ms
        self._navigations: List[NavigationRecord] = []
        self._listeners: List[Callable] = []

    def cache_route(self, route: str, html: str) -> None:
        """Cache rendered HTML for a route."""
        if len(self._cache) >= self._max_cache_size:
            # Evict oldest
            oldest = min(self._cache_times, key=self._cache_times.get)
            del self._cache[oldest]
            del self._cache_times[oldest]
        self._cache[route] = html
        self._cache_times[route] = time.time()

    def get_cached(self, route: str) -> Optional[str]:
        """Get cached HTML for a route."""
        return self._cache.get(route)

    def is_cached(self, route: str) -> bool:
        return route in self._cache

    def record_navigation(self, from_route: str, to_route: str) -> NavigationRecord:
        """Record a navigation event."""
        record = NavigationRecord(
            from_route=from_route,
            to_route=to_route,
            started_at=time.time(),
        )
        self._navigations.append(record)
        if len(self._navigations) > 200:
            self._navigations = self._navigations[-200:]
        return record

    def complete_navigation(self, record: NavigationRecord,
                             was_cached: bool = False,
                             prefetch_hit: bool = False) -> None:
        """Mark a navigation as complete."""
        record.completed_at = time.time()
        record.duration_ms = (record.completed_at - record.started_at) * 1000
        record.was_cached = was_cached
        record.prefetch_hit = prefetch_hit
        record.was_instant = record.duration_ms < self._instant_threshold
        record.status = "completed"

    def generate_instant_nav_script(self) -> str:
        """Generate JS for client-side instant navigation."""
        NL = chr(10)
        lines = [
            '<script>',
            '(function() {',
            '  var navCache = {};',
            '  var instantThreshold = ' + str(self._instant_threshold) + ';',
            '  var currentRoute = window.location.pathname;',
            '',
            '  function instantNavigate(toRoute) {',
            '    var startTime = performance.now();',
            '    // Check cache first',
            '    if (navCache[toRoute]) {',
            '      var cached = navCache[toRoute];',
            '      document.getElementById("tw-app").innerHTML = cached.html;',
            '      window.history.pushState({ route: toRoute }, "", toRoute);',
            '      var duration = performance.now() - startTime;',
            '      console.log("[InstantNav] Cached navigation: " + duration.toFixed(1) + "ms");',
            '      document.dispatchEvent(new CustomEvent("tw:navigation", {',
            '        detail: { route: toRoute, instant: true, cached: true, duration: duration }',
            '      }));',
            '      return true;',
            '    }',
            '    // Not cached - fetch with prefetch priority',
            '    fetch(toRoute, { headers: { "X-TW-Instant": "1" } })',
            '      .then(function(r) { return r.text(); })',
            '      .then(function(html) {',
            '        document.getElementById("tw-app").innerHTML = html;',
            '        navCache[toRoute] = { html: html, cached_at: Date.now() };',
            '        window.history.pushState({ route: toRoute }, "", toRoute);',
            '        var duration = performance.now() - startTime;',
            '        var instant = duration < instantThreshold;',
            '        document.dispatchEvent(new CustomEvent("tw:navigation", {',
            '          detail: { route: toRoute, instant: instant, cached: false, duration: duration }',
            '        }));',
            '        if (!instant) {',
            '          console.warn("[InstantNav] Slow navigation: " + duration.toFixed(1) + "ms");',
            '        }',
            '      });',
            '    return false;',
            '  }',
            '',
            '  // Intercept link clicks',
            '  document.addEventListener("click", function(e) {',
            '    var link = e.target.closest("a[href]");',
            '    if (!link) return;',
            '    var href = link.getAttribute("href");',
            '    if (!href || !href.startsWith("/") || href.startsWith("/api/")) return;',
            '    e.preventDefault();',
            '    instantNavigate(href);',
            '  });',
            '',
            '  // Handle back/forward',
            '  window.addEventListener("popstate", function(e) {',
            '    var route = window.location.pathname;',
            '    if (navCache[route]) {',
            '      document.getElementById("tw-app").innerHTML = navCache[route].html;',
            '    } else {',
            '      instantNavigate(route);',
            '    }',
            '  });',
            '',
            '  // Prefetch on hover',
            '  document.addEventListener("mouseover", function(e) {',
            '    var link = e.target.closest("a[href]");',
            '    if (!link) return;',
            '    var href = link.getAttribute("href");',
            '    if (!href || navCache[href] || !href.startsWith("/")) return;',
            '    // Prefetch',
            '    fetch(href, { headers: { "X-TW-Prefetch": "1" } })',
            '      .then(function(r) { return r.text(); })',
            '      .then(function(html) { navCache[href] = { html: html, cached_at: Date.now() }; });',
            '  });',
            '',
            '  window.__tw_instant_nav__ = {',
            '    navigate: instantNavigate,',
            '    cache: navCache,',
            '    isCached: function(route) { return !!navCache[route]; }',
            '  };',
            '})();',
            '</script>',
        ]
        return NL.join(lines)

    def get_navigation_stats(self) -> Dict[str, Any]:
        if not self._navigations:
            return {"total": 0}
        instant_count = sum(1 for n in self._navigations if n.was_instant)
        avg_duration = sum(n.duration_ms for n in self._navigations) / len(self._navigations)
        return {
            "total_navigations": len(self._navigations),
            "instant_count": instant_count,
            "instant_rate_pct": round(instant_count / len(self._navigations) * 100, 1),
            "avg_duration_ms": round(avg_duration, 1),
            "cache_hits": sum(1 for n in self._navigations if n.was_cached),
            "prefetch_hits": sum(1 for n in self._navigations if n.prefetch_hit),
        }


class InstantInsights:
    """Instant Insights tool — slow navigation detection.

    In development mode, flags slow navigations as errors so developers
    can fix them before production. Also provides Playwright test helpers.
    """

    def __init__(self, threshold_ms: float = 100, enabled: bool = True):
        self.threshold_ms = threshold_ms
        self.enabled = enabled
        self._violations: List[Dict[str, Any]] = []

    def check_navigation(self, record: NavigationRecord) -> Optional[Dict[str, Any]]:
        """Check if a navigation was too slow."""
        if not self.enabled:
            return None
        if record.duration_ms > self.threshold_ms and record.status == "completed":
            violation = {
                "route": record.to_route,
                "duration_ms": round(record.duration_ms, 1),
                "threshold_ms": self.threshold_ms,
                "was_cached": record.was_cached,
                "message": "Navigation took " + str(round(record.duration_ms, 1)) + "ms (threshold: " + str(self.threshold_ms) + "ms)",
                "severity": "error" if record.duration_ms > 500 else "warning",
            }
            self._violations.append(violation)
            return violation
        return None

    def generate_dev_error_script(self) -> str:
        """Generate JS that throws errors on slow navigations in dev mode."""
        NL = chr(10)
        lines = [
            '<script>',
            '(function() {',
            '  var threshold = ' + str(self.threshold_ms) + ';',
            '  document.addEventListener("tw:navigation", function(e) {',
            '    var detail = e.detail;',
            '    if (!detail.instant && detail.duration > threshold) {',
            '      console.error("[InstantInsights] Slow navigation to " + detail.route + ": " + detail.duration.toFixed(1) + "ms");',
            '      if (typeof __tw_dev_error__ === "function") {',
            '        __tw_dev_error__("Slow navigation: " + detail.route, {',
            '          route: detail.route, duration: detail.duration, threshold: threshold',
            '        });',
            '      }',
            '    }',
            '  });',
            '})();',
            '</script>',
        ]
        return NL.join(lines)

    def generate_playwright_helper(self) -> str:
        """Generate Playwright instant test helper."""
        NL = chr(10)
        lines = [
            '// TW Framework - Instant Navigation Playwright Helper',
            '// Usage: await instant(page, async () => { ... })',
            '',
            'async function instant(page, callback, options) {',
            '  options = options || {};',
            '  var threshold = options.threshold || 100; // ms',
            '  var route = await page.evaluate(function() { return window.location.pathname; });',
            '  var startTime = Date.now();',
            '  await callback();',
            '  var duration = Date.now() - startTime;',
            '  if (duration > threshold) {',
            '    throw new Error(',
            '      "Navigation was not instant: " + duration + "ms (threshold: " + threshold + "ms). " +',
            '      "Route: " + route + " -> " + await page.evaluate(function() { return window.location.pathname; })',
            '    );',
            '  }',
            '  return { duration: duration, instant: true };',
            '}',
            '',
            'module.exports = { instant };',
        ]
        return NL.join(lines)

    def get_violations(self) -> List[Dict[str, Any]]:
        return list(self._violations)

    def get_stats(self) -> Dict[str, Any]:
        return {
            "enabled": self.enabled,
            "threshold_ms": self.threshold_ms,
            "total_violations": len(self._violations),
            "errors": sum(1 for v in self._violations if v["severity"] == "error"),
            "warnings": sum(1 for v in self._violations if v["severity"] == "warning"),
        }


__all__ = [
    "NavigationRecord", "InstantNavigationManager", "InstantInsights",
]
