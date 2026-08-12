"""
Automatic static/dynamic route detection for TW Framework.

When `render auto` is set, the compiler chooses the best rendering mode
based on the page's content and dependencies.
"""

import logging
from typing import Any, Optional

from . import compiler
import re

logger = logging.getLogger(__name__)


def determine_render_mode(page_path: str) -> Any:
    """Analyze a page and return the recommended render mode."""
    raw = compiler.read_text_file(page_path)
    # Check for explicit render mode
    import re
    match = re.search(r'render\s+(\w+)', raw)
    if match:
        mode = match.group(1).lower()
        if mode in ("static", "server", "edge"):
            return mode
    # Auto-detect: if the page has dynamic content (e.g., `for`, `if`, `state`), use server
    if "state {" in raw or "for " in raw or "if " in raw:
        return "server"
    return "static"


__all__ = ["determine_render_mode"]
