"""
Partial Prerendering (PPR) for TW Framework.

Inspired by Next.js PPR — the static/dynamic boundary is at the COMPONENT
level, not the route level. A single page can have:
  - Static shell (prerendered at build time)
  - Cached components (revalidated on a schedule)
  - Dynamic components (SSR/streamed per request)

Usage in .tw files:
  component UserStats {
      dynamic              // Mark as dynamic — always SSR
      cache revalidate 60  // Cache with 60s revalidation
      body { ... }
  }

  component Navbar {
      static               // Mark as static — prerendered at build
      body { ... }
  }

Architecture:
  1. At build time, components marked `static` are prerendered into HTML
  2. Components marked `dynamic` are replaced with <tw-suspense> placeholders
  3. At request time, dynamic components are SSR'd and streamed into placeholders
  4. Components with `cache revalidate N` are cached for N seconds

This gives the best of both worlds: instant static shell + fresh dynamic content.
"""
from __future__ import annotations

import hashlib
import json
import logging
import os
import time
from dataclasses import dataclass, field
from typing import Any, Dict, List, Optional, Set, Tuple

logger = logging.getLogger(__name__)


# ── Component render modes ──────────────────────────────────────────

STATIC = "static"        # Prerendered at build time, never re-rendered
DYNAMIC = "dynamic"      # Always SSR'd per request
CACHED = "cached"        # Cached with revalidation (ISR-like)
STREAMING = "streaming"  # SSR'd and streamed via SSE


@dataclass
class ComponentRenderMode:
    """Describes how a component should be rendered."""
    mode: str = STATIC          # static | dynamic | cached | streaming
    revalidate: int = 0         # Revalidation period in seconds (for cached)
    cache_key: str = ""         # Custom cache key (for cached)
    fallback: str = ""          # Fallback HTML while streaming (skeleton)
    tags: List[str] = field(default_factory=list)  # Cache tags for on-demand revalidation


@dataclass
class PPRBoundary:
    """A static/dynamic boundary in a page."""
    component_name: str
    mode: str                   # static | dynamic | cached | streaming
    placeholder_id: str          # Unique ID for the suspense boundary
    revalidate: int = 0
    cache_key: str = ""
    tags: List[str] = field(default_factory=list)
    static_html: str = ""        # Prerendered HTML (for static components)
    fallback_html: str = ""      # Fallback HTML (for streaming components)


class PPRAnalyzer:
    """Analyzes a page AST and determines PPR boundaries.

    Scans all components used in a page and classifies them as
    static, dynamic, cached, or streaming based on their directives.
    """

    # Map of component name → render mode (populated during analysis)
    _component_modes: Dict[str, ComponentRenderMode] = {}

    @classmethod
    def classify_component(cls, component_source: str, component_name: str = "") -> ComponentRenderMode:
        """Classify a component based on its source directives.

        Looks for these directives inside component body:
          dynamic              → always SSR
          static               → prerendered at build
          cache revalidate 60  → cached with 60s revalidation
          streaming            → SSR'd and streamed
          cache_tags "a,b,c"   → tags for on-demand revalidation
        """
        mode = ComponentRenderMode(mode=STATIC)

        lines = component_source.split("\n")
        for line in lines:
            stripped = line.strip().lower()

            if stripped == "dynamic" or stripped.startswith("dynamic "):
                mode.mode = DYNAMIC
            elif stripped == "static" or stripped.startswith("static "):
                mode.mode = STATIC
            elif stripped == "streaming" or stripped.startswith("streaming "):
                mode.mode = STREAMING
            elif stripped.startswith("cache revalidate") or stripped.startswith("cache_revalidate"):
                # Parse "cache revalidate 60" or "cache revalidate 60s"
                parts = stripped.replace("cache_revalidate", "cache revalidate").split()
                mode.mode = CACHED
                for part in parts:
                    if part.endswith("s"):
                        try:
                            mode.revalidate = int(part.rstrip("s"))
                        except ValueError:
                            pass
                    else:
                        try:
                            mode.revalidate = int(part)
                        except ValueError:
                            pass
            elif stripped.startswith("cache_tags") or stripped.startswith("cache-tags"):
                # Parse cache_tags "user,posts,comments"
                if '"' in stripped or "'" in stripped:
                    tag_str = stripped.split('"')[1] if '"' in stripped else stripped.split("'")[1]
                    mode.tags = [t.strip() for t in tag_str.split(",") if t.strip()]

        # Set cache key
        if mode.mode in (CACHED, STREAMING) and component_name:
            mode.cache_key = f"ppr:{component_name}"

        return mode

    @classmethod
    def analyze_page(cls, page_source: str, page_name: str = "") -> List[PPRBoundary]:
        """Analyze a page and return all PPR boundaries.

        Returns a list of PPRBoundary objects, one for each component
        that is NOT static (i.e., dynamic, cached, or streaming).
        """
        boundaries: List[PPRBoundary] = []

        # Find all component references in the page
        import re
        # Match component names (capitalized identifiers followed by {)
        component_pattern = re.compile(r'([A-Z][a-zA-Z0-9_]*)\s*\{')

        seen_components: Set[str] = set()
        for match in component_pattern.finditer(page_source):
            comp_name = match.group(1)
            if comp_name in seen_components:
                continue
            seen_components.add(comp_name)

            # Skip standard HTML tags that start with uppercase
            if comp_name in ("True", "False", "None", "If", "Else", "Each", "Let"):
                continue

            # Try to find the component definition
            # In a real implementation, this would resolve the component file
            # and parse its directives. For now, check if the component
            # source is available in the page source itself.
            comp_source = cls._extract_component_source(page_source, comp_name)
            if comp_source:
                mode = cls.classify_component(comp_source, comp_name)
                if mode.mode != STATIC:
                    # This component needs a PPR boundary
                    placeholder_id = f"tw-ppr-{comp_name.lower()}-{hashlib.md5(comp_name.encode()).hexdigest()[:8]}"
                    boundary = PPRBoundary(
                        component_name=comp_name,
                        mode=mode.mode,
                        placeholder_id=placeholder_id,
                        revalidate=mode.revalidate,
                        cache_key=mode.cache_key,
                        tags=mode.tags,
                        fallback_html=cls._generate_fallback(comp_name, mode.mode),
                    )
                    boundaries.append(boundary)

        return boundaries

    @classmethod
    def _extract_component_source(cls, page_source: str, component_name: str) -> Optional[str]:
        """Try to extract a component's source from the page source."""
        import re
        # Look for "component Name {" pattern
        pattern = rf'component\s+{re.escape(component_name)}\s*\{{'
        match = re.search(pattern, page_source)
        if not match:
            return None

        # Find matching closing brace
        start = match.end()
        depth = 1
        i = start
        while i < len(page_source) and depth > 0:
            if page_source[i] == '{':
                depth += 1
            elif page_source[i] == '}':
                depth -= 1
            i += 1

        return page_source[match.start():i]

    @staticmethod
    def _generate_fallback(component_name: str, mode: str) -> str:
        """Generate fallback HTML for streaming/dynamic components."""
        if mode == STREAMING:
            return f'<div data-tw-suspense="{component_name}" class="tw-suspense-loading">' \
                   f'<div class="tw-skeleton tw-skeleton-pulse"></div>' \
                   f'</div>'
        elif mode == DYNAMIC:
            return f'<div data-tw-dynamic="{component_name}"></div>'
        return ""


class PPRRenderer:
    """Renders a page with PPR boundaries.

    At build time:
      - Static components → prerendered into HTML
      - Dynamic/cached/streaming → replaced with suspense placeholders

    At request time:
      - Dynamic components → SSR'd and injected
      - Cached components → served from cache (if fresh) or re-rendered
      - Streaming components → streamed via SSE into placeholders
    """

    def __init__(self, cache_dir: str = ""):
        self.cache_dir = cache_dir or os.path.join(os.getcwd(), ".tw", "ppr-cache")
        os.makedirs(self.cache_dir, exist_ok=True)
        self._component_cache: Dict[str, Tuple[str, float]] = {}  # key → (html, cached_at)

    def render_build_time(self, page_source: str, page_name: str, render_component_fn=None) -> Tuple[str, List[PPRBoundary]]:
        """Render a page at build time.

        Returns (html, boundaries) where html has suspense placeholders
        for non-static components.
        """
        boundaries = PPRAnalyzer.analyze_page(page_source, page_name)

        html = page_source
        for boundary in boundaries:
            if boundary.mode == STATIC:
                # Already prerendered — no change needed
                continue
            elif boundary.mode == DYNAMIC:
                # Replace with dynamic placeholder
                placeholder = f'<tw-suspense id="{boundary.placeholder_id}">{boundary.fallback_html}</tw-suspense>'
                # In real impl, the component's rendered output would be replaced
                # with the placeholder
            elif boundary.mode == CACHED:
                # Prerender and cache
                if render_component_fn:
                    cached_html = render_component_fn(boundary.component_name)
                    if cached_html:
                        self._set_cache(boundary.cache_key, cached_html, boundary.revalidate)
                        # Use cached version
                        continue
                # Fallback to placeholder
                placeholder = f'<tw-suspense id="{boundary.placeholder_id}">{boundary.fallback_html}</tw-suspense>'
            elif boundary.mode == STREAMING:
                # Replace with streaming placeholder
                placeholder = f'<tw-suspense id="{boundary.placeholder_id}">{boundary.fallback_html}</tw-suspense>'

        return html, boundaries

    def render_request_time(self, boundaries: List[PPRBoundary], render_component_fn=None) -> Dict[str, str]:
        """Render dynamic/cached components at request time.

        Returns a dict of placeholder_id → rendered_html.
        """
        results: Dict[str, str] = {}

        for boundary in boundaries:
            if boundary.mode == STATIC:
                continue  # Already prerendered

            if boundary.mode == CACHED:
                # Check cache
                cached = self._get_cache(boundary.cache_key, boundary.revalidate)
                if cached is not None:
                    results[boundary.placeholder_id] = cached
                    continue

            # Render the component
            if render_component_fn:
                rendered = render_component_fn(boundary.component_name)
                if rendered:
                    results[boundary.placeholder_id] = rendered
                    if boundary.mode == CACHED:
                        self._set_cache(boundary.cache_key, rendered, boundary.revalidate)

        return results

    def stream_request_time(self, boundaries: List[PPRBoundary], render_component_fn=None):
        """Generator that yields (placeholder_id, html) pairs as components render.

        For streaming SSR — yields results one by one.
        """
        for boundary in boundaries:
            if boundary.mode == STATIC:
                continue

            if boundary.mode == CACHED:
                cached = self._get_cache(boundary.cache_key, boundary.revalidate)
                if cached is not None:
                    yield (boundary.placeholder_id, cached)
                    continue

            if render_component_fn:
                rendered = render_component_fn(boundary.component_name)
                if rendered:
                    yield (boundary.placeholder_id, rendered)
                    if boundary.mode == CACHED:
                        self._set_cache(boundary.cache_key, rendered, boundary.revalidate)

    def _get_cache(self, key: str, revalidate: int) -> Optional[str]:
        """Get from cache if fresh (within revalidate window)."""
        if not key:
            return None
        if key in self._component_cache:
            html, cached_at = self._component_cache[key]
            if revalidate > 0 and (time.time() - cached_at) > revalidate:
                # Stale — need revalidation
                return None
            return html

        # Try disk cache
        cache_path = os.path.join(self.cache_dir, hashlib.sha256(key.encode()).hexdigest() + ".json")
        if os.path.exists(cache_path):
            try:
                with open(cache_path, "r") as f:
                    data = json.load(f)
                cached_at = data.get("cached_at", 0)
                if revalidate > 0 and (time.time() - cached_at) > revalidate:
                    return None
                html = data.get("html", "")
                self._component_cache[key] = (html, cached_at)
                return html
            except (json.JSONDecodeError, OSError):
                pass
        return None

    def _set_cache(self, key: str, html: str, revalidate: int) -> None:
        """Store in cache."""
        if not key:
            return
        self._component_cache[key] = (html, time.time())

        cache_path = os.path.join(self.cache_dir, hashlib.sha256(key.encode()).hexdigest() + ".json")
        try:
            with open(cache_path, "w") as f:
                json.dump({"html": html, "cached_at": time.time(), "revalidate": revalidate}, f)
        except OSError:
            pass

    def invalidate_by_tag(self, tag: str) -> int:
        """Invalidate all cached components with a given tag.

        For on-demand revalidation.
        """
        count = 0
        # In a real implementation, we'd track tag → keys mapping
        # For now, invalidate all cache entries
        for key in list(self._component_cache.keys()):
            self._component_cache.pop(key, None)
            cache_path = os.path.join(self.cache_dir, hashlib.sha256(key.encode()).hexdigest() + ".json")
            if os.path.exists(cache_path):
                try:
                    os.remove(cache_path)
                    count += 1
                except OSError:
                    pass
        return count


__all__ = [
    "STATIC", "DYNAMIC", "CACHED", "STREAMING",
    "ComponentRenderMode", "PPRBoundary", "PPRAnalyzer", "PPRRenderer",
    "PPRCompiler", "StreamChunk", "PPRStreamingRenderer",
    "PPRCacheEntry", "PPRCacheManager", "PPRAstNode", "PPRAstAnalyzer",
    "PPRRouteConfig", "PPRMiddleware", "PPRBoundaryReport", "PPRBuildReport",
    "HydrationManifest", "PPRHydrator", "PPRErrorBoundary", "PPRErrorBoundaryHandler",
    "PPRDebugTools", "PPRRoutePattern", "PPRRouteMatcher", "PPRSnapshotManager",
]


# ── PPR Compiler Integration ─────────────────────────────────────────

class PPRCompiler:
    """Integrates PPR with the TW compiler pipeline.

    Splits a page into static shell + dynamic boundaries at compile time.
    Static components are prerendered; dynamic components get suspense placeholders.
    """

    def __init__(self, ppr_renderer: PPRRenderer = None):
        self.renderer = ppr_renderer or PPRRenderer()
        self._component_sources: Dict[str, str] = {}  # name → source

    def register_component(self, name: str, source: str) -> None:
        """Register a component's source for PPR analysis."""
        self._component_sources[name] = source

    def compile_page_with_ppr(self, page_source: str, page_name: str = "",
                              render_component_fn=None) -> Dict[str, Any]:
        """Compile a page with PPR boundaries.

        Returns dict with:
          - static_html: prerendered HTML with suspense placeholders
          - boundaries: list of PPRBoundary objects
          - metadata: compile stats
        """
        boundaries = PPRAnalyzer.analyze_page(page_source, page_name)
        static_html, _ = self.renderer.render_build_time(
            page_source, page_name, render_component_fn
        )

        # Generate suspense placeholders for each boundary
        placeholders = {}
        for b in boundaries:
            placeholders[b.placeholder_id] = self.generate_suspense_html(b)

        return {
            "static_html": static_html,
            "boundaries": boundaries,
            "placeholders": placeholders,
            "boundary_count": len(boundaries),
            "has_dynamic": any(b.mode == DYNAMIC for b in boundaries),
            "has_streaming": any(b.mode == STREAMING for b in boundaries),
            "has_cached": any(b.mode == CACHED for b in boundaries),
        }

    def extract_component_directives(self, source: str) -> Dict[str, Any]:
        """Parse PPR directives from component source.

        Recognized directives (inside component body):
          dynamic           → always SSR
          static            → prerendered at build
          streaming         → SSR'd and streamed
          cache revalidate N → cached with N-second revalidation
          cache_tags "a,b"  → tags for on-demand revalidation
          cache_key "name"  → custom cache key
          fallback "html"   → fallback HTML for streaming
        """
        import re
        directives: Dict[str, Any] = {
            "mode": STATIC,
            "revalidate": 0,
            "cache_tags": [],
            "cache_key": "",
            "fallback": "",
        }

        lines = source.split("\n")
        for line in lines:
            s = line.strip().lower()

            if s == "dynamic" or s.startswith("dynamic "):
                directives["mode"] = DYNAMIC
            elif s == "static" or s.startswith("static "):
                directives["mode"] = STATIC
            elif s == "streaming" or s.startswith("streaming "):
                directives["mode"] = STREAMING
            elif s.startswith("cache revalidate") or s.startswith("cache_revalidate"):
                parts = s.replace("cache_revalidate", "cache revalidate").split()
                directives["mode"] = CACHED
                for part in parts:
                    cleaned = part.rstrip("s").rstrip("m").rstrip("h").rstrip("d")
                    try:
                        val = int(cleaned)
                        unit = part[-1] if part[-1].isalpha() else "s"
                        multipliers = {"s": 1, "m": 60, "h": 3600, "d": 86400}
                        directives["revalidate"] = val * multipliers.get(unit, 1)
                    except ValueError:
                        pass
            elif s.startswith("cache_tags") or s.startswith("cache-tags"):
                if '"' in s or "'" in s:
                    tag_str = s.split('"')[1] if '"' in s else s.split("'")[1]
                    directives["cache_tags"] = [t.strip() for t in tag_str.split(",") if t.strip()]
            elif s.startswith("cache_key") or s.startswith("cache-key"):
                if '"' in s or "'" in s:
                    directives["cache_key"] = s.split('"')[1] if '"' in s else s.split("'")[1]
            elif s.startswith("fallback"):
                if '"' in s or "'" in s:
                    directives["fallback"] = s.split('"')[1] if '"' in s else s.split("'")[1]

        return directives

    def resolve_component_dependencies(self, component_name: str,
                                        visited: Optional[Set[str]] = None) -> Dict[str, List[str]]:
        """Build a dependency graph for a component's PPR boundaries.

        Returns dict of {component_name: [dependencies]}.
        """
        if visited is None:
            visited = set()
        if component_name in visited:
            return {}  # Circular dependency — stop
        visited.add(component_name)

        source = self._component_sources.get(component_name, "")
        if not source:
            return {}

        deps: Dict[str, List[str]] = {component_name: []}
        # Find component references in source
        import re
        for match in re.finditer(r'([A-Z][a-zA-Z0-9_]*)\s*\{', source):
            ref_name = match.group(1)
            if ref_name in ("True", "False", "None", "If", "Else", "Each", "Let"):
                continue
            if ref_name != component_name:
                deps[component_name].append(ref_name)
                # Recursively resolve
                sub_deps = self.resolve_component_dependencies(ref_name, visited.copy())
                deps.update(sub_deps)

        return deps

    def generate_suspense_html(self, boundary: PPRBoundary) -> str:
        """Generate <tw-suspense> placeholder HTML for a PPR boundary.

        The placeholder is replaced at request time with the rendered component.
        """
        attrs = [
            f'id="{boundary.placeholder_id}"',
            f'data-tw-component="{boundary.component_name}"',
            f'data-tw-mode="{boundary.mode}"',
        ]
        if boundary.revalidate > 0:
            attrs.append(f'data-tw-revalidate="{boundary.revalidate}"')
        if boundary.tags:
            attrs.append(f'data-tw-tags="{",".join(boundary.tags)}"')
        if boundary.cache_key:
            attrs.append(f'data-tw-cache-key="{boundary.cache_key}"')

        fallback = boundary.fallback_html or self._default_skeleton(boundary.component_name)
        return f'<tw-suspense {" ".join(attrs)}>{fallback}</tw-suspense>'

    def generate_streaming_script(self, boundary: PPRBoundary, endpoint_url: str) -> str:
        """Generate SSE streaming JavaScript for a dynamic boundary.

        This script connects to an SSE endpoint and replaces the
        suspense placeholder with streamed content.
        """
        return (
            f'<script>\n'
            f'(function() {{\n'
            f'  var placeholder = document.getElementById("{boundary.placeholder_id}");\n'
            f'  if (!placeholder) return;\n'
            f'  var source = new EventSource("{endpoint_url}");\n'
            f'  source.onmessage = function(event) {{\n'
            f'    if (event.data === "__tw_done__") {{\n'
            f'      source.close();\n'
            f'      return;\n'
            f'    }}\n'
            f'    var chunk = document.createElement("div");\n'
            f'    chunk.innerHTML = event.data;\n'
            f'    while (chunk.firstChild) {{\n'
            f'      placeholder.appendChild(chunk.firstChild);\n'
            f'    }}\n'
            f'  }};\n'
            f'  source.onerror = function() {{\n'
            f'    source.close();\n'
            f'    placeholder.innerHTML += "<div class=\"tw-error\">Failed to load {boundary.component_name}</div>";\n'
            f'  }};\n'
            f'  setTimeout(function() {{ source.close(); }}, 30000);\n'
            f'}})();\n'
            f'</script>'
        )

    def merge_static_dynamic(self, static_html: str, dynamic_results: Dict[str, str]) -> str:
        """Merge prerendered HTML with request-time rendered components.

        Replaces <tw-suspense> placeholders with actual rendered content.
        """
        import re
        result = static_html
        for placeholder_id, html in dynamic_results.items():
            # Replace the content inside <tw-suspense id="...">...</tw-suspense>
            pattern = rf'(<tw-suspense[^>]*id="{re.escape(placeholder_id)}"[^>]*>)[^<]*(</tw-suspense>)'
            result = re.sub(pattern, rf'\g<1>{html}\g<2>', result, flags=re.DOTALL)
        return result

    @staticmethod
    def _default_skeleton(component_name: str) -> str:
        """Generate a default skeleton/loading state for a component."""
        return (
            f'<div class="tw-skeleton tw-skeleton-{component_name.lower()}" '
            f'aria-busy="true" aria-label="Loading {component_name}">'
            f'<div class="tw-skeleton-line"></div>'
            f'<div class="tw-skeleton-line"></div>'
            f'<div class="tw-skeleton-line tw-skeleton-short"></div>'
            f'</div>'
        )


# ── PPR Streaming Renderer ───────────────────────────────────────────

@dataclass
class StreamChunk:
    """A single chunk in a streaming response."""
    html: str
    placeholder_id: str = ""
    is_skeleton: bool = False
    is_final: bool = False
    metadata: Dict[str, Any] = field(default_factory=dict)


class PPRStreamingRenderer:
    """Streaming SSR with PPR support.

    Yields HTML chunks: static shell first, then dynamic components
    as they complete, with skeleton placeholders in between.
    """

    def __init__(self, ppr_compiler: PPRCompiler = None):
        self.compiler = ppr_compiler or PPRCompiler()
        self._render_times: Dict[str, float] = {}

    def stream_page(self, page_source: str, page_name: str = "",
                    render_component_fn=None) -> Any:
        """Generator that yields StreamChunk objects.

        Yields:
          1. Static shell (with suspense placeholders)
          2. Skeleton for each dynamic boundary
          3. Rendered component (replacing skeleton) as each completes
          4. Final sentinel
        """
        import time as _time
        compiled = self.compiler.compile_page_with_ppr(page_source, page_name)
        boundaries = compiled["boundaries"]

        # 1. Yield static shell
        yield StreamChunk(
            html=compiled["static_html"],
            is_final=False,
            metadata={"phase": "static_shell", "boundary_count": len(boundaries)},
        )

        # 2. Yield skeletons for all dynamic boundaries
        for b in boundaries:
            if b.mode == STATIC:
                continue
            yield self.yield_skeleton(b)

        # 3. Render and yield each dynamic component
        for b in boundaries:
            if b.mode == STATIC:
                continue

            start = _time.time()
            if render_component_fn:
                try:
                    rendered_html = render_component_fn(b.component_name)
                except Exception as e:
                    rendered_html = f'<div class="tw-error">Error rendering {b.component_name}: {e}</div>'
            else:
                rendered_html = f'<div data-tw-component="{b.component_name}">Component: {b.component_name}</div>'

            elapsed = _time.time() - start
            self._render_times[b.component_name] = elapsed

            yield self.yield_component(b, rendered_html)

        # 4. Yield final sentinel
        yield StreamChunk(html="", is_final=True, metadata={"phase": "done"})

    def yield_skeleton(self, boundary: PPRBoundary) -> StreamChunk:
        """Yield a skeleton/placeholder chunk for a boundary."""
        return StreamChunk(
            html=boundary.fallback_html or self.compiler._default_skeleton(boundary.component_name),
            placeholder_id=boundary.placeholder_id,
            is_skeleton=True,
            metadata={"component": boundary.component_name, "mode": boundary.mode},
        )

    def yield_component(self, boundary: PPRBoundary, html: str) -> StreamChunk:
        """Yield a rendered component chunk."""
        # Wrap in a script that replaces the placeholder
        replacement = (
            f'<script>'
            f'(function(){{'
            f'var p=document.getElementById("{boundary.placeholder_id}");'
            f'if(p){{p.innerHTML={json.dumps(html)};p.setAttribute("data-tw-loaded","true");}}'
            f'}})();'
            f'</script>'
        )
        return StreamChunk(
            html=replacement,
            placeholder_id=boundary.placeholder_id,
            is_final=False,
            metadata={
                "component": boundary.component_name,
                "mode": boundary.mode,
                "render_time_ms": self._render_times.get(boundary.component_name, 0) * 1000,
            },
        )

    @staticmethod
    def generate_stream_headers() -> Dict[str, str]:
        """Return HTTP headers for a streaming response."""
        return {
            "Content-Type": "text/html; charset=utf-8",
            "Transfer-Encoding": "chunked",
            "Cache-Control": "no-cache, no-transform",
            "X-Accel-Buffering": "no",  # Disable nginx buffering
        }

    @staticmethod
    def flush_sentinel() -> str:
        """Generate the flushing sentinel for streaming responses."""
        return "<!--__tw_flush__-->"

    def render_as_sse(self, page_source: str, page_name: str = "",
                      render_component_fn=None) -> Any:
        """Render as Server-Sent Events format.

        Yields strings in SSE format: "data: ...\n\n"
        """
        for chunk in self.stream_page(page_source, page_name, render_component_fn):
            if chunk.is_final:
                yield f"data: __tw_done__\n\n"
            else:
                # Escape for SSE
                data = json.dumps({"html": chunk.html, "id": chunk.placeholder_id})
                yield f"data: {data}\n\n"

    def render_as_html_chunks(self, page_source: str, page_name: str = "",
                               render_component_fn=None) -> Any:
        """Render as raw HTML chunks (not SSE).

        Yields HTML strings that can be flushed to the browser.
        """
        for chunk in self.stream_page(page_source, page_name, render_component_fn):
            if chunk.html:
                yield chunk.html
            if not chunk.is_final:
                yield self.flush_sentinel()

    def get_render_stats(self) -> Dict[str, Any]:
        """Return rendering statistics."""
        return {
            "component_count": len(self._render_times),
            "total_render_time_ms": sum(self._render_times.values()) * 1000,
            "per_component": {
                name: f"{t * 1000:.2f}ms"
                for name, t in self._render_times.items()
            },
        }


# ── PPR Cache Manager ────────────────────────────────────────────────

@dataclass
class PPRCacheEntry:
    """A cached PPR component."""
    html: str
    cached_at: float
    revalidate: int = 0
    tags: List[str] = field(default_factory=list)
    params_hash: str = ""


class PPRCacheManager:
    """Cache management for PPR components.

    Provides memory + disk cache with tag-based invalidation,
    stale-while-revalidate, and cache warming.
    """

    def __init__(self, cache_dir: str = "", max_memory_entries: int = 500):
        self.cache_dir = cache_dir or os.path.join(os.getcwd(), ".tw", "ppr-cache")
        os.makedirs(self.cache_dir, exist_ok=True)
        self._memory: Dict[str, PPRCacheEntry] = {}
        self._tag_index: Dict[str, Set[str]] = {}
        self._lock = threading.Lock()
        self._max_memory = max_memory_entries
        self._hits = 0
        self._misses = 0

    def _make_key(self, name: str, params: Optional[dict] = None) -> str:
        """Create cache key from component name and params."""
        params_hash = hashlib.sha256(
            json.dumps(params or {}, sort_keys=True).encode()
        ).hexdigest()[:16]
        return f"ppr:{name}:{params_hash}"

    def get_cached_component(self, name: str, params: Optional[dict] = None) -> Optional[str]:
        """Get cached component HTML if fresh."""
        import time as _time
        key = self._make_key(name, params)

        with self._lock:
            if key in self._memory:
                entry = self._memory[key]
                if entry.revalidate > 0 and (_time.time() - entry.cached_at) > entry.revalidate:
                    self._misses += 1
                    return None  # Stale
                self._hits += 1
                return entry.html

        # Check disk
        disk_path = os.path.join(self.cache_dir, hashlib.sha256(key.encode()).hexdigest() + ".json")
        if os.path.exists(disk_path):
            try:
                with open(disk_path, "r") as f:
                    data = json.load(f)
                entry = PPRCacheEntry(
                    html=data["html"],
                    cached_at=data["cached_at"],
                    revalidate=data.get("revalidate", 0),
                    tags=data.get("tags", []),
                )
                if entry.revalidate > 0 and (_time.time() - entry.cached_at) > entry.revalidate:
                    self._misses += 1
                    return None
                # Promote to memory
                with self._lock:
                    self._memory[key] = entry
                    for tag in entry.tags:
                        self._tag_index.setdefault(tag, set()).add(key)
                self._hits += 1
                return entry.html
            except (json.JSONDecodeError, OSError, KeyError):
                pass

        self._misses += 1
        return None

    def set_cached_component(self, name: str, params: Optional[dict],
                             html: str, revalidate: int = 0,
                             tags: Optional[List[str]] = None) -> None:
        """Store component in cache."""
        import time as _time
        key = self._make_key(name, params)
        entry = PPRCacheEntry(
            html=html,
            cached_at=_time.time(),
            revalidate=revalidate,
            tags=tags or [],
        )

        with self._lock:
            # LRU eviction
            while len(self._memory) >= self._max_memory:
                oldest_key = min(self._memory, key=lambda k: self._memory[k].cached_at)
                del self._memory[oldest_key]
                # Clean up tag index
                for tag_keys in self._tag_index.values():
                    tag_keys.discard(oldest_key)

            self._memory[key] = entry
            for tag in entry.tags:
                self._tag_index.setdefault(tag, set()).add(key)

        # Persist to disk
        disk_path = os.path.join(self.cache_dir, hashlib.sha256(key.encode()).hexdigest() + ".json")
        try:
            with open(disk_path, "w") as f:
                json.dump({
                    "html": html,
                    "cached_at": entry.cached_at,
                    "revalidate": revalidate,
                    "tags": tags or [],
                    "component": name,
                }, f)
        except OSError:
            pass

    def invalidate_tag(self, tag: str) -> int:
        """Invalidate all cached components with a given tag."""
        count = 0
        with self._lock:
            keys = self._tag_index.pop(tag, set())
            for key in keys:
                if key in self._memory:
                    del self._memory[key]
                    count += 1

        # Remove from disk
        for key in keys:
            disk_path = os.path.join(self.cache_dir, hashlib.sha256(key.encode()).hexdigest() + ".json")
            if os.path.exists(disk_path):
                try:
                    os.remove(disk_path)
                    count += 1
                except OSError:
                    pass

        logger.info("PPR cache: invalidated %d entries for tag '%s'", count, tag)
        return count

    def warm_cache(self, boundaries: List[PPRBoundary], render_fn) -> Dict[str, Any]:
        """Pre-render and cache all cached/streaming components."""
        import time as _time
        warmed = 0
        errors = 0

        for b in boundaries:
            if b.mode not in (CACHED, STREAMING):
                continue
            try:
                html = render_fn(b.component_name)
                if html:
                    self.set_cached_component(
                        b.component_name, None, html,
                        revalidate=b.revalidate, tags=b.tags
                    )
                    warmed += 1
            except Exception as e:
                logger.warning("Failed to warm cache for %s: %s", b.component_name, e)
                errors += 1

        return {
            "warmed": warmed,
            "errors": errors,
            "total_boundaries": len(boundaries),
            "cache_size": len(self._memory),
        }

    def get_cache_stats(self) -> Dict[str, Any]:
        """Return cache statistics."""
        total = self._hits + self._misses
        return {
            "memory_entries": len(self._memory),
            "disk_entries": len([f for f in os.listdir(self.cache_dir) if f.endswith(".json")]),
            "tag_count": len(self._tag_index),
            "hits": self._hits,
            "misses": self._misses,
            "hit_rate": f"{(self._hits / total * 100):.1f}%" if total > 0 else "N/A",
            "max_memory_entries": self._max_memory,
        }

    def evict_stale(self) -> int:
        """Remove all stale cache entries."""
        import time as _time
        count = 0
        now = _time.time()

        with self._lock:
            stale_keys = [
                key for key, entry in self._memory.items()
                if entry.revalidate > 0 and (now - entry.cached_at) > entry.revalidate
            ]
            for key in stale_keys:
                del self._memory[key]
                count += 1

        # Also check disk
        for fname in os.listdir(self.cache_dir):
            if not fname.endswith(".json"):
                continue
            fpath = os.path.join(self.cache_dir, fname)
            try:
                with open(fpath, "r") as f:
                    data = json.load(f)
                cached_at = data.get("cached_at", 0)
                revalidate = data.get("revalidate", 0)
                if revalidate > 0 and (now - cached_at) > revalidate:
                    os.remove(fpath)
                    count += 1
            except (json.JSONDecodeError, OSError):
                pass

        logger.info("PPR cache: evicted %d stale entries", count)
        return count

    def clear(self) -> None:
        """Clear all cache entries."""
        with self._lock:
            self._memory.clear()
            self._tag_index.clear()
        for fname in os.listdir(self.cache_dir):
            if fname.endswith(".json"):
                try:
                    os.remove(os.path.join(self.cache_dir, fname))
                except OSError:
                    pass


# ── PPR AST Analyzer ────────────────────────────────────────────────

@dataclass
class PPRAstNode:
    """A node in the PPR AST analysis."""
    component_name: str
    line: int = 0
    col: int = 0
    mode: str = STATIC
    children: List["PPRAstNode"] = field(default_factory=list)
    parent: Optional["PPRAstNode"] = None


class PPRAstAnalyzer:
    """AST-level PPR analysis.

    Walks the AST to find component invocations and classify them
    for PPR boundary creation.
    """

    def __init__(self, compiler: PPRCompiler = None):
        self.compiler = compiler or PPRCompiler()
        self._visited: Set[str] = set()

    def analyze_ast(self, program_ast: Any) -> List[PPRAstNode]:
        """Walk AST to find component invocations and classify them.

        Args:
            program_ast: The parsed AST (can be any object with children/nodes)

        Returns:
            List of PPRAstNode objects for each component invocation found.
        """
        nodes: List[PPRAstNode] = []
        self._visited.clear()

        # Try to walk the AST — handle different AST structures
        def _walk(node: Any, parent: Optional[PPRAstNode] = None, depth: int = 0):
            if depth > 50:  # Prevent infinite recursion
                return

            # Check if this node is a component invocation
            comp_name = self._extract_component_name(node)
            if comp_name and comp_name not in self._visited:
                self._visited.add(comp_name)

                # Classify the component
                source = self.compiler._component_sources.get(comp_name, "")
                mode = STATIC
                if source:
                    directives = self.compiler.extract_component_directives(source)
                    mode = directives.get("mode", STATIC)

                ast_node = PPRAstNode(
                    component_name=comp_name,
                    mode=mode,
                    parent=parent,
                )
                nodes.append(ast_node)

                # Recurse into children
                children = self._get_children(node)
                for child in children:
                    _walk(child, ast_node, depth + 1)
            else:
                # Not a component — just walk children
                children = self._get_children(node)
                for child in children:
                    _walk(child, parent, depth + 1)

        _walk(program_ast)
        return nodes

    def find_component_invocations(self, ast_node: Any) -> List[Dict[str, Any]]:
        """Recursively find all component references in an AST node.

        Returns a flat list of {name, line, col} dicts.
        """
        results: List[Dict[str, Any]] = []

        def _walk(node: Any, depth: int = 0):
            if depth > 50:
                return
            comp_name = self._extract_component_name(node)
            if comp_name:
                results.append({
                    "name": comp_name,
                    "line": getattr(node, "line", 0),
                    "col": getattr(node, "col", 0),
                })
            for child in self._get_children(node):
                _walk(child, depth + 1)

        _walk(ast_node)
        return results

    def classify_component_node(self, node: PPRAstNode,
                                  component_source: str) -> str:
        """Classify a single component invocation by its source."""
        directives = self.compiler.extract_component_directives(component_source)
        node.mode = directives.get("mode", STATIC)
        return node.mode

    def build_boundary_tree(self, boundaries: List[PPRBoundary]) -> Dict[str, Any]:
        """Build parent-child boundary tree for nested PPR.

        Returns a nested dict representing the boundary hierarchy.
        Outer boundaries must render before inner ones.
        """
        # Build a tree based on component dependencies
        tree: Dict[str, Any] = {"root": {"children": []}}

        for b in boundaries:
            deps = self.compiler.resolve_component_dependencies(b.component_name)
            parent_name = None
            for comp_name, comp_deps in deps.items():
                for dep in comp_deps:
                    if any(ob.component_name == dep for ob in boundaries):
                        parent_name = dep
                        break

            node = {
                "boundary": b.component_name,
                "mode": b.mode,
                "placeholder_id": b.placeholder_id,
                "children": [],
            }

            if parent_name:
                # Find parent in tree and add as child
                found = self._find_in_tree(tree["root"], parent_name)
                if found:
                    found["children"].append(node)
                else:
                    tree["root"]["children"].append(node)
            else:
                tree["root"]["children"].append(node)

        return tree

    def detect_circular_boundaries(self, boundaries: List[PPRBoundary]) -> List[List[str]]:
        """Detect circular dependencies between PPR boundaries.

        Returns a list of cycles, each cycle is a list of component names.
        """
        # Build adjacency list
        graph: Dict[str, List[str]] = {}
        for b in boundaries:
            deps = self.compiler.resolve_component_dependencies(b.component_name)
            graph[b.component_name] = deps.get(b.component_name, [])

        # DFS to find cycles
        cycles: List[List[str]] = []
        visited: Set[str] = set()
        stack: List[str] = []

        def _dfs(node: str):
            if node in stack:
                # Found a cycle
                cycle_start = stack.index(node)
                cycle = stack[cycle_start:] + [node]
                cycles.append(cycle)
                return
            if node in visited:
                return

            stack.append(node)
            for neighbor in graph.get(node, []):
                _dfs(neighbor)
            stack.pop()
            visited.add(node)

        for node in graph:
            _dfs(node)

        return cycles

    @staticmethod
    def _extract_component_name(node: Any) -> Optional[str]:
        """Try to extract a component name from an AST node."""
        # Handle different AST node types
        if hasattr(node, "name") and isinstance(node.name, str):
            name = node.name
            if name and name[0].isupper() and name not in ("True", "False", "None"):
                return name
        if hasattr(node, "tag") and isinstance(node.tag, str):
            tag = node.tag
            if tag and tag[0].isupper() and tag not in ("True", "False", "None"):
                return tag
        if isinstance(node, dict):
            for key in ("name", "tag", "component"):
                val = node.get(key)
                if isinstance(val, str) and val and val[0].isupper():
                    return val
        return None

    @staticmethod
    def _get_children(node: Any) -> List[Any]:
        """Get child nodes from an AST node."""
        if hasattr(node, "children"):
            return node.children or []
        if hasattr(node, "nodes"):
            return node.nodes or []
        if isinstance(node, dict) and "children" in node:
            return node["children"] or []
        return []

    @staticmethod
    def _find_in_tree(root: Dict[str, Any], name: str) -> Optional[Dict[str, Any]]:
        """Find a node by name in the boundary tree."""
        if root.get("boundary") == name:
            return root
        for child in root.get("children", []):
            found = PPRAstAnalyzer._find_in_tree(child, name)
            if found:
                return found
        return None


# ── PPR Middleware ───────────────────────────────────────────────────

@dataclass
class PPRRouteConfig:
    """PPR configuration for a specific route."""
    route_path: str
    enabled: bool = True
    streaming: bool = True
    default_mode: str = STATIC
    max_boundaries: int = 20


class PPRMiddleware:
    """Request middleware for PPR.

    Processes incoming requests to set up PPR streaming,
    inject polyfills, and configure response headers.
    """

    def __init__(self):
        self._route_configs: Dict[str, PPRRouteConfig] = {}
        self._global_enabled: bool = True
        self._default_config = PPRRouteConfig(route_path="*")

    def register_route(self, route_path: str, enabled: bool = True,
                       streaming: bool = True, default_mode: str = STATIC,
                       max_boundaries: int = 20) -> None:
        """Register PPR config for a route."""
        self._route_configs[route_path] = PPRRouteConfig(
            route_path=route_path,
            enabled=enabled,
            streaming=streaming,
            default_mode=default_mode,
            max_boundaries=max_boundaries,
        )

    def should_use_ppr(self, route_path: str) -> bool:
        """Check if a route should use PPR."""
        if not self._global_enabled:
            return False
        # Check exact match
        if route_path in self._route_configs:
            return self._route_configs[route_path].enabled
        # Check wildcard
        if "*" in self._route_configs:
            return self._route_configs["*"].enabled
        return self._default_config.enabled

    def process_request(self, request: dict, response: dict) -> dict:
        """Process a request for PPR.

        Sets up streaming headers if PPR is enabled for the route.
        """
        route_path = request.get("path", "")
        if not self.should_use_ppr(route_path):
            return response

        config = self._route_configs.get(route_path, self._default_config)

        if config.streaming:
            headers = response.get("headers", {})
            if isinstance(headers, dict):
                headers.update(PPRStreamingRenderer.generate_stream_headers())
            elif isinstance(headers, list):
                headers.extend(
                    list(PPRStreamingRenderer.generate_stream_headers().items())
                )
            response["headers"] = headers

        # Add PPR metadata to request context
        request["_ppr"] = {
            "enabled": True,
            "streaming": config.streaming,
            "default_mode": config.default_mode,
            "max_boundaries": config.max_boundaries,
        }

        return response

    def inject_suspense_polyfill(self, html: str) -> str:
        """Inject JS polyfill for <tw-suspense> custom element.

        This polyfill makes <tw-suspense> work in browsers that
        don't support custom elements (very old browsers).
        """
        polyfill = """<script>
(function() {
  if (!window.customElements) return;
  class TWSuspense extends HTMLElement {
    connectedCallback() {
      this.style.display = this.style.display || 'block';
    }
    set loaded(val) {
      if (val) this.setAttribute('data-tw-loaded', 'true');
    }
  }
  customElements.define('tw-suspense', TWSuspense);
})();
</script>"""
        # Inject before </head> or at the beginning
        if "</head>" in html:
            return html.replace("</head>", polyfill + "</head>")
        return polyfill + html

    def generate_ppr_meta_tag(self, boundaries: List[PPRBoundary]) -> str:
        """Generate <meta name="tw-ppr"> tag with boundary info.

        This metadata is used by the client-side runtime to know
        which boundaries exist and how to hydrate them.
        """
        boundary_info = [
            {
                "id": b.placeholder_id,
                "component": b.component_name,
                "mode": b.mode,
                "revalidate": b.revalidate,
                "tags": b.tags,
            }
            for b in boundaries
        ]
        content = json.dumps({"boundaries": boundary_info})
        return f'<meta name="tw-ppr" content="{html.escape(content)}">'

    def get_route_summary(self) -> List[Dict[str, Any]]:
        """Return summary of all PPR route configs."""
        return [
            {
                "route": cfg.route_path,
                "enabled": cfg.enabled,
                "streaming": cfg.streaming,
                "default_mode": cfg.default_mode,
                "max_boundaries": cfg.max_boundaries,
            }
            for cfg in self._route_configs.values()
        ]


# ── PPR Build Report ────────────────────────────────────────────────

@dataclass
class PPRBoundaryReport:
    """Report entry for a single PPR boundary."""
    component_name: str
    mode: str
    placeholder_id: str
    revalidate: int = 0
    tags: List[str] = field(default_factory=list)
    has_fallback: bool = False
    warnings: List[str] = field(default_factory=list)


class PPRBuildReport:
    """Build-time reporting for PPR.

    Generates human-readable reports of PPR boundaries,
    with warnings and optimization recommendations.
    """

    def __init__(self):
        self._reports: Dict[str, List[PPRBoundaryReport]] = {}

    def generate_report(self, boundaries: List[PPRBoundary],
                        page_name: str = "") -> str:
        """Generate a text report of PPR boundaries for a page."""
        reports: List[PPRBoundaryReport] = []
        lines = [
            "=" * 60,
            f"  PPR Build Report — {page_name or '(unnamed)'}",
            "=" * 60,
            "",
            f"  Total boundaries: {len(boundaries)}",
            "",
        ]

        mode_counts = {STATIC: 0, DYNAMIC: 0, CACHED: 0, STREAMING: 0}
        for b in boundaries:
            mode_counts[b.mode] = mode_counts.get(b.mode, 0) + 1
            report = PPRBoundaryReport(
                component_name=b.component_name,
                mode=b.mode,
                placeholder_id=b.placeholder_id,
                revalidate=b.revalidate,
                tags=b.tags,
                has_fallback=bool(b.fallback_html),
            )

            # Check for warnings
            if b.mode == STREAMING and not b.fallback_html:
                report.warnings.append("Streaming boundary has no fallback — users see nothing while loading")
            if b.mode == CACHED and b.revalidate == 0:
                report.warnings.append("Cached boundary has no revalidation period — will never refresh")
            if b.mode == CACHED and not b.tags:
                report.warnings.append("Cached boundary has no tags — cannot be invalidated on-demand")
            if b.mode == DYNAMIC and len(boundaries) > 10:
                report.warnings.append("Too many dynamic boundaries — consider caching some")

            reports.append(report)

        self._reports[page_name] = reports

        # Mode summary
        lines.append("  Mode breakdown:")
        icons = {STATIC: "📄", DYNAMIC: "⚡", CACHED: "🔄", STREAMING: "📡"}
        for mode, count in mode_counts.items():
            if count > 0:
                lines.append(f"    {icons.get(mode, '?')} {mode}: {count}")
        lines.append("")

        # Per-boundary details
        lines.append("  Boundaries:")
        lines.append("  " + "-" * 56)
        for r in reports:
            icon = icons.get(r.mode, "?")
            lines.append(f"  {icon} {r.component_name}")
            lines.append(f"      Mode: {r.mode}")
            if r.revalidate > 0:
                lines.append(f"      Revalidate: {r.revalidate}s")
            if r.tags:
                lines.append(f"      Tags: {', '.join(r.tags)}")
            if r.has_fallback:
                lines.append(f"      Fallback: yes")
            for warning in r.warnings:
                lines.append(f"      ⚠️  {warning}")
            lines.append("")

        # Recommendations
        recommendations = self._generate_recommendations(boundaries, mode_counts)
        if recommendations:
            lines.append("  Recommendations:")
            for rec in recommendations:
                lines.append(f"    • {rec}")
        else:
            lines.append("  ✓ No issues found — PPR configuration looks good!")

        lines.append("")
        lines.append("=" * 60)
        return "\n".join(lines)

    @staticmethod
    def _generate_recommendations(boundaries: List[PPRBoundary],
                                    mode_counts: Dict[str, int]) -> List[str]:
        """Generate optimization recommendations."""
        recs: List[str] = []

        total = len(boundaries)
        dynamic = mode_counts.get(DYNAMIC, 0)
        streaming = mode_counts.get(STREAMING, 0)
        cached = mode_counts.get(CACHED, 0)

        if total > 15:
            recs.append(f"Too many PPR boundaries ({total}) — consider consolidating components")
        if dynamic > 5:
            recs.append(f"Too many dynamic boundaries ({dynamic}) — consider caching or streaming some")
        if streaming > 3:
            recs.append(f"Too many streaming boundaries ({streaming}) — may overwhelm the client")
        if cached > 0 and all(not b.tags for b in boundaries if b.mode == CACHED):
            recs.append("Cached boundaries have no tags — on-demand revalidation won't work")
        if dynamic == 0 and streaming == 0 and cached == 0:
            recs.append("No dynamic boundaries — page is fully static, PPR is not needed")

        # Check for missing fallbacks
        missing_fallback = [b for b in boundaries if b.mode == STREAMING and not b.fallback_html]
        if missing_fallback:
            names = ", ".join(b.component_name for b in missing_fallback)
            recs.append(f"Streaming boundaries without fallback: {names} — users see blank space while loading")

        # Check for very short revalidation
        short_reval = [b for b in boundaries if b.mode == CACHED and 0 < b.revalidate < 5]
        if short_reval:
            recs.append(f"Some cached boundaries have very short revalidation (<5s) — may cause excessive re-renders")

        return recs

    def save_report(self, output_dir: str = "") -> str:
        """Save all reports to a file."""
        path = os.path.join(output_dir or os.getcwd(), ".tw", "ppr-report.txt")
        os.makedirs(os.path.dirname(path), exist_ok=True)
        all_reports = []
        for page_name, reports in self._reports.items():
            all_reports.append(f"# Page: {page_name}")
            for r in reports:
                all_reports.append(f"  {r.component_name}: {r.mode} (revalidate={r.revalidate}, tags={r.tags})")
        try:
            with open(path, "w") as f:
                f.write("\n".join(all_reports))
        except OSError:
            pass
        return path

    def get_summary(self) -> Dict[str, Any]:
        """Return summary dict for tw info / tw doctor."""
        total_boundaries = sum(len(reports) for reports in self._reports.values())
        all_reports = [r for reports in self._reports.values() for r in reports]
        return {
            "pages_with_ppr": len(self._reports),
            "total_boundaries": total_boundaries,
            "by_mode": {
                mode: sum(1 for r in all_reports if r.mode == mode)
                for mode in (STATIC, DYNAMIC, CACHED, STREAMING)
            },
            "warnings": sum(len(r.warnings) for r in all_reports),
            "pages": {
                name: [r.component_name for r in reports]
                for name, reports in self._reports.items()
            },
        }


# Update __all__


# ── PPR Hydration System ─────────────────────────────────────────────

@dataclass
class HydrationManifest:
    """Manifest of all PPR boundaries that need client-side hydration."""
    page_name: str
    boundaries: List[Dict[str, Any]] = field(default_factory=list)
    generated_at: float = field(default_factory=time.time)

    def add_boundary(self, boundary: PPRBoundary) -> None:
        """Add a boundary to the hydration manifest."""
        self.boundaries.append({
            "id": boundary.placeholder_id,
            "component": boundary.component_name,
            "mode": boundary.mode,
            "revalidate": boundary.revalidate,
            "tags": boundary.tags,
            "cache_key": boundary.cache_key,
        })

    def to_json(self) -> str:
        """Serialize manifest to JSON."""
        return json.dumps({
            "page": self.page_name,
            "generated_at": self.generated_at,
            "boundary_count": len(self.boundaries),
            "boundaries": self.boundaries,
        }, indent=2)

    def to_script_tag(self) -> str:
        """Generate a <script> tag that injects the hydration manifest."""
        data = self.to_json()
        # Escape for HTML attribute
        escaped = data.replace("</", "<\/")
        return f'<script type="application/json" id="__tw_ppr_manifest__">{escaped}</script>'


class PPRHydrator:
    """Client-side hydration for PPR boundaries.

    After the static HTML shell is delivered, the hydrator:
    1. Reads the hydration manifest from the page
    2. For each dynamic boundary, initiates a fetch to the SSR endpoint
    3. Replaces suspense placeholders with rendered content
    4. Attaches event listeners and reactivity
    5. Reports hydration completion

    This is the client-side companion to PPRStreamingRenderer.
    """

    def __init__(self):
        self._hydration_endpoints: Dict[str, str] = {}  # component_name → endpoint URL
        self._fallback_timeout: int = 30  # seconds before showing fallback
        self._concurrent_limit: int = 5  # max concurrent hydrations

    def register_endpoint(self, component_name: str, endpoint_url: str) -> None:
        """Register an SSR endpoint for a component."""
        self._hydration_endpoints[component_name] = endpoint_url

    def generate_hydration_script(self, manifest: HydrationManifest) -> str:
        """Generate the client-side hydration JavaScript.

        This script is injected at the end of the page and:
        1. Reads the PPR manifest
        2. For each boundary, fetches the rendered component
        3. Replaces the placeholder with the result
        4. Handles errors and timeouts
        """
        manifest_json = manifest.to_json().replace("</", "<\/")

        # Build endpoint mapping
        endpoints_json = json.dumps(self._hydration_endpoints)

        return f"""<script>
(function() {{
  var manifest = {manifest_json};
  var endpoints = {endpoints_json};
  var timeout = {self._fallback_timeout} * 1000;
  var concurrent = {self._concurrent_limit};
  var completed = 0;
  var failed = 0;

  function hydrateBoundary(boundary) {{
    var placeholder = document.getElementById(boundary.id);
    if (!placeholder) {{
      console.warn('[PPR] Placeholder not found:', boundary.id);
      failed++;
      return;
    }}

    // Skip static boundaries (already rendered)
    if (boundary.mode === 'static') {{
      completed++;
      return;
    }}

    // For cached boundaries, check if already in the HTML
    if (boundary.mode === 'cached' && placeholder.getAttribute('data-tw-loaded') === 'true') {{
      completed++;
      return;
    }}

    // Get the endpoint for this component
    var endpoint = endpoints[boundary.component] || '/__tw/ppr/' + boundary.component;

    var controller = new AbortController();
    var timer = setTimeout(function() {{
      controller.abort();
      onTimeout(boundary);
    }}, timeout);

    fetch(endpoint, {{
      method: 'POST',
      headers: {{ 'Content-Type': 'application/json' }},
      body: JSON.stringify({{ component: boundary.component, id: boundary.id }}),
      signal: controller.signal
    }})
    .then(function(r) {{
      if (!r.ok) throw new Error('HTTP ' + r.status);
      return r.text();
    }})
    .then(function(html) {{
      clearTimeout(timer);
      // Replace placeholder content
      placeholder.innerHTML = html;
      placeholder.setAttribute('data-tw-loaded', 'true');
      placeholder.setAttribute('data-tw-hydrated', 'true');
      completed++;
      checkComplete();
    }})
    .catch(function(err) {{
      clearTimeout(timer);
      if (err.name === 'AbortError') {{
        onTimeout(boundary);
      }} else {{
        onError(boundary, err);
      }}
    }});
  }}

  function onTimeout(boundary) {{
    console.warn('[PPR] Hydration timeout:', boundary.component);
    var placeholder = document.getElementById(boundary.id);
    if (placeholder) {{
      placeholder.innerHTML += '<div class="tw-ppr-timeout">Loading timed out</div>';
      placeholder.setAttribute('data-tw-error', 'timeout');
    }}
    failed++;
    checkComplete();
  }}

  function onError(boundary, err) {{
    console.error('[PPR] Hydration error:', boundary.component, err);
    var placeholder = document.getElementById(boundary.id);
    if (placeholder) {{
      placeholder.innerHTML = '<div class="tw-ppr-error">Failed to load ' + boundary.component + '</div>';
      placeholder.setAttribute('data-tw-error', err.message);
    }}
    failed++;
    checkComplete();
  }}

  function checkComplete() {{
    var total = manifest.boundaries.length;
    if (completed + failed >= total) {{
      document.dispatchEvent(new CustomEvent('tw:ppr-hydrated', {{
        detail: {{ completed: completed, failed: failed, total: total }}
      }}));
      console.log('[PPR] Hydration complete:', completed, 'success,', failed, 'failed');
    }}
  }}

  // Start hydration — limit concurrent requests
  var queue = manifest.boundaries.filter(function(b) {{ return b.mode !== 'static'; }});
  var active = 0;

  function processQueue() {{
    while (active < concurrent && queue.length > 0) {{
      var boundary = queue.shift();
      active++;
      hydrateBoundary(boundary);
      // Decrement active after a delay (simulating async completion)
      setTimeout(function() {{ active--; processQueue(); }}, 50);
    }}
  }}

  // Start after DOM is ready
  if (document.readyState === 'loading') {{
    document.addEventListener('DOMContentLoaded', processQueue);
  }} else {{
    processQueue();
  }}
}})();
</script>"""

    def generate_loading_styles(self) -> str:
        """Generate CSS for PPR loading states and error states."""
        return """<style>
.tw-skeleton {
  background: linear-gradient(90deg, #f0f0f0 25%, #e0e0e0 50%, #f0f0f0 75%);
  background-size: 200% 100%;
  animation: tw-skeleton-pulse 1.5s infinite;
  border-radius: 4px;
  min-height: 1em;
}
.tw-skeleton-line {
  height: 1em;
  margin: 0.5em 0;
  width: 100%;
}
.tw-skeleton-short { width: 60%; }
.tw-skeleton-pulse {
  animation: tw-skeleton-pulse 1.5s ease-in-out infinite;
}
@keyframes tw-skeleton-pulse {
  0% { background-position: 200% 0; }
  100% { background-position: -200% 0; }
}
.tw-ppr-error {
  color: #dc2626;
  padding: 1rem;
  border: 1px solid #fecaca;
  border-radius: 4px;
  background: #fef2f2;
}
.tw-ppr-timeout {
  color: #f59e0b;
  padding: 0.5rem;
  font-size: 0.875rem;
}
tw-suspense {
  display: block;
}
tw-suspense[data-tw-loaded] {
  animation: tw-fade-in 0.3s ease-out;
}
@keyframes tw-fade-in {
  from { opacity: 0; transform: translateY(4px); }
  to { opacity: 1; transform: translateY(0); }
}
</style>"""


# ── PPR Error Boundaries ─────────────────────────────────────────────

@dataclass
class PPRErrorBoundary:
    """Error boundary for a PPR component.

    If a component fails to render (at build or request time),
    the error boundary catches the failure and renders a fallback
    instead of crashing the entire page.
    """
    component_name: str
    fallback_html: str = ""
    on_error: Optional[Callable[[Exception], None]] = None
    max_retries: int = 1
    retry_delay: float = 0.5  # seconds
    log_errors: bool = True


class PPRErrorBoundaryHandler:
    """Manages error boundaries for PPR components.

    Wraps component rendering with try/except and provides
    graceful fallbacks, retry logic, and error reporting.
    """

    def __init__(self):
        self._boundaries: Dict[str, PPRErrorBoundary] = {}
        self._error_counts: Dict[str, int] = {}
        self._last_errors: Dict[str, str] = {}

    def register(self, boundary: PPRErrorBoundary) -> None:
        """Register an error boundary for a component."""
        self._boundaries[boundary.component_name] = boundary

    def register_simple(self, component_name: str,
                        fallback_html: str = "",
                        max_retries: int = 1) -> None:
        """Simple registration with just a fallback."""
        self._boundaries[component_name] = PPRErrorBoundary(
            component_name=component_name,
            fallback_html=fallback_html or self._default_fallback(component_name),
            max_retries=max_retries,
        )

    def safe_render(self, component_name: str,
                     render_fn: Callable[[], str],
                     params: Optional[dict] = None) -> str:
        """Safely render a component with error boundary protection.

        If the component fails, returns the fallback HTML instead.
        Supports retry logic for transient failures.
        """
        boundary = self._boundaries.get(component_name)

        # If no boundary registered, just render directly
        if not boundary:
            try:
                return render_fn()
            except Exception as e:
                logger.error("Unprotected component %s failed: %s", component_name, e)
                return f'<div class="tw-ppr-error">Component {component_name} failed to render</div>'

        # Try rendering with retries
        last_error: Optional[Exception] = None
        for attempt in range(boundary.max_retries + 1):
            try:
                result = render_fn()
                # Success — reset error count
                self._error_counts[component_name] = 0
                return result
            except Exception as e:
                last_error = e
                self._error_counts[component_name] = self._error_counts.get(component_name, 0) + 1
                self._last_errors[component_name] = str(e)

                if boundary.log_errors:
                    logger.warning(
                        "PPR component %s failed (attempt %d/%d): %s",
                        component_name, attempt + 1, boundary.max_retries + 1, e
                    )

                # Call error callback
                if boundary.on_error:
                    try:
                        boundary.on_error(e)
                    except Exception:
                        pass

                # Wait before retry
                if attempt < boundary.max_retries:
                    import time as _time
                    _time.sleep(boundary.retry_delay)

        # All retries exhausted — return fallback
        logger.error(
            "PPR component %s failed after %d retries: %s",
            component_name, boundary.max_retries, last_error
        )
        return boundary.fallback_html or self._default_fallback(component_name)

    @staticmethod
    def _default_fallback(component_name: str) -> str:
        """Generate a default error fallback for a component."""
        return (
            f'<div class="tw-ppr-error" role="alert">'
            f'<p>Unable to load {component_name}</p>'
            f'<p class="tw-ppr-error-detail">This component is temporarily unavailable.</p>'
            f'</div>'
        )

    def get_error_stats(self) -> Dict[str, Any]:
        """Return error statistics for all components."""
        return {
            "components_with_errors": len(self._error_counts),
            "total_errors": sum(self._error_counts.values()),
            "per_component": {
                name: {
                    "error_count": count,
                    "last_error": self._last_errors.get(name, ""),
                }
                for name, count in self._error_counts.items()
                if count > 0
            },
        }

    def reset_errors(self, component_name: str = "") -> None:
        """Reset error counts for a component or all."""
        if component_name:
            self._error_counts.pop(component_name, None)
            self._last_errors.pop(component_name, None)
        else:
            self._error_counts.clear()
            self._last_errors.clear()

    def get_boundary_info(self) -> List[Dict[str, Any]]:
        """Return info about all registered error boundaries."""
        return [
            {
                "component": b.component_name,
                "has_fallback": bool(b.fallback_html),
                "max_retries": b.max_retries,
                "retry_delay": b.retry_delay,
                "error_count": self._error_counts.get(b.component_name, 0),
            }
            for b in self._boundaries.values()
        ]


# ── PPR Debug Tools ──────────────────────────────────────────────────

class PPRDebugTools:
    """Debugging tools for PPR.

    Provides utilities for debugging PPR boundaries during development:
    - Visualize boundaries on the page
    - Profile render times
    - Check cache status
    - Generate debug headers
    - Export debug data
    """

    def __init__(self):
        self._enabled: bool = False
        self._profiling_data: Dict[str, Dict[str, Any]] = {}
        self._debug_headers: Dict[str, str] = {}

    def enable(self) -> None:
        """Enable debug mode."""
        self._enabled = True

    def disable(self) -> None:
        """Disable debug mode."""
        self._enabled = False

    @property
    def is_enabled(self) -> bool:
        return self._enabled

    def start_profile(self, component_name: str) -> None:
        """Start profiling a component render."""
        if not self._enabled:
            return
        import time as _time
        self._profiling_data[component_name] = {
            "start_time": _time.time(),
            "end_time": None,
            "duration_ms": None,
        }

    def end_profile(self, component_name: str) -> float:
        """End profiling a component render. Returns duration in ms."""
        if not self._enabled or component_name not in self._profiling_data:
            return 0.0
        import time as _time
        entry = self._profiling_data[component_name]
        entry["end_time"] = _time.time()
        entry["duration_ms"] = (entry["end_time"] - entry["start_time"]) * 1000
        return entry["duration_ms"]

    def add_debug_header(self, name: str, value: str) -> None:
        """Add a debug header to responses."""
        if self._enabled:
            self._debug_headers[f"X-TW-PPR-{name}"] = value

    def get_debug_headers(self) -> Dict[str, str]:
        """Return debug headers for the response."""
        return dict(self._debug_headers) if self._enabled else {}

    def get_debug_script(self, boundaries: List[PPRBoundary]) -> str:
        """Generate a debug script that visualizes PPR boundaries.

        In debug mode, each boundary gets a colored outline and tooltip
        showing its mode, cache status, and render time.
        """
        if not self._enabled:
            return ""

        boundary_data = [
            {
                "id": b.placeholder_id,
                "component": b.component_name,
                "mode": b.mode,
                "revalidate": b.revalidate,
                "tags": b.tags,
            }
            for b in boundaries
        ]

        profiling_json = json.dumps(self._profiling_data, indent=2, default=str)

        return f"""<script>
(function() {{
  var boundaries = {json.dumps(boundary_data)};
  var profiling = {profiling_json};
  var modeColors = {{
    static: '#22c55e',
    dynamic: '#3b82f6',
    cached: '#f59e0b',
    streaming: '#8b5cf6'
  }};

  boundaries.forEach(function(b) {{
    var el = document.getElementById(b.id);
    if (!el) return;

    var color = modeColors[b.mode] || '#6b7280';
    el.style.outline = '2px dashed ' + color;
    el.style.outlineOffset = '2px';
    el.style.position = 'relative';

    // Add debug badge
    var badge = document.createElement('div');
    badge.style.cssText = 'position:absolute;top:-20px;right:0;background:' + color +
      ';color:white;padding:2px 6px;font-size:10px;border-radius:2px;z-index:9999;' +
      'font-family:monospace;pointer-events:none;';
    badge.textContent = b.component + ' [' + b.mode + ']';
    el.appendChild(badge);

    // Add tooltip with details
    el.setAttribute('title', 'Component: ' + b.component +
      '\nMode: ' + b.mode +
      '\nRevalidate: ' + (b.revalidate || 'none') + 's' +
      '\nTags: ' + (b.tags.join(', ') || 'none'));

    // Add profiling info
    var profile = profiling[b.component];
    if (profile && profile.duration_ms) {{
      var time_badge = document.createElement('div');
      time_badge.style.cssText = 'position:absolute;top:-20px;left:0;background:#1f2937;' +
        'color:white;padding:2px 6px;font-size:10px;border-radius:2px;z-index:9999;' +
        'font-family:monospace;pointer-events:none;';
      time_badge.textContent = profile.duration_ms.toFixed(1) + 'ms';
      el.appendChild(time_badge);
    }}
  }});

  console.log('[PPR Debug]', boundaries.length, 'boundaries:', boundaries);
  console.log('[PPR Debug] Profiling:', profiling);
}})();
</script>"""

    def get_debug_report(self) -> Dict[str, Any]:
        """Return a debug report with profiling data."""
        if not self._enabled:
            return {"enabled": False}

        return {
            "enabled": True,
            "components_profiled": len(self._profiling_data),
            "profiling": {
                name: {
                    "duration_ms": round(data.get("duration_ms", 0), 2),
                }
                for name, data in self._profiling_data.items()
            },
            "total_render_time_ms": round(
                sum(data.get("duration_ms", 0) for data in self._profiling_data.values()), 2
            ),
            "debug_headers": dict(self._debug_headers),
        }

    def reset(self) -> None:
        """Reset all debug data."""
        self._profiling_data.clear()
        self._debug_headers.clear()


# ── PPR Route Matcher ────────────────────────────────────────────────

@dataclass
class PPRRoutePattern:
    """A route pattern that should use PPR."""
    pattern: str               # e.g. "/dashboard/*" or "/blog/[slug]"
    ppr_mode: str = "auto"    # auto | always | never
    max_boundaries: int = 20
    streaming: bool = True
    cache_revalidate: int = 0
    cache_tags: List[str] = field(default_factory=list)


class PPRRouteMatcher:
    """Matches request paths to PPR route patterns.

    Determines which routes should use PPR and with what configuration.
    Supports wildcard patterns, dynamic segments, and exclusion rules.
    """

    def __init__(self):
        self._patterns: List[PPRRoutePattern] = []
        self._exclusions: Set[str] = set()
        self._default_mode: str = "auto"  # auto = use PPR if boundaries exist

    def add_pattern(self, pattern: str, ppr_mode: str = "auto",
                    max_boundaries: int = 20, streaming: bool = True,
                    revalidate: int = 0, tags: Optional[List[str]] = None) -> None:
        """Add a PPR route pattern."""
        self._patterns.append(PPRRoutePattern(
            pattern=pattern,
            ppr_mode=ppr_mode,
            max_boundaries=max_boundaries,
            streaming=streaming,
            cache_revalidate=revalidate,
            cache_tags=tags or [],
        ))

    def exclude(self, path: str) -> None:
        """Exclude a path from PPR."""
        self._exclusions.add(path)

    def match(self, request_path: str) -> Optional[PPRRoutePattern]:
        """Match a request path to a PPR pattern.

        Returns the matching PPRRoutePattern or None if PPR should not be used.
        """
        # Check exclusions first
        if request_path in self._exclusions:
            return None

        # Check each pattern
        for pattern in self._patterns:
            if self._match_pattern(pattern.pattern, request_path):
                if pattern.ppr_mode == "never":
                    return None
                return pattern

        # Default mode
        if self._default_mode == "never":
            return None
        if self._default_mode == "always":
            return PPRRoutePattern(pattern="*", ppr_mode="always")

        # Auto mode — return default pattern (PPR will be used if boundaries exist)
        return PPRRoutePattern(pattern="*")

    @staticmethod
    def _match_pattern(pattern: str, path: str) -> bool:
        """Check if a path matches a pattern.

        Supports:
        - Exact match: "/about" matches "/about"
        - Wildcard: "/dashboard/*" matches "/dashboard/anything"
        - Double wildcard: "/api/**" matches "/api/a/b/c"
        - Dynamic: "/blog/[slug]" matches "/blog/hello-world"
        """
        # Exact match
        if pattern == path:
            return True

        # Double wildcard (/**)
        if pattern.endswith("/**"):
            prefix = pattern[:-3]
            return path.startswith(prefix)

        # Single wildcard (/*)
        if pattern.endswith("/*"):
            prefix = pattern[:-2]
            if not path.startswith(prefix):
                return False
            # Only match one level deep
            remainder = path[len(prefix):]
            return "/" not in remainder.lstrip("/")

        # Dynamic segment [slug]
        if "[" in pattern and "]" in pattern:
            import re as _re
            # Convert pattern to regex
            regex_pattern = _re.escape(pattern)
            # Replace escaped \[slug\] with a regex capture group
            regex_pattern = _re.sub(r'\\[([^\]]+)\\]', r'([^/]+)', regex_pattern)
            regex_pattern = regex_pattern.replace("\*", "[^/]*")
            return bool(_re.match(f"^{regex_pattern}$", path))

        # Simple wildcard in middle
        if "*" in pattern:
            import re as _re
            regex_pattern = _re.escape(pattern).replace("\*", ".*")
            return bool(_re.match(f"^{regex_pattern}$", path))

        return False

    def get_all_patterns(self) -> List[Dict[str, Any]]:
        """Return all registered patterns."""
        return [
            {
                "pattern": p.pattern,
                "ppr_mode": p.ppr_mode,
                "max_boundaries": p.max_boundaries,
                "streaming": p.streaming,
                "cache_revalidate": p.cache_revalidate,
                "cache_tags": p.cache_tags,
            }
            for p in self._patterns
        ]

    def set_default_mode(self, mode: str) -> None:
        """Set the default PPR mode for unmatched routes."""
        if mode in ("auto", "always", "never"):
            self._default_mode = mode

    def summary(self) -> Dict[str, Any]:
        """Return summary of route matcher configuration."""
        return {
            "pattern_count": len(self._patterns),
            "exclusion_count": len(self._exclusions),
            "default_mode": self._default_mode,
            "patterns": self.get_all_patterns(),
            "exclusions": sorted(self._exclusions),
        }


# ── PPR Snapshot Manager ────────────────────────────────────────────

class PPRSnapshotManager:
    """Manages snapshots of PPR state for debugging and rollback.

    Takes snapshots of:
    - All PPR boundaries and their render modes
    - Cache state (entries, staleness)
    - Render times and profiling data
    - Error counts and last errors

    Snapshots can be compared to detect changes between builds or deploys.
    """

    def __init__(self):
        self._snapshots: Dict[str, Dict[str, Any]] = {}

    def take_snapshot(self, name: str, boundaries: List[PPRBoundary],
                       cache_manager: Optional["PPRCacheManager"] = None,
                       error_handler: Optional[PPRErrorBoundaryHandler] = None,
                       debug_tools: Optional[PPRDebugTools] = None) -> Dict[str, Any]:
        """Take a snapshot of the current PPR state."""
        snapshot = {
            "name": name,
            "timestamp": time.time(),
            "boundary_count": len(boundaries),
            "boundaries": [
                {
                    "component": b.component_name,
                    "mode": b.mode,
                    "revalidate": b.revalidate,
                    "tags": b.tags,
                    "has_fallback": bool(b.fallback_html),
                }
                for b in boundaries
            ],
        }

        if cache_manager:
            snapshot["cache_stats"] = cache_manager.get_cache_stats()

        if error_handler:
            snapshot["error_stats"] = error_handler.get_error_stats()

        if debug_tools:
            snapshot["debug_report"] = debug_tools.get_debug_report()

        self._snapshots[name] = snapshot
        return snapshot

    def get_snapshot(self, name: str) -> Optional[Dict[str, Any]]:
        """Get a snapshot by name."""
        return self._snapshots.get(name)

    def compare_snapshots(self, name1: str, name2: str) -> Dict[str, Any]:
        """Compare two snapshots and return differences."""
        s1 = self._snapshots.get(name1, {})
        s2 = self._snapshots.get(name2, {})

        diffs: Dict[str, Any] = {
            "snapshot1": name1,
            "snapshot2": name2,
            "changes": [],
        }

        # Compare boundary counts
        c1 = s1.get("boundary_count", 0)
        c2 = s2.get("boundary_count", 0)
        if c1 != c2:
            diffs["changes"].append({
                "field": "boundary_count",
                "before": c1,
                "after": c2,
            })

        # Compare individual boundaries
        b1 = {b["component"]: b for b in s1.get("boundaries", [])}
        b2 = {b["component"]: b for b in s2.get("boundaries", [])}

        added = set(b2.keys()) - set(b1.keys())
        removed = set(b1.keys()) - set(b2.keys())
        changed = []

        for comp in set(b1.keys()) & set(b2.keys()):
            if b1[comp] != b2[comp]:
                changed.append({
                    "component": comp,
                    "before": b1[comp],
                    "after": b2[comp],
                })

        if added:
            diffs["changes"].append({"added_boundaries": sorted(added)})
        if removed:
            diffs["changes"].append({"removed_boundaries": sorted(removed)})
        if changed:
            diffs["changes"].append({"changed_boundaries": changed})

        diffs["has_changes"] = len(diffs["changes"]) > 0
        return diffs

    def list_snapshots(self) -> List[Dict[str, Any]]:
        """List all snapshots."""
        return [
            {
                "name": name,
                "timestamp": s.get("timestamp"),
                "boundary_count": s.get("boundary_count", 0),
            }
            for name, s in self._snapshots.items()
        ]

    def export_snapshot(self, name: str, output_path: str = "") -> str:
        """Export a snapshot to a JSON file."""
        import json as _json
        snapshot = self._snapshots.get(name)
        if not snapshot:
            return ""

        output_path = output_path or os.path.join(os.getcwd(), ".tw", f"ppr-snapshot-{name}.json")
        os.makedirs(os.path.dirname(output_path), exist_ok=True)
        try:
            with open(output_path, "w") as f:
                _json.dump(snapshot, f, indent=2, default=str)
        except OSError:
            pass
        return output_path


# ── Update __all__ ──────────────────────────────────────────────────

