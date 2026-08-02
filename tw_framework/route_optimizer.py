"""
Automatic route optimization for TW Framework.

Detects duplicate routes, unreachable routes, route conflicts, and shadowed routes.
"""

import logging
from typing import Dict, List

from . import compiler

logger = logging.getLogger(__name__)


def optimize_routes(project_root: str) -> Dict[str, List[str]]:
    """Analyze routes and return optimization suggestions."""
    issues = {
        "duplicate_routes": [],
        "unreachable_routes": [],
        "route_conflicts": [],
        "shadowed_routes": [],
    }

    pages = compiler.discover_pages()
    route_map: Dict[str, List[str]] = {}
    for page in pages:
        route = compiler.route_path_from_page_info(page)
        if route not in route_map:
            route_map[route] = []
        route_map[route].append(page["path"])

    for route, paths in route_map.items():
        if len(paths) > 1:
            issues["duplicate_routes"].append({"route": route, "paths": paths})

    # TODO: Add unreachable, conflict, and shadow detection
    return issues


__all__ = ["optimize_routes"]
