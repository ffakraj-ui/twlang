from __future__ import annotations

import re
from typing import Any, Dict, List, Tuple


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
#   export client function name(...) { ... }      (v0.8.1)
#   export client async function name(...) { ... } (v0.8.1)
#   export client fn name(...) { ... }             (v0.8.1)
_FUNC_HEADER_RE = re.compile(
    r"""
    (?P<prefix>\bexport\b\s+)?
    (?P<client>\bclient\b\s+)?
    (?P<async>\basync\b\s+)?
    (?P<kw>\bfunction\b|\bfn\b)\s+
    (?P<name>[A-Za-z_$][A-Za-z0-9_$]*)\s*
    (?P<params>\((?:[^()]|\([^()]*\))*\))?\s*
    \{
    """,
    re.VERBOSE,
)


class TWMParseError(Exception):
    pass


def _scan_matching_brace(source: str, open_brace_index: int) -> Any:
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
                i += 2 if i + 1 < len(source) else 1
                continue
            if (mode == "string_d" and ch == '"') or (mode == "string_s" and ch == "'"):
                mode = "code"
            i += 1
            continue

        if mode == "template":
            if ch == "\\":
                i += 2 if i + 1 < len(source) else 1
                continue
            if ch == "`":
                mode = "code"
            elif ch == "$" and i + 1 < len(source) and source[i + 1] == "{":
                mode = "code"
                depth += 1
                i += 2
                continue
            i += 1
            continue

        # mode == "code"
        if ch == "/" and i + 1 < len(source) and source[i + 1] not in ("/", "*"):
            prev_char = source[i - 1] if i > 0 else "\n"
            if prev_char in "(,=:[!&|?{;\n+-*%":
                j = i + 1
                in_class = False
                while j < len(source):
                    if source[j] == "\\":
                        j += 2
                        continue
                    if source[j] == "[":
                        in_class = True
                    elif source[j] == "]":
                        in_class = False
                    elif source[j] == "/" and not in_class:
                        j += 1
                        while j < len(source) and source[j].isalpha():
                            j += 1
                        break
                    elif source[j] == "\n":
                        break
                    j += 1
                i = j
                continue
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


_IMPORT_RE = re.compile(
    r'^\s*import\s+(?:.+?\s+from\s+)?["\']([^"\']+)["\']\s*;?\s*$',
    re.MULTILINE,
)


def parse_twm_functions(source: str) -> List[Dict[str, Any]]:
    """
    Parse a `.twm` module into function declarations + top-level imports.

    v0.8.1: Top-level ``import`` statements are now allowed so that npm
    packages (e.g. ``import dayjs from "dayjs"``) can be used inside
    server-side .twm modules.  Imports are returned alongside functions
    so the CJS compiler can hoist them to the top of the module.
    """
    src = str(source or "")
    functions: List[Dict[str, Any]] = []
    imports: List[str] = []

    consumed_spans: List[Tuple[int, int]] = []

    # ── Extract top-level import statements (v0.8.1) ────────────────────
    for m in _IMPORT_RE.finditer(src):
        imports.append(src[m.start():m.end()].strip())
        consumed_spans.append((m.start(), m.end()))

    # ── Extract function declarations ───────────────────────────────────
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

    return {"functions": functions, "imports": imports}


def compile_twm_module_to_js(source: str, *, module_id: str) -> Any:
    result = parse_twm_functions(source)
    funcs = result["functions"] if isinstance(result, dict) else result
    lines: List[str] = []
    lines.append(f"// TW module: {module_id}")
    for fn in funcs:
        name = fn["name"]
        params = fn["params"]
        body = fn["body"]
        async_prefix = "async " if fn.get("async") else ""
        lines.append(f"{async_prefix}function {name}{params}{{{body}\n}}")
        # FIX #441: Guard against window not existing (Node.js server-side)
        lines.append(f"if (typeof window !== 'undefined' && window.__twRegister) window.__twRegister('{_js_string(name)}', {name});")
        lines.append("")
    return "\n".join(lines)


def _convert_es_import_to_cjs(import_stmt: str) -> str:
    """
    Convert an ES import statement to CJS require.

    Examples:
      import dayjs from "dayjs"
        → const dayjs = require("dayjs");
      import { foo, bar } from "utils"
        → const { foo, bar } = require("utils");
      import * as ns from "pkg"
        → const ns = require("pkg");
      import "pkg"  (side-effect only)
        → require("pkg");
    """
    import_stmt = import_stmt.strip().rstrip(";")
    
    # import "pkg" (side-effect only)
    m = re.match(r'^import\s+["\']([^"\']+)["\']$', import_stmt)
    if m:
        return f'require("{m.group(1)}");'
    
    # import * as ns from "pkg"
    m = re.match(r'^import\s+\*\s+as\s+([A-Za-z_$][A-Za-z0-9_$]*)\s+from\s+["\']([^"\']+)["\']$', import_stmt)
    if m:
        return f'const {m.group(1)} = require("{m.group(2)}");'
    
    # import defaultExport from "pkg"
    m = re.match(r'^import\s+([A-Za-z_$][A-Za-z0-9_$]*)\s+from\s+["\']([^"\']+)["\']$', import_stmt)
    if m:
        return f'const {m.group(1)} = require("{m.group(2)}");'
    
    # import { a, b as c } from "pkg"
    m = re.match(r'^import\s+\{([^}]+)\}\s+from\s+["\']([^"\']+)["\']$', import_stmt)
    if m:
        named = m.group(1).strip()
        return f'const {{ {named} }} = require("{m.group(2)}");'
    
    # import defaultExport, { named } from "pkg"
    m = re.match(r'^import\s+([A-Za-z_$][A-Za-z0-9_$]*)\s*,\s*\{([^}]+)\}\s+from\s+["\']([^"\']+)["\']$', import_stmt)
    if m:
        default_name = m.group(1)
        named = m.group(2).strip()
        pkg = m.group(3)
        return f'const {default_name} = require("{pkg}");\nconst {{ {named} }} = require("{pkg}");'
    
        # FIX #108: Fallback — strip comments before extracting string
    cleaned = re.sub(r'//.*$', '', import_stmt).strip()
    cleaned = re.sub(r'/\*.*?\*/', '', cleaned, flags=re.DOTALL).strip()
    m = re.search(r'["\']([^"\']+)["\']', cleaned)
    if m:
        return f'require("{m.group(1)}");'

    return f"// Could not convert: {import_stmt}"


def compile_twm_module_to_cjs(source: str, *, module_id: str) -> Any:
    """
    Compile `.twm` into a CommonJS module for server-side execution (Node.js).

    v0.8.1: Top-level import statements are converted to CJS require()
    and hoisted to the top of the module, so npm packages work.

    Important:
    - `.twm` already forbids top-level statements (except imports), so
      generating a Node module is safe from accidental auto-execution.
    - This output does NOT use `window` / browser globals.
    """
    result = parse_twm_functions(source)
    funcs = result["functions"]
    imports = result.get("imports", [])
    
    lines: List[str] = []
    lines.append(f"// TW server module: {module_id} (v0.8.1)")
    lines.append("'use strict';")
    lines.append("")
    
    # Hoist imports as CJS require() statements (v0.8.1)
    for imp in imports:
        lines.append(_convert_es_import_to_cjs(imp))
    if imports:
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
    sources: List[Dict[str, Any]],
    *,
    page_source_path: str = "",
) -> Any:
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
        # FIX #448: Sanitize path to prevent comment injection / path escape
        _safe_path = page_source_path.replace("*/", "").replace("\n", " ").replace("\r", "")
        parts.append(f"  // Source page: {_safe_path}")
    parts.append("")

    for item in sources or []:
        if item.get("kind") == "file":
            path = item.get("path") or ""
            # FIX #110: Handle FileNotFoundError gracefully
            try:
                with open(path, "r", encoding="utf-8") as f:
                    src = f.read()
            except (FileNotFoundError, OSError) as e:
                parts.append(f"// ERROR: Could not read {path}: {e}")
                continue
            parts.append(compile_twm_module_to_js(src, module_id=path))
            parts.append("")
            continue
        if item.get("kind") == "inline":
            src = item.get("source") or ""
            # FIX #453: Use unique module_id for inline sources to avoid collision
            _inline_id = f"<inline-{hash(src) & 0xFFFF:04x}>"
            parts.append(compile_twm_module_to_js(src, module_id=_inline_id))
            parts.append("")
            continue
        # FIX #111: Log unknown kinds instead of silently skipping
        import logging as _logging
        _logging.getLogger("tw_framework").warning(
            "Unknown source kind %r in build_page_twm_bundle_js \u2014 skipped",
            item.get("kind")
        )

    parts.append("})();")
    return "\n".join(parts)


def _js_string(value: str) -> Any:
    # FIX #109: Also escape double quotes and newlines
    s = str(value)
    s = s.replace("\\", "\\\\")
    s = s.replace("'", "\\'")
    s = s.replace('"', '\\"')
    s = s.replace("\n", "\\n")
    s = s.replace("\r", "\\r")
    s = s.replace("\t", "\\t")
    return s


__all__ = [
    "TWMParseError",
    "build_page_twm_bundle_js",
    "compile_twm_module_to_cjs",
    "compile_twm_module_to_js",
    "parse_twm_functions",
]
