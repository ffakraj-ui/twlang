"""
TW App Router — Next.js-style routing and layout system for TW Framework.

This module replaces the flat [home]/pages/ + [home]/layouts/ structure with
a nested, file-system-based App Router:

    [home]/
    ├── layout.tw          ← Root layout (wraps everything)
    ├── page.tw            ← Home page (/)
    ├── loading.tw         ← Route-level loading state
    ├── not-found.tw       ← Route-level 404
    ├── (main)/            ← Route group (excluded from URL)
    │   ├── layout.tw      ← Layout for all pages inside (main)
    │   ├── page.tw        ← Still / (route group doesn't add to URL)
    │   ├── app/
    │   │   └── [slug]/    ← Dynamic route /app/:slug
    │   │       └── page.tw
    │   ├── blog/
    │   │   ├── page.tw    ← /blog
    │   │   └── [slug]/
    │   │       ├── layout.tw  ← Nested layout (wraps blog posts)
    │   │       └── page.tw    ← /blog/:slug
    │   └── category/
    │       └── [slug]/
    │           └── page.tw    ← /category/:slug
    ├── admin/             ← Separate layout tree
    │   ├── layout.tw      ← Admin layout (no (main) wrapper)
    │   ├── page.tw        ← /admin
    │   └── login/
    │       └── page.tw    ← /admin/login
    └── api/               ← API routes (route.tw files)
        └── apps/
            └── route.tw   ← /api/apps

Key concepts:
- layout.tw files are TW components, NOT HTML templates
- They receive {children} (page content) and wrap it
- Nested layouts compose: root → (main) → blog → page
- Route groups (folder) don't affect URL, only layout grouping
- Dynamic routes [slug] become URL params accessible in page context
"""

import os
import re
import logging
from dataclasses import dataclass, field
from typing import Any

logger = logging.getLogger(__name__)

# ─── Route Types ──────────────────────────────────────────────────────────

ROUTE_TYPE_STATIC = "static"
ROUTE_TYPE_DYNAMIC = "dynamic"
ROUTE_TYPE_CATCH_ALL = "catch_all"

# ─── Special Filenames ────────────────────────────────────────────────────

PAGE_FILE = "page.tw"
LAYOUT_FILE = "layout.tw"
LOADING_FILE = "loading.tw"
NOT_FOUND_FILE = "not-found.tw"
ERROR_FILE = "error.tw"
ROUTE_FILE = "route.tw"  # API route

# ─── Route Group / Dynamic Segment Regexes ───────────────────────────────

# (main), (auth), (marketing) → route group, excluded from URL
ROUTE_GROUP_RE = re.compile(r"^\(([^)]+)\)$")

# [slug], [id], [lang] → dynamic segment
DYNAMIC_SEGMENT_RE = re.compile(r"^\[([^\]]+)\]$")

# [...slug] → catch-all segment
CATCH_ALL_RE = re.compile(r"^\[\.\.\.([^\]]+)\]$")


@dataclass
class RouteSegment:
    """A single segment of a route path."""
    raw: str          # Raw folder name (e.g. "[slug]", "(main)", "blog")
    type: str         # "static", "dynamic", "catch_all", "route_group"
    param_name: str = ""  # For dynamic: "slug"; for route_group: "main"

    @property
    def is_url_segment(self) -> bool:
        """Whether this segment appears in the URL."""
        return self.type != "route_group"


@dataclass
class RouteInfo:
    """Discovered route information for a single page."""
    file_path: str           # Absolute path to page.tw
    url_path: str            # URL path (e.g. "/blog/my-post")
    segments: list = field(default_factory=list)  # List[RouteSegment]
    layout_files: list = field(default_factory=list)  # List of layout.tw paths (root → inner)
    loading_file: str = ""   # loading.tw path if exists
    not_found_file: str = "" # not-found.tw path if exists
    error_file: str = ""     # error.tw path if exists
    params: dict = field(default_factory=dict)  # Dynamic params (for dynamic routes)
    is_api: bool = False      # True if this is an API route
    api_file: str = ""        # route.tw path for API routes


@dataclass
class LayoutInfo:
    """Information about a discovered layout.tw file."""
    file_path: str       # Absolute path to layout.tw
    dir_path: str        # Directory containing the layout
    depth: int           # 0 = root, 1 = first nested, etc.
    is_root: bool        # True if this is the root layout ([home]/layout.tw)


def classify_segment(folder_name: str) -> RouteSegment:
    """Classify a folder name as a route segment."""
    # FIX #376: Validate empty param names — reject [] and [...]
    # Route group: (main), (auth), etc.
    m = ROUTE_GROUP_RE.match(folder_name)
    if m:
        param = m.group(1)
        if not param.strip():
            raise ValueError(f"Route group has empty name: {folder_name!r}")
        return RouteSegment(
            raw=folder_name,
            type="route_group",
            param_name=param,
        )

    # Catch-all: [...slug]
    m = CATCH_ALL_RE.match(folder_name)
    if m:
        param = m.group(1)
        if not param.strip():
            raise ValueError(f"Catch-all segment has empty param name: {folder_name!r}")
        return RouteSegment(
            raw=folder_name,
            type="catch_all",
            param_name=param,
        )

    # Dynamic: [slug], [id], etc.
    m = DYNAMIC_SEGMENT_RE.match(folder_name)
    if m:
        param = m.group(1)
        if not param.strip():
            raise ValueError(f"Dynamic segment has empty param name: {folder_name!r}")
        return RouteSegment(
            raw=folder_name,
            type="dynamic",
            param_name=param,
        )

    # Static folder
    return RouteSegment(
        raw=folder_name,
        type="static",
    )


def build_url_path(segments: list) -> str:
    """Build URL path from route segments (excluding route groups)."""
    parts = []
    for seg in segments:
        if seg.type == "route_group":
            continue
        elif seg.type == "dynamic":
            parts.append(f":{seg.param_name}")
        elif seg.type == "catch_all":
            parts.append(f"*{seg.param_name}")
        else:
            parts.append(seg.raw)

    if not parts:
        return "/"

    return "/" + "/".join(parts)


# FIX #399: Cache layout lookups to avoid repeated disk I/O
_layout_cache = {}

def find_layouts_for_dir(dir_path: str, home_dir: str) -> list:
    """Walk up from dir_path to home_dir, collecting all layout.tw files."""
    _cache_key = (os.path.abspath(dir_path), os.path.abspath(home_dir))
    if _cache_key in _layout_cache:
        return _layout_cache[_cache_key]
    layouts = []

    current = os.path.abspath(dir_path)
    home_abs = os.path.abspath(home_dir)

    # Walk from current dir up to home_dir
    while True:
        layout_path = os.path.join(current, LAYOUT_FILE)
        if os.path.exists(layout_path):
            is_root = (current == home_abs)
            # FIX #378/#379: Use os.path.relpath for cross-platform depth calculation
            rel = os.path.relpath(current, home_abs)
            depth = 0 if rel == "." else rel.count(os.sep) + 1
            layouts.append(LayoutInfo(
                file_path=layout_path,
                dir_path=current,
                depth=depth,
                is_root=is_root,
            ))

        if current == home_abs:
            break

        parent = os.path.dirname(current)
        if parent == current:  # Root of filesystem
            break
        current = parent

    # Reverse: root → innermost
    layouts.reverse()
    _layout_cache[_cache_key] = layouts
    return layouts


def find_special_files(dir_path: str) -> dict:
    """Find loading.tw, not-found.tw, error.tw in a directory."""
    result = {
        "loading": "",
        "not_found": "",
        "error": "",
    }

    loading = os.path.join(dir_path, LOADING_FILE)
    if os.path.exists(loading):
        result["loading"] = loading

    not_found = os.path.join(dir_path, NOT_FOUND_FILE)
    if os.path.exists(not_found):
        result["not_found"] = not_found

    error = os.path.join(dir_path, ERROR_FILE)
    if os.path.exists(error):
        result["error"] = error

    return result

# FIX #380: Cache for special files lookup to avoid repeated disk I/O
_special_files_cache = {}

def find_special_files_cached(dir_path: str, home_dir: str = "") -> dict:
    """Cached version of find_special_files that also searches parent dirs."""
    cache_key = dir_path
    if cache_key in _special_files_cache:
        return _special_files_cache[cache_key]
    result = find_special_files(dir_path)
    _special_files_cache[cache_key] = result
    return result


def discover_routes(home_dir: str) -> list:
    """
    Walk the [home]/ directory tree and discover all routes.

    Returns a list of RouteInfo objects.

    Rules:
    - Each page.tw becomes a route
    - Each route.tw becomes an API route
    - Layouts are collected by walking up from page dir to home_dir
    - Route groups (folder) don't appear in URL
    - Dynamic routes [slug] become :slug in URL
    - Catch-all [...slug] becomes *slug in URL
    """
    routes = []

    if not os.path.isdir(home_dir):
        return routes

    home_abs = os.path.abspath(home_dir)

    for root, dirs, files in os.walk(home_abs):
        # Skip hidden dirs and internal dirs
        dirs[:] = [d for d in dirs if not d.startswith(".") and d != "node_modules"]

        # FIX #400: Case-insensitive check for page.tw
        _files_lower = {f.lower(): f for f in files}
        if PAGE_FILE in files or PAGE_FILE.lower() in _files_lower:
            # Build route segments from path relative to home
            rel_path = os.path.relpath(root, home_abs)
            if rel_path == ".":
                segments = []
            else:
                # FIX #397: Handle both os.sep and / for cross-platform
                folder_parts = rel_path.replace("/", os.sep).split(os.sep)
                segments = [classify_segment(p) for p in folder_parts if p]

            url = build_url_path(segments)

            # Find layouts (walk up to home)
            layout_files = find_layouts_for_dir(root, home_abs)

            # Find special files (loading, not-found, error)
            # Search from current dir up through layout dirs
            special = find_special_files(root)
            if not special["not_found"]:
                # Check parent layout dirs
                for li in reversed(layout_files):
                    if li.dir_path != root:
                        parent_special = find_special_files(li.dir_path)
                        if parent_special["not_found"]:
                            special["not_found"] = parent_special["not_found"]
                            break

            route = RouteInfo(
                file_path=os.path.join(root, PAGE_FILE),
                url_path=url,
                segments=segments,
                layout_files=[li.file_path for li in layout_files],
                loading_file=special["loading"],
                not_found_file=special["not_found"],
                error_file=special["error"],
                is_api=False,
            )
            routes.append(route)

        # Check for route.tw (API route)
        # FIX #382: If both page.tw and route.tw exist in same dir, warn and skip route.tw
        if ROUTE_FILE in files:
            if PAGE_FILE in files:
                logger.warning("Both page.tw and route.tw found in %s — route.tw will be ignored", root)
                continue
            rel_path = os.path.relpath(root, home_abs)
            if rel_path == ".":
                segments = []
            else:
                # FIX #397: Handle both os.sep and / for cross-platform
                folder_parts = rel_path.replace("/", os.sep).split(os.sep)
                segments = [classify_segment(p) for p in folder_parts if p]

            url = build_url_path(segments)

            # FIX #393: API routes don't need layout files
            layout_files = find_layouts_for_dir(root, home_abs)

            route = RouteInfo(
                file_path=os.path.join(root, ROUTE_FILE),
                url_path=url,
                segments=segments,
                layout_files=[li.file_path for li in layout_files],
                is_api=True,
                api_file=os.path.join(root, ROUTE_FILE),
            )
            routes.append(route)

    # FIX #390: Deduplicate routes by URL — warn on conflicts
    _seen_urls = {}
    _deduped = []
    for r in routes:
        if r.url_path in _seen_urls:
            logger.warning("Duplicate route URL %s from %s (already defined by %s) — ignoring",
                          r.url_path, r.file_path, _seen_urls[r.url_path])
            continue
        _seen_urls[r.url_path] = r.file_path
        _deduped.append(r)
    return _deduped

def match_route(routes: list, url_path: str) -> tuple:
    """
    Match a URL path against discovered routes.

    Returns (RouteInfo, params_dict) or (None, None).
    """
    # FIX #385/#386: Normalize URL — handle trailing slashes consistently
    # Store original for redirect detection, then strip for matching
    _had_trailing_slash = url_path.endswith("/") and url_path != "/"
    url_path = url_path.rstrip("/") or "/"
    url_parts = [p for p in url_path.split("/") if p and not p.isspace()]  # FIX #403: Skip empty/whitespace segments

    best_match = None
    best_params = None
    best_score = -1  # Root route (score=0) should still beat initial -1

    for route in routes:
        route_url = route.url_path
        route_parts = [p for p in route_url.split("/") if p]

        if len(url_parts) != len(route_parts):
            # Try catch-all
            if route_parts and route_parts[-1].startswith("*"):
                if len(url_parts) >= len(route_parts) - 1:
                    # Check static parts match
                    match = True
                    params = {}
                    for i, rp in enumerate(route_parts[:-1]):
                        if rp.startswith(":"):
                            params[rp[1:]] = url_parts[i] if i < len(url_parts) else ""
                        elif rp != url_parts[i]:
                            match = False
                            break
                    if match:
                        param_name = route_parts[-1][1:]
                        # FIX #398: catch-all should preserve leading segment correctly
                        _caught = url_parts[len(route_parts)-1:]
                        params[param_name] = "/".join(_caught) if _caught else ""
                        score = len(route_parts) * 10 + 1
                        if score > best_score:
                            best_match = route
                            best_params = params
                            best_score = score
            continue

        match = True
        params = {}
        for i, rp in enumerate(route_parts):
            if rp.startswith(":"):
                params[rp[1:]] = url_parts[i]
            elif rp.startswith("*"):
                params[rp[1:]] = "/".join(url_parts[i:])
            elif rp != url_parts[i]:
                match = False
                break

        if match:
            # Score: prefer static matches over dynamic
            score = 0
            for rp in route_parts:
                if rp.startswith(":") or rp.startswith("*"):
                    score += 1
                else:
                    score += 10
            if score > best_score:
                best_match = route
                best_params = params
                best_score = score

    if best_match:
        return best_match, best_params
    return None, None


def get_layout_chain(route: RouteInfo) -> list:
    """Return layout file paths for a route (root → innermost)."""
    return route.layout_files


def is_root_layout(layout_path: str, home_dir: str) -> bool:
    """Check if a layout file is the root layout."""
    return os.path.abspath(os.path.dirname(layout_path)) == os.path.abspath(home_dir)


def route_to_output_path(url_path: str) -> str:
    """Convert a URL path to an output file path (cross-platform safe)."""
    # FIX #389: Use forward slashes consistently, not os.path.join
    clean = url_path.strip("/")
    if not clean:
        return "index.html"
    # Use forward slashes for output paths (works on all platforms)
    return clean.replace("/", os.sep) + os.sep + "index.html"


# ─── Layout Parsing Support ──────────────────────────────────────────────

# Marker for {children} in layout body
CHILDREN_MARKER = "{children}"


def extract_children_slot(nodes: list) -> tuple:
    """
    Split layout body nodes at the {children} marker.

    Returns (before_children, after_children).
    If no {children} marker found, returns (all_nodes, []).
    """
    before = []
    after = []

    found_children = False
    for node in nodes:
        # Check if this node is a {children} marker
        # Could be a text node with content "{children}"
        # Or a special element node
        if not found_children:
            # Check for text content containing {children}
            if hasattr(node, "tag") and node.tag == "text":
                if hasattr(node, "text") and CHILDREN_MARKER in str(node.text):
                    found_children = True
                    continue
            elif hasattr(node, "tag") and node.tag == "children":
                found_children = True
                continue
            before.append(node)
        else:
            after.append(node)

    return before, after


# ─── Legacy Compatibility ─────────────────────────────────────────────────

# FIX #388: Cache for has_app_router_structure to avoid repeated os.walk
_app_router_structure_cache = {}

def has_app_router_structure(home_dir: str) -> bool:
    """Check if a project uses the new App Router structure."""
    home_abs = os.path.abspath(home_dir)
    # Check cache
    if home_abs in _app_router_structure_cache:
        return _app_router_structure_cache[home_abs]
    if not os.path.isdir(home_dir):
        _app_router_structure_cache[home_abs] = False
        return False

    # Check for root layout or root page first (fast path)
    if os.path.exists(os.path.join(home_dir, LAYOUT_FILE)):
        _app_router_structure_cache[home_abs] = True
        return True
    if os.path.exists(os.path.join(home_dir, PAGE_FILE)):
        _app_router_structure_cache[home_abs] = True
        return True

    # Check subdirectories — stop at first match
    for root, dirs, files in os.walk(home_dir):
        dirs[:] = [d for d in dirs if not d.startswith(".") and d != "node_modules"]
        if PAGE_FILE in files or LAYOUT_FILE in files:
            _app_router_structure_cache[home_abs] = True
            return True

    _app_router_structure_cache[home_abs] = False
    return False


def has_legacy_structure(home_dir: str) -> bool:
    """Check if a project uses the legacy structure (pages/ + layouts/)."""
    pages_dir = os.path.join(home_dir, "pages")
    layouts_dir = os.path.join(home_dir, "layouts")
    # FIX #405: Check dir existence (backward compatible with empty dirs)
    return os.path.isdir(pages_dir) or os.path.isdir(layouts_dir)
