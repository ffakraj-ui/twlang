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
