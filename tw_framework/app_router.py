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
    # Route group: (main), (auth), etc.
    m = ROUTE_GROUP_RE.match(folder_name)
    if m:
        return RouteSegment(
            raw=folder_name,
            type="route_group",
            param_name=m.group(1),
        )

    # Catch-all: [...slug]
    m = CATCH_ALL_RE.match(folder_name)
    if m:
        return RouteSegment(
            raw=folder_name,
            type="catch_all",
            param_name=m.group(1),
        )

    # Dynamic: [slug], [id], etc.
    m = DYNAMIC_SEGMENT_RE.match(folder_name)
    if m:
        return RouteSegment(
            raw=folder_name,
            type="dynamic",
            param_name=m.group(1),
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


def find_layouts_for_dir(dir_path: str, home_dir: str) -> list:
    """
    Walk up from dir_path to home_dir, collecting all layout.tw files.

    Returns layouts in order: root → ... → innermost (closest to page).
    """
    layouts = []

    current = os.path.abspath(dir_path)
    home_abs = os.path.abspath(home_dir)

    # Walk from current dir up to home_dir
    while True:
        layout_path = os.path.join(current, LAYOUT_FILE)
        if os.path.exists(layout_path):
            is_root = (current == home_abs)
            depth = current.replace(home_abs, "").count(os.sep)
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

        # Check for page.tw
        if PAGE_FILE in files:
            # Build route segments from path relative to home
            rel_path = os.path.relpath(root, home_abs)
            if rel_path == ".":
                segments = []
            else:
                folder_parts = rel_path.split(os.sep)
                segments = [classify_segment(p) for p in folder_parts]

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
        if ROUTE_FILE in files:
            rel_path = os.path.relpath(root, home_abs)
            if rel_path == ".":
                segments = []
            else:
                folder_parts = rel_path.split(os.sep)
                segments = [classify_segment(p) for p in folder_parts]

            # API routes get /api prefix if under api/ folder
            url = build_url_path(segments)

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

    return routes


def match_route(routes: list, url_path: str) -> tuple:
    """
    Match a URL path against discovered routes.

    Returns (RouteInfo, params_dict) or (None, None).
    """
    # Normalize URL
    url_path = url_path.rstrip("/") or "/"
    url_parts = [p for p in url_path.split("/") if p]

    best_match = None
    best_params = None
    best_score = -1

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
                        params[param_name] = "/".join(url_parts[len(route_parts)-1:])
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
    """
    Convert a URL path to an output file path.

    /blog/my-post → blog/my-post/index.html
    / → index.html
    """
    clean = url_path.strip("/")
    if not clean:
        return os.path.join("index.html")
    return os.path.join(clean, "index.html")


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

def has_app_router_structure(home_dir: str) -> bool:
    """
    Check if a project uses the new App Router structure.

    Returns True if:
    - [home]/layout.tw exists, OR
    - [home]/page.tw exists, OR
    - Any subdirectory of [home] has a page.tw or layout.tw
    """
    if not os.path.isdir(home_dir):
        return False

    # Check for root layout or root page
    if os.path.exists(os.path.join(home_dir, LAYOUT_FILE)):
        return True
    if os.path.exists(os.path.join(home_dir, PAGE_FILE)):
        return True

    # Check subdirectories
    for root, dirs, files in os.walk(home_dir):
        dirs[:] = [d for d in dirs if not d.startswith(".")]
        if PAGE_FILE in files or LAYOUT_FILE in files:
            return True

    return False


def has_legacy_structure(home_dir: str) -> bool:
    """
    Check if a project uses the legacy structure ([home]/pages/ + [home]/layouts/).
    """
    pages_dir = os.path.join(home_dir, "pages")
    layouts_dir = os.path.join(home_dir, "layouts")
    return os.path.isdir(pages_dir) or os.path.isdir(layouts_dir)
