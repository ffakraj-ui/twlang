"""
Automatic code splitting for TW Framework.

Generates separate JavaScript chunks for each page and shared runtime.
"""

import hashlib
import json
import logging
import os
from typing import Dict, List, Optional

from . import compiler

logger = logging.getLogger(__name__)


def generate_chunks(pages: List[dict], output_dir: str) -> Dict[str, str]:
    """Generate code-split chunks for each page and return a mapping of page path to chunk URL."""
    chunk_map = {}
    shared_runtime = _build_shared_runtime()
    runtime_url = _write_chunk(shared_runtime, "runtime", output_dir)
    chunk_map["__shared__"] = runtime_url

    for page in pages:
        page_path = page["path"]
        page_js = _build_page_js(page)
        if page_js:
            chunk_name = _page_chunk_name(page_path)
            chunk_url = _write_chunk(page_js, chunk_name, output_dir)
            chunk_map[page_path] = chunk_url
    return chunk_map


def _build_shared_runtime() -> str:
    """Build the shared runtime JavaScript that is loaded on every page."""
    return """
window.__tw = window.__tw || {};
window.__tw.router = window.__tw.router || {};
window.__tw.router.goto = function(path) {
  window.location.href = path;
};
window.__twInvoke = function(name, event) {
  var fn = window.__tw[name];
  if (typeof fn === 'function') return fn(event);
};
"""


def _build_page_js(page: dict) -> Optional[str]:
    """Build the JavaScript for a single page (events, router, etc.)."""
    # In a real implementation, this would extract event handlers and router calls
    # from the compiled page AST. For now, return a minimal placeholder.
    return None


def _page_chunk_name(page_path: str) -> str:
    """Generate a deterministic chunk name from the page path."""
    normalized = page_path.replace(os.sep, "/").lstrip("/")
    return normalized.replace("/", "_").replace(".", "_")


def _write_chunk(js_content: str, name: str, output_dir: str) -> str:
    """Write a JavaScript chunk to the output directory and return its URL."""
    digest = hashlib.sha256(js_content.encode("utf-8")).hexdigest()[:12]
    filename = f"{name}.{digest}.js"
    chunk_dir = os.path.join(output_dir, "_tw", "chunks")
    os.makedirs(chunk_dir, exist_ok=True)
    chunk_path = os.path.join(chunk_dir, filename)
    if not os.path.exists(chunk_path):
        with open(chunk_path, "w", encoding="utf-8") as f:
            f.write(js_content)
    return f"/_tw/chunks/{filename}"


__all__ = ["generate_chunks"]
