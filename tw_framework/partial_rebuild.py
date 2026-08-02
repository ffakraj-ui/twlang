"""
Partial rebuild support for TW Framework.

When only one page changes, rebuild only affected pages using the dependency graph.
"""

import logging
from typing import List, Set

from . import compiler
from .dependency_graph import DependencyGraph

logger = logging.getLogger(__name__)


def get_pages_to_rebuild(project_root: str, changed_files: Set[str]) -> List[dict]:
    """Return the list of pages that need to be rebuilt given the changed files."""
    graph = DependencyGraph(project_root)
    affected = graph.get_affected_nodes(changed_files)
    pages = compiler.discover_pages()
    return [p for p in pages if p["path"] in affected]


__all__ = ["get_pages_to_rebuild"]
