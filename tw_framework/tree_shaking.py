"""
Tree shaking for TW Framework.

Removes unused components, CSS, JavaScript, assets, and imports.
"""

import logging
import os
import re
from typing import Dict, List, Set

from . import compiler

logger = logging.getLogger(__name__)


def _find_inline_component_refs(raw: str) -> Set[str]:
    """Scan raw .tw source for inline component references.

    Components are used as tag names with a capital first letter,
    e.g. Navbar {}, Button { ... }, Card { title "..." }
    """
    refs: Set[str] = set()
    # Match capitalized identifiers followed by { (component invocation)
    # Also match component paths like ui/Button
    for m in re.finditer(r'(?:^|\n|\s)([A-Z][a-zA-Z0-9_/]+)\s*\{', raw):
        name = m.group(1).strip()
        # Skip HTML/standard tags that start with uppercase by convention
        if name in ("True", "False", "None"):
            continue
        refs.add(name)
    return refs


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
    all_raw_sources: List[str] = []

    for page in pages:
        raw = compiler.read_text_file(page["path"])
        all_raw_sources.append(raw)
        page_dir = os.path.dirname(page["path"])
        try:
            directives = compiler.extract_directives_from_source(raw, page_dir)
        except Exception as e:
            logger.warning("Tree shaking: skipping %s (%s)", page["path"], e)
            continue
        # Track explicitly imported components
        for comp_name in directives.get("imports", []):
            used_components.add(comp_name)
        # Track inline component references (Navbar {}, Button {}, etc.)
        used_components.update(_find_inline_component_refs(raw))

    # Also scan layout files — components are often used in layouts
    home_dir = compiler.HOME_DIR
    if os.path.isdir(home_dir):
        for fname in os.listdir(home_dir):
            if fname.endswith(".tw") and fname != "page.tw":
                layout_path = os.path.join(home_dir, fname)
                try:
                    raw = compiler.read_text_file(layout_path)
                    used_components.update(_find_inline_component_refs(raw))
                except Exception:
                    pass

    # Find all component files
    components_dir = compiler.COMPONENTS_DIR
    if os.path.isdir(components_dir):
        for fname in os.listdir(components_dir):
            if fname.endswith(".tw"):
                comp_name = fname[:-3]
                if comp_name not in used_components:
                    # Double-check: scan all page sources for this component name
                    found = False
                    for raw in all_raw_sources:
                        if re.search(rf'(?:^|\n|\s){re.escape(comp_name)}\s*\{{', raw):
                            found = True
                            break
                    if not found:
                        unused["components"].append(comp_name)

    # TODO: Add CSS, JS, assets, and import analysis
    return unused


__all__ = ["shake_project"]
