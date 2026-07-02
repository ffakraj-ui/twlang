from __future__ import annotations

import re
from typing import Dict, List, Optional, Tuple


_IDENT_RE = re.compile(r"^[A-Za-z_$][A-Za-z0-9_$]*$")

# Supports:
#   export async function name(...) { ... }
#   async function name(...) { ... }
#   export function name(...) { ... }
#   function name(...) { ... }
#   export async fn name(...) { ... }
#   async fn name(...) { ... }
#   export fn name(...) { ... }
#   fn name(...) { ... }
_FUNC_HEADER_RE = re.compile(
    r"""
    (?P<prefix>\bexport\b\s+)?(?P<async>\basync\b\s+)?(?P<kw>\bfunction\b|\bfn\b)\s+
    (?P<name>[A-Za-z_$][A-Za-z0-9_$]*)\s*
    (?P<params>\([^)]*\))?\s*
    \{
    """,
    re.VERBOSE,
)


class TWMParseError(Exception):
    pass


def _scan_matching_brace(source: str, open_brace_index: int) -> int:
    """
    Returns index of the matching closing brace `}` for the `{` at open_brace_index.
    Implements JS-like string/comment awareness so braces inside strings/comments
    don't affect nesting.
    """
    if open_brace_index < 0 or open_brace_index >= len(source) or source[open_brace_index] != "{":
        raise TWMParseError("Internal error: expected `{` at open brace index")

    i = open_brace_index + 1
    depth = 1
    mode = "code"  # code|string_d|string_s|template|line_comment|block_comment

    while i < len(source):
        ch = source[i]

        if mode == "line_comment":
            if ch == "\n":
                mode = "code"
            i += 1
            continue

        if mode == "block_comment":
            if ch == "*" and i + 1 < len(source) and source[i + 1] == "/":
                i += 2
                mode = "code"
                continue
            i += 1
            continue

        if mode in {"string_d", "string_s"}:
            if ch == "\\":
                i += 2
                continue
            if (mode == "string_d" and ch == '"') or (mode == "string_s" and ch == "'"):
                mode = "code"
            i += 1
            continue

        if mode == "template":
            if ch == "\\":
                i += 2
                continue
            if ch == "`":
                mode = "code"
            i += 1
            continue

        # mode == "code"
        if ch == "/" and i + 1 < len(source) and source[i + 1] == "/":
            mode = "line_comment"
            i += 2
            continue
        if ch == "/" and i + 1 < len(source) and source[i + 1] == "*":
            mode = "block_comment"
            i += 2
            continue
        if ch == '"':
            mode = "string_d"
            i += 1
            continue
        if ch == "'":
            mode = "string_s"
            i += 1
            continue
        if ch == "`":
            mode = "template"
            i += 1
            continue

        if ch == "{":
            depth += 1
            i += 1
            continue
        if ch == "}":
            depth -= 1
            if depth == 0:
                return i
            i += 1
            continue

        i += 1

    raise TWMParseError("Unterminated `{ ... }` block in `.twm` source")


def parse_twm_functions(source: str) -> List[Dict[str, str]]:
    """
    Minimal `.twm` surface:
    - `.twm` files are declarative: top-level code is NOT allowed.
    - Only function declarations are supported in the MVP.
    """
    src = str(source or "")
    functions: List[Dict[str, str]] = []

    consumed_spans: List[Tuple[int, int]] = []
    for match in _FUNC_HEADER_RE.finditer(src):
        name = match.group("name")
        params = match.group("params") or "()"
        if not _IDENT_RE.match(name):
            raise TWMParseError(f"Invalid function name: {name!r}")

        # Find the exact opening brace for this match.
        open_brace = src.find("{", match.start())
        close_brace = _scan_matching_brace(src, open_brace)
        body = src[open_brace + 1 : close_brace]

        functions.append(
            {
                "name": name,
                "params": params,
                "body": body,
                "async": bool(match.group("async")),
            }
        )
        consumed_spans.append((match.start(), close_brace + 1))

    # Enforce "no top-level execution": after removing function spans, remaining
    # source must be only whitespace/comments.
    scratch = list(src)
    for start, end in consumed_spans:
        for i in range(start, end):
            scratch[i] = " "
    remainder = "".join(scratch).strip()
    if remainder:
        # Allow top-level comments (line + block) and whitespace.
        # This is safe here because function bodies were already stripped out,
        # so this pass only affects truly top-level text.
        remainder = re.sub(r"//.*?$", "", remainder, flags=re.MULTILINE)
        remainder = re.sub(r"/\*.*?\*/", "", remainder, flags=re.DOTALL)
        remainder = remainder.strip()
    if remainder:
        raise TWMParseError(
            "Top-level statements are not allowed in `.twm`. "
            "Only `function`/`fn` declarations are supported so modules never auto-execute."
        )

    return functions


def compile_twm_module_to_js(source: str, *, module_id: str) -> str:
    funcs = parse_twm_functions(source)
    lines: List[str] = []
    lines.append(f"// TW module: {module_id}")
    for fn in funcs:
        name = fn["name"]
        params = fn["params"]
        body = fn["body"]
        async_prefix = "async " if fn.get("async") else ""
        lines.append(f"{async_prefix}function {name}{params}{{{body}\n}}")
        lines.append(f"window.__twRegister('{_js_string(name)}', {name});")
        lines.append("")
    return "\n".join(lines)


def compile_twm_module_to_cjs(source: str, *, module_id: str) -> str:
    """
    Compile `.twm` into a CommonJS module for server-side execution (Node.js).

    Important:
    - `.twm` already forbids top-level statements, so generating a Node module
      is safe from accidental auto-execution.
    - This output does NOT use `window` / browser globals.
    """
    funcs = parse_twm_functions(source)
    lines: List[str] = []
    lines.append(f"// TW server module: {module_id}")
    lines.append("'use strict';")
    lines.append("")
    for fn in funcs:
        name = fn["name"]
        params = fn["params"]
        body = fn["body"]
        async_prefix = "async " if fn.get("async") else ""
        lines.append(f"{async_prefix}function {name}{params}{{{body}\n}}")
        lines.append(f"exports.{name} = {name};")
        lines.append("")
    return "\n".join(lines)


def build_page_twm_bundle_js(
    sources: List[Dict[str, str]],
    *,
    page_source_path: str = "",
) -> str:
    """
    Produces a per-page JS bundle that:
    - creates the module registry
    - registers functions from loaded `.twm` files
    - registers functions from local `SCRIPT { ... }` blocks
    """
    parts: List[str] = []
    parts.append("(function(){")
    parts.append("  window.__twRegistry = window.__twRegistry || Object.create(null);")
    parts.append("  window.__twRegister = window.__twRegister || function(name, fn){")
    parts.append("    if (!name) return;")
    parts.append("    window.__twRegistry[name] = fn;")
    parts.append("  };")
    parts.append("  window.__twInvoke = window.__twInvoke || function(name, event){")
    parts.append("    try {")
    parts.append("      var fn = window.__twRegistry && window.__twRegistry[name];")
    parts.append("      if (typeof fn === 'function') return fn(event);")
    parts.append("      var g = window[name];")
    parts.append("      if (typeof g === 'function') return g(event);")
    parts.append("      console.warn('[tw] Missing handler:', name);")
    parts.append("    } catch (e) {")
    parts.append("      console.error('[tw] Handler error:', name, e);")
    parts.append("    }")
    parts.append("  };")
    if page_source_path:
        parts.append(f"  // Source page: {page_source_path}")
    parts.append("")

    for item in sources or []:
        if item.get("kind") == "file":
            path = item.get("path") or ""
            with open(path, "r", encoding="utf-8") as f:
                src = f.read()
            parts.append(compile_twm_module_to_js(src, module_id=path))
            parts.append("")
            continue
        if item.get("kind") == "inline":
            src = item.get("source") or ""
            parts.append(compile_twm_module_to_js(src, module_id="<inline SCRIPT>"))
            parts.append("")
            continue

    parts.append("})();")
    return "\n".join(parts)


def _js_string(value: str) -> str:
    return str(value).replace("\\", "\\\\").replace("'", "\\'")


__all__ = [
    "TWMParseError",
    "build_page_twm_bundle_js",
    "compile_twm_module_to_cjs",
    "compile_twm_module_to_js",
    "parse_twm_functions",
]
