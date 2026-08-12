"""
TW Framework - Streaming & Web Vitals Optimization

Implements:
11. Streaming & Web Vitals Optimization (TTFB, FCP, LCP, CLS, INP)
"""

from __future__ import annotations
import time, json, logging
from dataclasses import dataclass, field
from typing import Any, Callable, Dict, List, Optional
import logging

logger = logging.getLogger(__name__)


@dataclass
class WebVitalMetric:
    """A single Web Vital metric."""
    name: str  # TTFB, FCP, LCP, CLS, INP
    value: float
    rating: str = ""  # good | needs-improvement | poor
    timestamp: float = field(default_factory=time.time)
    route: str = ""


@dataclass
class StreamingConfig:
    """Configuration for streaming optimization."""
    send_static_shell_immediately: bool = True
    stream_dynamic_content: bool = True
    max_stream_timeout_ms: int = 30000
    chunk_size: int = 4096  # bytes per chunk
    flush_interval_ms: int = 50  # flush interval for streaming


class WebVitalsOptimizer:
    """Web Vitals optimization and monitoring.

    Tracks and optimizes Core Web Vitals:
    - TTFB (Time to First Byte): Server sends static shell immediately
    - FCP (First Contentful Paint): Optimize initial render
    - LCP (Largest Contentful Paint): Keep LCP elements out of Suspense
    - CLS (Cumulative Layout Shift): Use skeleton fallbacks
    - INP (Interaction to Next Paint): Selective hydration
    """

    # Rating thresholds (Google's official thresholds)
    THRESHOLDS = {
        "TTFB": {"good": 800, "poor": 1800},     # ms
        "FCP": {"good": 1800, "poor": 3000},     # ms
        "LCP": {"good": 2500, "poor": 4000},     # ms
        "CLS": {"good": 0.1, "poor": 0.25},      # score
        "INP": {"good": 200, "poor": 500},       # ms
    }

    def __init__(self):
        self._metrics: List[WebVitalMetric] = []
        self._recommendations: List[str] = []
        self._streaming_config = StreamingConfig()

    def record_metric(self, name: str, value: float, route: str = "") -> WebVitalMetric:
        """Record a Web Vital metric."""
        rating = self._rate_metric(name, value)
        metric = WebVitalMetric(name=name, value=value, rating=rating, route=route)
        self._metrics.append(metric)
        if len(self._metrics) > 1000:
            self._metrics = self._metrics[-1000:]
        return metric

    def _rate_metric(self, name: str, value: float) -> str:
        """Rate a metric value as good/needs-improvement/poor."""
        thresholds = self.THRESHOLDS.get(name)
        if not thresholds:
            return "unknown"
        if value <= thresholds["good"]:
            return "good"
        elif value <= thresholds["poor"]:
            return "needs-improvement"
        else:
            return "poor"

    def generate_recommendations(self) -> List[str]:
        """Generate optimization recommendations based on metrics."""
        self._recommendations.clear()

        for metric in self._metrics[-50:]:  # Last 50 metrics
            if metric.rating == "poor":
                if metric.name == "TTFB":
                    self._recommendations.append(
                        "TTFB is " + str(int(metric.value)) + "ms — enable streaming to send static shell immediately"
                    )
                elif metric.name == "LCP":
                    self._recommendations.append(
                        "LCP is " + str(int(metric.value)) + "ms — move LCP elements outside Suspense boundaries"
                    )
                elif metric.name == "CLS":
                    self._recommendations.append(
                        "CLS is " + str(metric.value) + " — use skeleton fallbacks with fixed dimensions"
                    )
                elif metric.name == "INP":
                    self._recommendations.append(
                        "INP is " + str(int(metric.value)) + "ms — enable selective hydration to keep main thread responsive"
                    )
                elif metric.name == "FCP":
                    self._recommendations.append(
                        "FCP is " + str(int(metric.value)) + "ms — reduce initial bundle size and enable PPR"
                    )

        # Deduplicate
        self._recommendations = list(dict.fromkeys(self._recommendations))
        return self._recommendations

    def get_metrics_summary(self) -> Dict[str, Any]:
        """Get summary of all metrics by name."""
        summary: Dict[str, Any] = {}
        for name in self.THRESHOLDS:
            metrics = [m for m in self._metrics if m.name == name]
            if metrics:
                values = [m.value for m in metrics]
                summary[name] = {
                    "count": len(values),
                    "avg": round(sum(values) / len(values), 2),
                    "min": round(min(values), 2),
                    "max": round(max(values), 2),
                    "last": round(values[-1], 2),
                    "rating": self._rate_metric(name, values[-1]),
                }
        return summary

    def generate_monitoring_script(self) -> str:
        """Generate JS for collecting Web Vitals from the browser."""
        NL = chr(10)
        lines = [
            '<script>',
            '(function() {',
            '  function sendMetric(name, value) {',
            '    navigator.sendBeacon("/__tw/web-vitals", JSON.stringify({',
            '      name: name, value: value, route: location.pathname, timestamp: Date.now()',
            '    }));',
            '  }',
            '  // TTFB',
            '  var navEntry = performance.getEntriesByType("navigation")[0];',
            '  if (navEntry) {',
            '    sendMetric("TTFB", navEntry.responseStart - navEntry.requestStart);',
            '  }',
            '  // FCP',
            '  new PerformanceObserver(function(list) {',
            '    list.getEntries().forEach(function(entry) { sendMetric("FCP", entry.startTime); });',
            '  }).observe({ type: "paint", buffered: true });',
            '  // LCP',
            '  new PerformanceObserver(function(list) {',
            '    var entries = list.getEntries();',
            '    if (entries.length) sendMetric("LCP", entries[entries.length - 1].startTime);',
            '  }).observe({ type: "largest-contentful-paint", buffered: true });',
            '  // CLS',
            '  var clsValue = 0;',
            '  new PerformanceObserver(function(list) {',
            '    list.getEntries().forEach(function(entry) {',
            '      if (!entry.hadRecentInput) clsValue += entry.value;',
            '    });',
            '    sendMetric("CLS", clsValue);',
            '  }).observe({ type: "layout-shift", buffered: true });',
            '  // INP',
            '  new PerformanceObserver(function(list) {',
            '    list.getEntries().forEach(function(entry) { sendMetric("INP", entry.duration); });',
            '  }).observe({ type: "interaction", buffered: true });',
            '})();',
            '</script>',
        ]
        return NL.join(lines)

    def generate_skeleton_css(self) -> str:
        """Generate CSS for skeleton fallbacks to minimize CLS."""
        return (
            '<style>'
            '.tw-skeleton { background: #e5e7eb; border-radius: 4px; animation: tw-skel 1.5s infinite; }'
            '.tw-skeleton-line { height: 1em; width: 100%; margin: 0.5em 0; }'
            '.tw-skeleton-short { width: 60%; }'
            '.tw-skeleton-block { height: 200px; width: 100%; }'
            '@keyframes tw-skel { 0%,100% { opacity: 1; } 50% { opacity: 0.5; } }'
            '</style>'
        )

    def get_stats(self) -> Dict[str, Any]:
        return {
            "total_metrics": len(self._metrics),
            "recommendations": len(self._recommendations),
            "summary": self.get_metrics_summary(),
        }


class StreamingOptimizer:
    """Optimizes streaming SSR for Web Vitals.

    Strategies:
    1. Send static shell immediately (lowers TTFB)
    2. Stream dynamic content as it resolves (lowers LCP)
    3. Use skeleton fallbacks (lowers CLS)
    4. Break hydration into chunks (lowers INP)
    5. Prioritize above-the-fold content (lowers FCP)
    """

    def __init__(self, config: Optional[StreamingConfig] = None):
        self.config = config or StreamingConfig()
        self._chunks_sent: int = 0
        self._total_bytes: int = 0

    def create_static_shell(self, head: str, body_skeleton: str) -> str:
        """Create the initial static shell to send immediately.

        This is the minimal HTML that gets the browser painting
        while dynamic content is still being rendered.
        """
        return (
            '<!DOCTYPE html><html><head>' + head + '</head>'
            '<body>' + body_skeleton +
            '<!-- tw-stream-start --></body></html>'
        )

    def create_stream_chunk(self, content: str, slot_id: str = "") -> bytes:
        """Create a streaming chunk for a specific slot."""
        chunk = '<div data-tw-stream="' + slot_id + '">' + content + '</div>'
        self._chunks_sent += 1
        self._total_bytes += len(chunk)
        return chunk.encode("utf-8")

    def create_final_chunk(self) -> bytes:
        """Create the final chunk that closes the stream."""
        return b"<!-- tw-stream-end -->"

    def create_hydration_script(self) -> str:
        """Generate JS for selective hydration (lowers INP).

        Breaks hydration into small tasks so the main thread
        stays responsive to user interactions.
        """
        NL = chr(10)
        lines = [
            '<script>',
            '(function() {',
            '  var boundaries = document.querySelectorAll("[data-tw-client]");',
            '  var queue = Array.from(boundaries);',
            '  function hydrateNext() {',
            '    if (queue.length === 0) return;',
            '    var el = queue.shift();',
            '    var moduleId = el.getAttribute("data-tw-client");',
            '    var comp = window.__tw_modules__ && window.__tw_modules__[moduleId];',
            '    if (comp && comp.render) {',
            '      try { el.innerHTML = comp.render(JSON.parse(el.getAttribute("data-tw-props") || "{}"));',
            '        el.setAttribute("data-tw-hydrated", "true"); } catch(e) {}',
            '    }',
            '    // Schedule next hydration as a microtask',
            '    if (queue.length > 0) setTimeout(hydrateNext, 0);',
            '  }',
            '  // Start hydration after first paint',
            '  requestAnimationFrame(function() { setTimeout(hydrateNext, 0); });',
            '})();',
            '</script>',
        ]
        return NL.join(lines)

    def get_stats(self) -> Dict[str, Any]:
        return {
            "chunks_sent": self._chunks_sent,
            "total_bytes": self._total_bytes,
            "config": {
                "static_shell": self.config.send_static_shell_immediately,
                "stream_dynamic": self.config.stream_dynamic_content,
                "max_timeout_ms": self.config.max_stream_timeout_ms,
                "chunk_size": self.config.chunk_size,
            },
        }


__all__ = [
    "WebVitalMetric", "StreamingConfig",
    "WebVitalsOptimizer", "StreamingOptimizer",
]
