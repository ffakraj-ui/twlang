"""
Complete project dependency graph for TW Framework.

Tracks pages, components, layouts, middleware, APIs, imports, and assets.
Persisted between builds for incremental rebuilds.
"""

import json
import logging
import os
from typing import Dict, List, Optional, Set

from . import compiler

logger = logging.getLogger(__name__)

GRAPH_FILE = "dependency-graph.json"


class DependencyGraph:
    """Maintains a directed graph of project dependencies."""

    def __init__(self, project_root: str) -> None:
        self.project_root = project_root
        self.graph: Dict[str, List[str]] = {}
        self.reverse: Dict[str, List[str]] = {}
        self._load()

    def _load(self) -> None:
        path = os.path.join(self.project_root, ".tw", GRAPH_FILE)
        if os.path.exists(path):
            try:
                with open(path, "r", encoding="utf-8") as f:
                    data = json.load(f)
                self.graph = data.get("forward", {})
                self.reverse = data.get("reverse", {})
            except (json.JSONDecodeError, OSError):
                logger.warning("Failed to load dependency graph; starting fresh")
                self.graph = {}
                self.reverse = {}

    def save(self) -> None:
        path = os.path.join(self.project_root, ".tw", GRAPH_FILE)
        os.makedirs(os.path.dirname(path), exist_ok=True)
        with open(path, "w", encoding="utf-8") as f:
            json.dump({"forward": self.graph, "reverse": self.reverse}, f, indent=2)

    def add_dependency(self, source: str, target: str) -> None:
        if source not in self.graph:
            self.graph[source] = []
        if target not in self.graph[source]:
            self.graph[source].append(target)
        if target not in self.reverse:
            self.reverse[target] = []
        if source not in self.reverse[target]:
            self.reverse[target].append(source)

    def get_dependents(self, node: str) -> List[str]:
        """Return all nodes that depend on the given node."""
        return self.reverse.get(node, [])

    def get_dependencies(self, node: str) -> List[str]:
        """Return all nodes that the given node depends on."""
        return self.graph.get(node, [])

    def get_affected_nodes(self, changed_nodes: Set[str]) -> Set[str]:
        """Return all nodes that need to be rebuilt when the given nodes change."""
        affected = set(changed_nodes)
        queue = list(changed_nodes)
        while queue:
            current = queue.pop(0)
            for dependent in self.get_dependents(current):
                if dependent not in affected:
                    affected.add(dependent)
                    queue.append(dependent)
        return affected

    def build_from_project(self) -> None:
        """Build the dependency graph by scanning the project."""
        self.graph = {}
        self.reverse = {}
        pages = compiler.discover_pages()
        for page in pages:
            page_path = page["path"]
            deps = compiler.collect_page_dependencies(page_path)
            for dep in deps:
                self.add_dependency(page_path, dep)
        self.save()


__all__ = ["DependencyGraph"]
