"""
Dead code detection for TW Framework.

Detects unused pages, APIs, middleware, components, and layouts.
"""

import logging
import os
from typing import Dict, List

from . import compiler

logger = logging.getLogger(__name__)


def detect_dead_code(project_root: str) -> Dict[str, List[str]]:
    """Return lists of dead code items."""
    dead = {
        "pages": [],
        "apis": [],
        "middleware": [],
        "components": [],
        "layouts": [],
    }

    # Discover all pages
    pages = compiler.discover_pages()
    page_paths = {p["path"] for p in pages}

    # Check for orphaned page files
    pages_dir = compiler.PAGES_DIR
    if os.path.isdir(pages_dir):
        for root, _, files in os.walk(pages_dir):
            for fname in files:
                if fname.endswith(".tw"):
                    full_path = os.path.join(root, fname)
                    if full_path not in page_paths:
                        dead["pages"].append(full_path)

    # TODO: Add API, middleware, component, and layout detection
    return dead


__all__ = ["detect_dead_code"]
