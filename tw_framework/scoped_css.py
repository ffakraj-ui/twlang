"""
TW Scoped CSS (CSS Modules) — v0.8.37

Automatically scopes .tss files to their parent component.
When a .tss file has the same name as a .tw component (e.g. Button.tw + Button.tss),
the styles are scoped with a unique data attribute instead of being global.

Usage:
  - Place Button.tss next to Button.tw
  - All selectors in Button.tss are automatically scoped
  - No manual data-scoped attributes needed

Example:
  Button.tss:
    .btn { background blue }       →  .btn[data-tw-abc123] { background: blue }
    h1 { color red }               →  [data-tw-abc123] h1 { color: red }
"""

from __future__ import annotations

import hashlib
import os
import re
from typing import Optional


def generate_scope_id(component_name: str) -> str:
    """Generate a unique scope ID from component name."""
    h = hashlib.md5(component_name.encode()).hexdigest()[:8]
    return f"tw-{h}"


def scope_css(css: str, scope_id: str) -> str:
    """
    Scope CSS rules with a data attribute selector.

    .btn { ... }       →  .btn[data-tw-{scope_id}] { ... }
    h1 { ... }         →  [data-tw-{scope_id}] h1 { ... }
    .btn:hover { ... } →  .btn[data-tw-{scope_id}]:hover { ... }

    @media queries are preserved, inner rules are scoped.
    @keyframes are NOT scoped (they need global names).
    """
    scoped_lines = []
    in_media = False
    in_keyframes = False
    media_buffer = []

    attr = f"[data-tw-{scope_id}]"

    for line in css.split("\n"):
        stripped = line.strip()

        # Don't scope @keyframes
        if stripped.startswith("@keyframes") or stripped.startswith("@-webkit-keyframes"):
            in_keyframes = True
            scoped_lines.append(line)
            continue
        if in_keyframes:
            if stripped == "}":
                in_keyframes = False
            scoped_lines.append(line)
            continue

        # Handle @media
        if stripped.startswith("@media"):
            in_media = True
            scoped_lines.append(line)
            media_buffer = []
            continue

        if in_media:
            if stripped == "}":
                in_media = False
                for mline in media_buffer:
                    scoped_lines.append(_scope_selector_line(mline, attr))
                scoped_lines.append("}")
            else:
                media_buffer.append(line)
            continue

        scoped_lines.append(_scope_selector_line(line, attr))

    return "\n".join(scoped_lines)


def _scope_selector_line(line: str, attr: str) -> str:
    """Scope a single CSS line."""
    stripped = line.strip()
    if not stripped:
        return line

    # Don't scope properties (lines inside a rule block)
    if ":" in stripped and "{" not in stripped and "}" not in stripped:
        return line

    # Check if this is a selector line
    if "{" in stripped:
        brace_idx = line.index("{")
        selector_part = line[:brace_idx].strip()
        rest = line[brace_idx:]

        selectors = [s.strip() for s in selector_part.split(",")]
        scoped_selectors = []
        for sel in selectors:
            if not sel:
                continue
            # Don't scope :root, @-rules, or html/body
            if sel.startswith(":root") or sel.startswith("@") or sel in ("html", "body"):
                scoped_selectors.append(sel)
                continue
            # Don't double-scope
            if attr in sel:
                scoped_selectors.append(sel)
                continue
            # For class/id selectors, append attr
            if sel.startswith(".") or sel.startswith("#"):
                pseudo_match = re.match(r'^(\.\S+|#[\w-]+)(:.+)?$', sel)
                if pseudo_match:
                    base = pseudo_match.group(1)
                    pseudo = pseudo_match.group(2) or ""
                    scoped_selectors.append(f"{base}{attr}{pseudo}")
                else:
                    scoped_selectors.append(f"{sel}{attr}")
            else:
                # Tag selectors: prepend attr
                scoped_selectors.append(f"{attr} {sel}")

        indent = line[:len(line) - len(line.lstrip())]
        return f"{indent}{', '.join(scoped_selectors)} {rest}"

    return line


def find_scoped_stylesheet(component_path: str) -> Optional[str]:
    """
    Find a .tss file that matches a .tw component.
    e.g. /path/Button.tw → /path/Button.tss
    """
    base = os.path.splitext(component_path)[0]
    tss_path = base + ".tss"
    if os.path.exists(tss_path):
        return tss_path
    return None


def process_scoped_css(component_path: str, css_content: str) -> tuple:
    """
    Process CSS content for a component.
    Returns (scoped_css, scope_id).
    """
    component_name = os.path.splitext(os.path.basename(component_path))[0]
    scope_id = generate_scope_id(component_name)
    scoped = scope_css(css_content, scope_id)
    return scoped, scope_id


__all__ = [
    "generate_scope_id",
    "scope_css",
    "find_scoped_stylesheet",
    "process_scoped_css",
]
