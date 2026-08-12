"""
TW Framework — Client-side Prefetching (v0.9.08)

Automatically prefetches pages on hover/viewport. Like Next.js next/link.
"""

from __future__ import annotations


PREFETCH_SCRIPT = """
<script>
(function() {
    var prefetched = {};
    var PREFETCH_LIMIT = 10;

    function isInternal(href) {
        if (!href) return false;
        if (href.startsWith("http") && !href.includes(window.location.hostname)) return false;
        if (href.startsWith("#") || href.startsWith("mailto:") || href.startsWith("tel:")) return false;
        if (href.startsWith("javascript:")) return false;
        return true;
    }

    function prefetch(url) {
        if (prefetched[url]) return;
        if (Object.keys(prefetched).length >= PREFETCH_LIMIT) return;
        prefetched[url] = "loading";
        fetch(url, {
            method: "GET",
            headers: { "X-TW-Prefetch": "1" },
            credentials: "same-origin",
        }).then(function(resp) {
            if (resp.ok) { prefetched[url] = "ready"; }
            else { delete prefetched[url]; }
        }).catch(function() { delete prefetched[url]; });
    }

    document.addEventListener("mouseover", function(e) {
        var link = e.target.closest("a");
        if (link && isInternal(link.getAttribute("href"))) {
            var url = link.getAttribute("href");
            if (url && !url.startsWith("http")) url = window.location.origin + url;
            prefetch(url);
        }
    }, true);

    if ("IntersectionObserver" in window) {
        var observer = new IntersectionObserver(function(entries) {
            entries.forEach(function(entry) {
                if (entry.isIntersecting) {
                    var link = entry.target;
                    var href = link.getAttribute("href");
                    if (href && isInternal(href)) {
                        if (!href.startsWith("http")) href = window.location.origin + href;
                        prefetch(href);
                    }
                    observer.unobserve(link);
                }
            });
        }, { rootMargin: "100px" });

        function observeLinks() {
            document.querySelectorAll("a[href]").forEach(function(link) {
                if (isInternal(link.getAttribute("href"))) observer.observe(link);
            });
        }
        if (document.readyState === "loading") {
            document.addEventListener("DOMContentLoaded", observeLinks);
        } else { observeLinks(); }
    }
})();
</script>
"""


def get_prefetch_script() -> str:
    return PREFETCH_SCRIPT


# ── Incremental Prefetching (#17) ───────────────────────────────────
# Only prefetch uncached segments, not entire pages


class IncrementalPrefetcher:
    """Incremental prefetching — only prefetch uncached route segments.

    Instead of prefetching entire pages, this system:
    1. Checks which route segments are already cached on the client
    2. Only fetches the segments that are missing
    3. Merges new segments with cached ones
    4. Reduces bandwidth and improves load time
    """

    def __init__(self):
        self._prefetched_segments: set = set()
        self._segment_cache: dict = {}
        self._max_concurrent = 3
        self._prefetch_queue: list = []

    def should_prefetch(self, route: str, segment: str = "") -> bool:
        """Check if a segment needs prefetching."""
        key = route + "/" + segment if segment else route
        return key not in self._prefetched_segments

    def mark_prefetched(self, route: str, segment: str = "") -> None:
        """Mark a segment as prefetched."""
        key = route + "/" + segment if segment else route
        self._prefetched_segments.add(key)

    def get_uncached_segments(self, route: str, segments: list) -> list:
        """Filter list to only uncached segments."""
        return [s for s in segments if self.should_prefetch(route, s)]

    def generate_incremental_script(self) -> str:
        """Generate JS for incremental prefetching."""
        NL = chr(10)
        lines = [
            '<script>',
            '(function() {',
            '  var prefetched = {};',
            '  function prefetchSegment(route, segment) {',
            '    var key = route + "/" + segment;',
            '    if (prefetched[key]) return;',
            '    prefetched[key] = true;',
            '    var link = document.createElement("link");',
            '    link.rel = "prefetch";',
            '    link.href = "/__tw/segment?route=" + encodeURIComponent(route) + "&segment=" + encodeURIComponent(segment);',
            '    link.as = "fetch";',
            '    document.head.appendChild(link);',
            '  }',
            '  function prefetchRoute(route, segments) {',
            '    if (!segments) {',
            '      prefetchSegment(route, "");',
            '      return;',
            '    }',
            '    segments.forEach(function(seg) {',
            '      var key = route + "/" + seg;',
            '      if (!prefetched[key]) { prefetchSegment(route, seg); }',
            '    });',
            '  }',
            '  window.__tw_incremental_prefetch__ = {',
            '    prefetch: prefetchRoute,',
            '    isCached: function(route, segment) {',
            '      return !!prefetched[route + "/" + segment];',
            '    },',
            '    getCached: function() { return Object.keys(prefetched); }',
            '  };',
            '  // Auto-prefetch visible links',
            '  document.querySelectorAll("a[href]").forEach(function(link) {',
            '    var href = link.getAttribute("href");',
            '    if (href && href.startsWith("/") && !href.startsWith("/api/")) {',
            '      link.addEventListener("mouseenter", function() {',
            '        prefetchRoute(href, null);',
            '      }, { once: true });',
            '    }',
            '  });',
            '})();',
            '</script>',
        ]
        return NL.join(lines)

    def get_stats(self) -> dict:
        return {
            "prefetched_count": len(self._prefetched_segments),
            "cached_segments": len(self._segment_cache),
            "queue_length": len(self._prefetch_queue),
        }


# ── Layout Deduplication (#18) ──────────────────────────────────────
# Shared layouts download once, not multiple times


class LayoutDeduplicator:
    """Layout deduplication — shared layouts downloaded once.

    When navigating between routes that share a layout:
    1. The layout is NOT re-downloaded
    2. Only the changed content area is fetched
    3. The layout persists across navigations
    4. Reduces bandwidth and improves navigation speed
    """

    def __init__(self):
        self._active_layouts: dict = {}  # route -> layout data
        self._layout_cache: dict = {}     # layout_name -> cached HTML
        self._shared_layouts: dict = {}   # parent_route -> [child_routes]

    def register_shared_layout(self, parent_route: str, child_routes: list) -> None:
        """Register that child routes share a parent layout."""
        self._shared_layouts[parent_route] = child_routes

    def should_keep_layout(self, old_route: str, new_route: str) -> bool:
        """Check if layout should be kept when navigating from old to new route."""
        for parent, children in self._shared_layouts.items():
            if old_route in children and new_route in children:
                return True
        return False

    def cache_layout(self, layout_name: str, html: str) -> None:
        """Cache a layout's HTML."""
        self._layout_cache[layout_name] = html

    def get_cached_layout(self, layout_name: str) -> str:
        """Get cached layout HTML."""
        return self._layout_cache.get(layout_name, "")

    def get_navigation_diff(self, old_route: str, new_route: str) -> dict:
        """Determine what needs to change when navigating between routes."""
        keep_layout = self.should_keep_layout(old_route, new_route)
        return {
            "old_route": old_route,
            "new_route": new_route,
            "keep_layout": keep_layout,
            "fetch_content_only": keep_layout,
            "layout_change": not keep_layout,
        }

    def generate_layout_script(self) -> str:
        """Generate JS for layout deduplication."""
        NL = chr(10)
        lines = [
            '<script>',
            '(function() {',
            '  var currentLayout = null;',
            '  var layoutCache = {};',
            '  window.__tw_layout__ = {',
            '    setLayout: function(name, html) {',
            '      currentLayout = name;',
            '      layoutCache[name] = html;',
            '    },',
            '    getLayout: function(name) {',
            '      return layoutCache[name] || null;',
            '    },',
            '    shouldKeepLayout: function(newRoute) {',
            '      return currentLayout && newRoute.startsWith(currentLayout.split("/").slice(0, -1).join("/"));',
            '    },',
            '    getCurrentLayout: function() { return currentLayout; }',
            '  };',
            '})();',
            '</script>',
        ]
        return NL.join(lines)

    def get_stats(self) -> dict:
        return {
            "active_layouts": len(self._active_layouts),
            "cached_layouts": len(self._layout_cache),
            "shared_layout_groups": len(self._shared_layouts),
        }
