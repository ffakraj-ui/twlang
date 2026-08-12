"""
TW Framework - Static Export & SPA Mode

Implements:
24. Static Export (SPA Mode) - output: export to export entire app as static SPA
33. generateStaticParams - Build-time dynamic route pre-rendering
22. Automatic Static Optimization - Auto-detect if page can be static
"""

from __future__ import annotations

import os
import re
import json
import time
import logging
from dataclasses import dataclass, field
from typing import Any, Callable, Dict, List, Optional, Tuple

logger = logging.getLogger(__name__)


@dataclass
class StaticRoute:
    """A route that can be statically exported."""
    path: str
    is_dynamic: bool = False  # Has [param] segments
    params: List[str] = field(default_factory=list)  # Param names
    static_params: List[Dict[str, str]] = field(default_factory=list)  # generateStaticParams output
    output_path: str = ""  # File path for the exported HTML
    is_spa: bool = False  # Client-side only (no SSR)
    priority: int = 0  # Higher = export first


@dataclass
class ExportConfig:
    """Configuration for static export."""
    output_dir: str = "out"
    export_mode: str = "static"  # static | spa | hybrid
    trailing_slash: str = "always"  # always | never | auto
    include_drafts: bool = False
    minify_html: bool = True
    copy_assets: bool = True
    generate_sitemap: bool = True
    generate_rss: bool = False
    sitemap_base_url: str = ""
    exclude_routes: List[str] = field(default_factory=list)
    concurrency: int = 4


class StaticExporter:
    """Static export engine.

    Exports the entire application as static HTML files:
    - Static pages: Pre-rendered at build time
    - Dynamic routes: Pre-rendered with generateStaticParams
    - SPA pages: Exported as client-side only (no SSR)
    - Hybrid: Some pages static, some dynamic

    Output structure:
        out/
          index.html
          about/index.html
          blog/[slug]/index.html  -> blog/post-1/index.html, blog/post-2/index.html
          _assets/  (JS, CSS, images)
          _redirects  (redirect rules)
          sitemap.xml
    """

    def __init__(self, config: Optional[ExportConfig] = None):
        self.config = config or ExportConfig()
        self._routes: List[StaticRoute] = []
        self._exported: List[str] = []
        self._errors: List[Dict[str, str]] = []
        self._stats: Dict[str, Any] = {
            "total_routes": 0,
            "exported": 0,
            "errors": 0,
            "total_size_bytes": 0,
            "duration_ms": 0,
        }

    def add_route(self, path: str, is_dynamic: bool = False,
                  params: Optional[List[str]] = None,
                  static_params: Optional[List[Dict]] = None,
                  is_spa: bool = False) -> StaticRoute:
        """Register a route for static export."""
        route = StaticRoute(
            path=path,
            is_dynamic=is_dynamic,
            params=params or [],
            static_params=static_params or [],
            is_spa=is_spa,
            output_path=self._path_to_file(path),
        )
        self._routes.append(route)
        return route

    def discover_routes(self, pages_dir: str) -> List[StaticRoute]:
        """Discover routes from a pages directory structure."""
        if not os.path.isdir(pages_dir):
            return []

        for root, dirs, files in os.walk(pages_dir):
            dirs[:] = [d for d in dirs if not d.startswith("_") and not d.startswith(".")]
            for fname in sorted(files):
                if not fname.endswith((".py", ".js", ".ts")):
                    continue
                if fname.startswith("_"):
                    continue

                rel_path = os.path.relpath(os.path.join(root, fname), pages_dir)
                route_path = self._file_to_route(rel_path)
                is_dynamic = "[" in route_path
                params = re.findall(r"\[(\w+)\]", route_path)

                self.add_route(
                    path=route_path,
                    is_dynamic=is_dynamic,
                    params=params,
                )

        logger.info("Discovered %d routes from %s", len(self._routes), pages_dir)
        return self._routes

    def export_route(self, route: StaticRoute,
                     render_fn: Callable[[str, Dict], str]) -> List[str]:
        """Export a single route to static HTML.

        For dynamic routes with static_params, generates one HTML file
        per parameter combination.
        """
        exported_files: List[str] = []

        if route.is_dynamic and route.static_params:
            # Generate one file per param combination
            for params in route.static_params:
                # Replace [param] with actual values
                actual_path = route.path
                for key, value in params.items():
                    actual_path = actual_path.replace(f"[{key}]", str(value))

                output_path = self._path_to_file(actual_path)
                html = render_fn(actual_path, params)

                if self.config.minify_html:
                    html = self._minify_html(html)

                self._write_file(output_path, html)
                exported_files.append(output_path)
                self._stats["exported"] += 1
                self._stats["total_size_bytes"] += len(html)
        else:
            # Static or SPA route
            html = render_fn(route.path, {})

            if self.config.minify_html and not route.is_spa:
                html = self._minify_html(html)

            self._write_file(route.output_path, html)
            exported_files.append(route.output_path)
            self._stats["exported"] += 1
            self._stats["total_size_bytes"] += len(html)

        self._exported.extend(exported_files)
        return exported_files

    def export_all(self, render_fn: Callable[[str, Dict], str]) -> Dict[str, Any]:
        """Export all registered routes."""
        start_time = time.time()
        self._stats["total_routes"] = len(self._routes)

        for route in self._routes:
            # Skip excluded routes
            if any(route.path.startswith(ex) for ex in self.config.exclude_routes):
                continue

            try:
                self.export_route(route, render_fn)
            except Exception as e:
                logger.error("Failed to export %s: %s", route.path, e)
                self._errors.append({"route": route.path, "error": str(e)})
                self._stats["errors"] += 1

        # Generate sitemap
        if self.config.generate_sitemap:
            self._generate_sitemap()

        # Generate redirects file
        self._generate_redirects()

        self._stats["duration_ms"] = (time.time() - start_time) * 1000
        return self.get_stats()

    def _path_to_file(self, path: str) -> str:
        """Convert a route path to a file path."""
        if path == "/" or path == "":
            return os.path.join(self.config.output_dir, "index.html")

        # Remove leading slash
        path = path.lstrip("/")

        # Handle trailing slash
        if self.config.trailing_slash == "always":
            return os.path.join(self.config.output_dir, path, "index.html")
        elif self.config.trailing_slash == "never":
            return os.path.join(self.config.output_dir, path + ".html")
        else:  # auto
            return os.path.join(self.config.output_dir, path, "index.html")

    @staticmethod
    def _file_to_route(file_path: str) -> str:
        """Convert a file path to a route path."""
        # Remove extension
        path = re.sub(r"\.(py|js|ts|jsx|tsx)$", "", file_path)
        # Replace os.sep with /
        path = path.replace(os.sep, "/")
        # Handle index files
        path = re.sub(r"/index$", "", path)
        if not path.startswith("/"):
            path = "/" + path
        return path

    @staticmethod
    def _minify_html(html: str) -> str:
        """Minify HTML output."""
        # Remove HTML comments
        html = re.sub(r"<!--.*?-->", "", html, flags=re.DOTALL)
        # Remove extra whitespace
        html = re.sub(r"\s+", " ", html)
        # Remove whitespace between tags
        html = re.sub(r">\s+<", "><", html)
        return html.strip()

    def _write_file(self, filepath: str, content: str) -> None:
        """Write a file, creating directories as needed."""
        os.makedirs(os.path.dirname(filepath), exist_ok=True)
        with open(filepath, "w", encoding="utf-8") as f:
            f.write(content)

    def _generate_sitemap(self) -> None:
        """Generate sitemap.xml."""
        if not self.config.sitemap_base_url:
            return

        urls: List[str] = []
        for route in self._routes:
            if route.is_dynamic and route.static_params:
                for params in route.static_params:
                    actual_path = route.path
                    for key, value in params.items():
                        actual_path = actual_path.replace(f"[{key}]", str(value))
                    urls.append(self.config.sitemap_base_url + actual_path)
            else:
                urls.append(self.config.sitemap_base_url + route.path)

        sitemap_path = os.path.join(self.config.output_dir, "sitemap.xml")
        xml_parts = ['<?xml version="1.0" encoding="UTF-8"?>']
        xml_parts.append('<urlset xmlns="http://www.sitemaps.org/schemas/sitemap/0.9">')
        for url in urls:
            xml_parts.append(f"  <url><loc>{url}</loc></url>")
        xml_parts.append("</urlset>")

        self._write_file(sitemap_path, "\n".join(xml_parts))

    def _generate_redirects(self) -> None:
        """Generate _redirects file for hosting platforms."""
        redirects_path = os.path.join(self.config.output_dir, "_redirects")
        # Basic SPA fallback
        content = "/*    /index.html   200\n"
        self._write_file(redirects_path, content)

    def get_stats(self) -> Dict[str, Any]:
        return {
            **self._stats,
            "total_size_kb": round(self._stats["total_size_bytes"] / 1024, 2),
            "exported_files": len(self._exported),
            "errors_list": self._errors,
        }


class AutoStaticOptimizer:
    """Automatic static optimization.

    Analyzes pages and determines if they can be statically optimized:
    - Pages without server-side data fetching -> static
    - Pages with getServerSideProps -> dynamic (SSR)
    - Pages with getStaticProps -> static (SSG)
    - Pages with no data fetching -> auto-static

    This runs at build time to determine the rendering strategy
    for each page.
    """

    def __init__(self):
        self._analysis: Dict[str, Dict[str, Any]] = {}

    def analyze_page(self, path: str, source: str) -> Dict[str, Any]:
        """Analyze a page to determine its rendering strategy."""
        has_ssr = bool(re.search(r"getServerSideProps|get_initial_props|tw\.server\.fetch", source))
        has_ssg = bool(re.search(r"getStaticProps|generateStaticParams", source))
        has_dynamic = "[" in path

        if has_ssr:
            strategy = "ssr"
        elif has_ssg:
            strategy = "ssg"
        elif has_dynamic:
            strategy = "ssg"  # Dynamic routes default to SSG
        else:
            strategy = "static"

        result = {
            "path": path,
            "strategy": strategy,
            "has_ssr": has_ssr,
            "has_ssg": has_ssg,
            "is_dynamic": has_dynamic,
            "can_prerender": strategy in ("static", "ssg"),
        }

        self._analysis[path] = result
        return result

    def get_static_pages(self) -> List[str]:
        return [p for p, a in self._analysis.items() if a["strategy"] == "static"]

    def get_ssg_pages(self) -> List[str]:
        return [p for p, a in self._analysis.items() if a["strategy"] == "ssg"]

    def get_ssr_pages(self) -> List[str]:
        return [p for p, a in self._analysis.items() if a["strategy"] == "ssr"]

    def get_all_analysis(self) -> Dict[str, Dict[str, Any]]:
        return dict(self._analysis)


__all__ = [
    "StaticRoute", "ExportConfig", "StaticExporter", "AutoStaticOptimizer",
]
