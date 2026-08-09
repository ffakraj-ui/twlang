"""
Tree shaking for TW Framework.

Removes unused components, CSS, JavaScript, assets, and imports.
"""

import logging
import os
from typing import Dict, List, Set

from . import compiler

logger = logging.getLogger(__name__)


def shake_project(project_root: str) -> Dict[str, List[str]]:
    """Analyze the project and return lists of unused items."""
    unused = {
        "components": [],
        "css": [],
        "js": [],
        "assets": [],
        "imports": [],
    }

    # Discover all pages and their used components
    pages = compiler.discover_pages()
    used_components: Set[str] = set()
    for page in pages:
        raw = compiler.read_text_file(page["path"])
        page_dir = os.path.dirname(page["path"])
        try:
            directives = compiler.extract_directives_from_source(raw, page_dir)
        except Exception as e:
            logger.warning("Tree shaking: skipping %s (%s)", page["path"], e)
            continue
        for comp_name in directives.get("imports", []):
            used_components.add(comp_name)

    # Find all component files
    components_dir = compiler.COMPONENTS_DIR
    if os.path.isdir(components_dir):
        for fname in os.listdir(components_dir):
            if fname.endswith(".tw"):
                comp_name = fname[:-3]
                if comp_name not in used_components:
                    unused["components"].append(comp_name)

    # TODO: Add CSS, JS, assets, and import analysis
    return unused


__all__ = ["shake_project"]
