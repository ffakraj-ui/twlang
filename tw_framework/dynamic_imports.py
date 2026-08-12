"""
Dynamic imports / lazy loading support for TW Framework.

Components with `lazy true` are compiled into separate chunks and loaded on demand.
"""

import hashlib
import json
import logging
import os
from typing import Dict, List, Optional

from . import compiler
import re

logger = logging.getLogger(__name__)


def extract_lazy_components(page_path: str) -> List[str]:
    """Return a list of component names that are marked as lazy in the given page."""
    raw = compiler.read_text_file(page_path)
    lazy_components = []
    # Simple regex-based detection (in production, use the AST)
    import re
    for match in re.finditer(r'(\w+)\s*\{[^}]*lazy\s+true[^}]*\}', raw):
        lazy_components.append(match.group(1))
    return lazy_components


def generate_lazy_chunks(page_path: str, output_dir: str) -> Dict[str, str]:
    """Generate separate chunks for lazy components and return a mapping."""
    lazy_comps = extract_lazy_components(page_path)
    chunk_map = {}
    for comp_name in lazy_comps:
        comp_path = compiler.resolve_component_path(comp_name)
        if comp_path and os.path.exists(comp_path):
            raw = compiler.read_text_file(comp_path)
            # In production, compile the component to JS
            js_content = f"// Lazy component: {comp_name}\n"
            digest = hashlib.sha256(js_content.encode("utf-8")).hexdigest()[:12]
            filename = f"lazy_{comp_name}.{digest}.js"
            chunk_dir = os.path.join(output_dir, "_tw", "chunks")
            os.makedirs(chunk_dir, exist_ok=True)
            chunk_path = os.path.join(chunk_dir, filename)
            if not os.path.exists(chunk_path):
                with open(chunk_path, "w", encoding="utf-8") as f:
                    f.write(js_content)
            chunk_map[comp_name] = f"/_tw/chunks/{filename}"
    return chunk_map


__all__ = ["extract_lazy_components", "generate_lazy_chunks"]
