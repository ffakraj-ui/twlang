"""
TW Lib System v0.8.0 — Next.js-style module system

Major upgrades from v0.7.x:
  1. import syntax: `import { getApps } from "@/lib/data"` instead of `let x = func()`
  2. Async/await support in .twm files
  3. TypeScript-style type annotations: `export function getData(slug: string): Promise<App>`
  4. Client-side lib support: `export client function formatPrice(n)` — ships to browser
  5. Hot reload: lib file change triggers page rebuild
  6. Named + default exports

Architecture:
  - .twm files are compiled to CJS modules (via twm_parser.py)
  - Server-side functions run in Node.js at build time
  - Client-side functions are extracted and shipped as JS to the browser
  - Import resolution: @/ prefix → project root, relative paths supported

Usage in .tw:
  import { getApps, getApp } from "@/lib/data"
  import formatPrice from "@/lib/utils"

  page {
    title "Apps"
    render static
  }

  let apps = getApps()
  let featured = getApp("calculator")

  body {
    each apps as app {
      div { class "card"
        h1 "{app.name}"
        p "Price: {formatPrice(app.price)}"
      }
    }
  }

Usage in .twm:
  // Server-side function (default — runs at build time)
  export async function getApps() {
    const data = await fetch("https://api.example.com/apps");
    return data.json();
  }

  // Client-side function (ships to browser)
  export client function formatPrice(n) {
    return "₹" + n.toFixed(2);
  }

  // With type annotations (stripped before execution)
  export function getApp(slug: string): Promise<App> {
    const apps = getApps();
    return apps.find(a => a.slug === slug);
  }
"""

from __future__ import annotations

import json
import os
import re
import subprocess
import tempfile
from typing import Any, Dict, List, Optional, Tuple


class LibExecutionError(Exception):
    def __init__(self, message, *, suggestion=""):
        super().__init__(message)
        self.message = message
        self.suggestion = suggestion


# ─── Import Statement Parser ──────────────────────────────────────────────────

# Matches:
#   import { a, b, c } from "@/lib/data"
#   import { a, b as c } from "./utils"
#   import defaultExport from "@/lib/utils"
#   import defaultExport, { named } from "@/lib/utils"
#   import * as ns from "@/lib/utils"
# Default-only import: import X from "path"
_DEFAULT_IMPORT_RE = re.compile(r'\bimport\s+(?P<default>[A-Za-z_$][A-Za-z0-9_$]*)\s+from\s*["\'](?P<module>[^"\']+)["\']')
_IMPORT_RE = re.compile(
    r'\bimport\s+'
    r'(?:(?P<default>[A-Za-z_$][A-Za-z0-9_$]*)\s*,\s*)?'  # optional default
    r'(?:\*\s+as\s+(?P<namespace>[A-Za-z_$][A-Za-z0-9_$]*)|'  # namespace import
    r'\{(?P<named>[^}]*)\})?\s*'  # named imports
    r'from\s+["\'](?P<module>[^"\']+)["\']',  # module path
)

# Parse named imports: "a, b as c, d" → [("a","a"), ("b","c"), ("d","d")]
_NAMED_IMPORT_RE = re.compile(
    r'(?P<original>[A-Za-z_$][A-Za-z0-9_$]*)'
    r'(?:\s+as\s+(?P<alias>[A-Za-z_$][A-Za-z0-9_$]*))?'
)


def parse_imports(source: str) -> List[Dict[str, Any]]:
    """
    Parse all import statements from .tw source.
    Supports: named, default, namespace, and default+named imports.
    """
    imports = []
    
    # Unified regex: handles all import forms
    # Form 1: import { a, b } from "path"
    # Form 2: import defaultExport from "path"
    # Form 3: import defaultExport, { a, b } from "path"
    # Form 4: import * as ns from "path"
    _unified = re.compile(
        r'\bimport\s+'
        r'(?:(?P<default>[A-Za-z_$][A-Za-z0-9_$]*)\s*,\s*)?'  # optional default before named
        r'(?:(?P<namespace>\*\s+as\s+[A-Za-z_$][A-Za-z0-9_$]*)|'  # namespace
        r'\{(?P<named>[^}]*)\})?'  # named imports
        r'\s*(?:(?P<default2>[A-Za-z_$][A-Za-z0-9_$]*)\s+)?'  # default-only (after named or alone)
        r'from\s*["\'](?P<module>[^"\']+)["\']'
    )
    
    for m in _unified.finditer(source):
        named_str = m.group('named')
        named = []
        if named_str:
            for nm in _NAMED_IMPORT_RE.finditer(named_str):
                named.append((nm.group('original'), nm.group('alias') or nm.group('original')))
        
        default = m.group('default') or m.group('default2')
        ns = m.group('namespace')
        if ns:
            ns = ns.replace('* as ', '').strip()
        
        imports.append({
            'default': default,
            'namespace': ns,
            'named': named,
            'module': m.group('module'),
            'resolved_path': None,
            'position': (m.start(), m.end()),
        })
    return imports

def resolve_module_path(module_spec: str, source_file: str, project_root: str) -> Optional[str]:
    """
    Resolve a module specifier to a file path.
    
    Supports:
      "@/lib/data" → <project_root>/lib/data.twm
      "./utils"    → <source_dir>/utils.twm
      "../shared"  → <source_dir>/../shared.twm
      "lib/data"   → <project_root>/lib/data.twm (no @ prefix)
    """
    if module_spec.startswith('@/'):
        rel = module_spec[2:]
        base = os.path.join(project_root, rel)
    elif module_spec.startswith('./') or module_spec.startswith('../'):
        source_dir = os.path.dirname(source_file)
        base = os.path.normpath(os.path.join(source_dir, module_spec))
    else:
        base = os.path.join(project_root, module_spec)
    
    # Try extensions
    for ext in ('.twm', '.js', '.mjs', '.cjs', '/index.twm', '/index.js'):
        candidate = base + ext if not ext.startswith('/') else base + ext
        if os.path.exists(candidate):
            return os.path.abspath(candidate)
    
    return None


def resolve_imports(imports: List[Dict], source_file: str, project_root: str) -> List[Dict]:
    """Resolve all import module paths."""
    for imp in imports:
        imp['resolved_path'] = resolve_module_path(imp['module'], source_file, project_root)
    return imports


# ─── Strip Import Statements ──────────────────────────────────────────────────

def strip_imports(source: str) -> str:
    """Remove import statements from .tw source, return cleaned source."""
    return _IMPORT_RE.sub('', source)


# ─── Extract Client-Side Functions ────────────────────────────────────────────

# Matches: export client function name(...) { ... }
_CLIENT_FUNC_RE = re.compile(
    r'export\s+client\s+(?:async\s+)?(?:function|fn)\s+(\w+)\s*\([^)]*\)\s*\{',
)


def extract_client_functions(twm_source: str) -> List[Dict[str, str]]:
    """
    Extract client-side functions from .twm source.
    These are functions marked with `export client`.
    
    Returns list of:
        {
            "name": "formatPrice",
            "body": "function formatPrice(n) { return ... }",
            "is_async": False,
        }
    """
    from .twm_parser import _scan_matching_brace
    
    client_fns = []
    
    # Pattern: export client [async] function|fn name(params) { body }
    pattern = re.compile(
        r'export\s+client\s+(?P<async>async\s+)?(?P<kw>function|fn)\s+'
        r'(?P<name>[A-Za-z_$][A-Za-z0-9_$]*)\s*'
        r'(?P<params>\([^)]*\))?\s*\{',
        re.VERBOSE,
    )
    
    for m in pattern.finditer(twm_source):
        name = m.group('name')
        is_async = bool(m.group('async'))
        kw = 'function' if m.group('kw') == 'function' else 'function'
        params = m.group('params') or '()'
        
        # Find the closing brace
        brace_idx = twm_source.find('{', m.end() - 1)
        if brace_idx < 0:
            continue
        try:
            close_idx = _scan_matching_brace(twm_source, brace_idx)
        except Exception:
            continue
        
        body = twm_source[brace_idx + 1:close_idx]
        
        # Strip type annotations from params
        params_clean = strip_type_annotations(params)
        
        js_fn = f"function {name}{params_clean} {{\n{body}\n}}"
        
        client_fns.append({
            'name': name,
            'body': js_fn,
            'is_async': is_async,
        })
    
    return client_fns


def strip_type_annotations(code: str) -> str:
    """
    Strip TypeScript-style type annotations from JS code.
    
    Examples:
      (slug: string) → (slug)
      (a: number, b: number) → (a, b)
      function foo(x: string): Promise<App> { → function foo(x) {
      let x: number = 5 → let x = 5
    """
    # Strip return type annotations: ): Type {
    code = re.sub(r'\)\s*:\s*[A-Za-z_$][A-Za-z0-9_$<>\[\]|\s&]*\s*\{', ') {', code)
    
    # Strip parameter type annotations: (name: type → (name
    def _strip_param_types(m):
        params = m.group(1)
        # Split by comma, strip type after colon
        parts = params.split(',')
        cleaned = []
        for part in parts:
            part = part.strip()
            if ':' in part and not part.startswith('{'):
                colon_idx = part.index(':')
                # Make sure the colon isn't inside a string or object
                before = part[:colon_idx].strip()
                if re.match(r'^[A-Za-z_$][A-Za-z0-9_$]*$', before):
                    cleaned.append(before)
                else:
                    cleaned.append(part)
            else:
                cleaned.append(part)
        return '(' + ', '.join(cleaned) + ')'
    
    # Find function params and strip types
    code = re.sub(r'\(([^)]*)\)', _strip_param_types, code)
    
    # Strip variable type annotations: let x: type = → let x =
    code = re.sub(r'\b(let|const|var)\s+(\w+)\s*:\s*[A-Za-z_$][A-Za-z0-9_$<>\[\]|\s&]*\s*=', r'\1 \2 =', code)
    
    return code


# ─── Compile .twm with Import Support ─────────────────────────────────────────

def compile_twm_with_imports(
    twm_source: str,
    file_path: str,
    project_root: str,
) -> Dict[str, Any]:
    """
    Compile a .twm file, resolving imports from other .twm files.
    
    Returns:
        {
            "server_functions": {"name": "compiled_js_body", ...},
            "client_functions": [{"name": ..., "body": ...}, ...],
            "imports": [...],
        }
    """
    from .twm_parser import parse_twm_functions, compile_twm_module_to_cjs
    
    # Parse functions from the source
    funcs = parse_twm_functions(twm_source)
    
    # Extract client functions
    client_fns = extract_client_functions(twm_source)
    
    # Get server functions (non-client)
    client_names = {f['name'] for f in client_fns}
    server_funcs = {f['name']: f for f in funcs if f['name'] not in client_names}
    
    # Compile to CJS for server execution
    compiled_path = None
    try:
        compiled = compile_twm_module_to_cjs(twm_source, file_path)
        if compiled:
            # Write to temp file for Node.js execution
            fd, compiled_path = tempfile.mkstemp(suffix='.js', prefix='tw_lib_')
            with os.fdopen(fd, 'w') as f:
                f.write(compiled)
    except Exception:
        pass
    
    return {
        'server_functions': {name: f.get('body', '') for name, f in server_funcs.items()},
        'client_functions': client_fns,
        'compiled_path': compiled_path,
    }


# ─── Execute Server Function via Node.js ──────────────────────────────────────

_NODE_BRIDGE_SCRIPT = r"""// TW lib function executor (build-time) — v0.8.0
"use strict";
const path = require("path");
const fs = require("fs");

function main() {
  const compiledPath = process.argv[2];
  const fnName = process.argv[3];
  const argsJson = process.argv[4] || "[]";
  let args;
  try { args = JSON.parse(argsJson); } catch (e) { args = []; }
  
  // Support import-based module loading
  const moduleDir = process.argv[5] || "";
  if (moduleDir) {
    // Create a require that resolves from the module's directory
    const Module = require('module');
    const origResolve = Module._resolveFilename;
    Module._resolveFilename = function(request, parent) {
      // Resolve @/ prefix
      if (request.startsWith('@/')) {
        const rel = request.slice(2);
        for (const ext of ['.twm', '.js', '.mjs', '.cjs', '/index.twm', '/index.js']) {
          const candidate = path.join(moduleDir, rel + ext);
          if (fs.existsSync(candidate)) return candidate;
        }
      }
      return origResolve.apply(this, arguments);
    };
  }
  
  const mod = require(path.resolve(compiledPath));
  const fn = mod[fnName];
  if (typeof fn !== "function") {
    process.stderr.write("Function '" + fnName + "' not found. Available: " + Object.keys(mod).join(", ") + "\n");
    process.exit(3);
  }
  Promise.resolve()
    .then(function () { return fn.apply(null, args); })
    .then(function (result) {
      try { process.stdout.write(JSON.stringify(result)); }
      catch (e) { process.stdout.write(JSON.stringify(String(result))); }
    })
    .catch(function (err) {
      process.stderr.write("Error: " + (err && err.stack ? err.stack : String(err)) + "\n");
      process.exit(4);
    });
}
main();
"""


def _find_node():
    """Find Node.js binary."""
    for candidate in ("node", "nodejs"):
        try:
            result = subprocess.run(
                [candidate, "--version"],
                capture_output=True, text=True, timeout=5
            )
            if result.returncode == 0:
                return candidate
        except (FileNotFoundError, subprocess.TimeoutExpired):
            pass
    return None


def _execute_compiled(
    compiled_path: str,
    fn_name: str,
    args: list,
    project_root: str = "",
    timeout: int = 30,
) -> Any:
    """Execute a server-side lib function via Node.js."""
    node_bin = _find_node()
    if not node_bin:
        raise LibExecutionError(
            "Node.js not found. Install Node.js to use lib functions.",
            suggestion="Install Node.js: https://nodejs.org/"
        )
    
    # Write bridge script
    fd, bridge_path = tempfile.mkstemp(suffix='.js', prefix='tw_bridge_')
    try:
        with os.fdopen(fd, 'w') as f:
            f.write(_NODE_BRIDGE_SCRIPT)
        
        args_json = json.dumps(args)
        
        result = subprocess.run(
            [node_bin, bridge_path, compiled_path, fn_name, args_json, project_root],
            capture_output=True, text=True, timeout=timeout
        )
        
        if result.returncode == 0:
            try:
                return json.loads(result.stdout.strip())
            except json.JSONDecodeError:
                return result.stdout.strip()
        else:
            stderr = result.stderr.strip()
            raise LibExecutionError(
                f"Lib function '{fn_name}' failed: {stderr}",
                suggestion="Check your .twm file for syntax errors"
            )
    except subprocess.TimeoutExpired:
        raise LibExecutionError(
            f"Lib function '{fn_name}' timed out after {timeout}s",
            suggestion="Make sure async functions resolve properly"
        )
    finally:
        try:
            os.unlink(bridge_path)
        except OSError:
            pass


# ─── Client-side Lib JS Generation ─────────────────────────────────────────────

def build_client_lib_js(client_functions: List[Dict]) -> str:
    """
    Generate JS that contains all client-side lib functions.
    This is injected into the page's <script> tag.
    """
    if not client_functions:
        return ""
    
    parts = ["// TW Client Lib Functions (v0.8.0)"]
    for fn in client_functions:
        parts.append(fn['body'])
    
    return "\n".join(parts)


# ─── Import Resolution for .tw Pages ───────────────────────────────────────────

def process_page_imports(
    source: str,
    source_file: str,
    project_root: str,
) -> Dict[str, Any]:
    """
    Process all imports in a .tw page.
    
    Returns:
        {
            "imports": [...],
            "clean_source": source without import lines,
            "server_bindings": {"var_name": ("fn_name", "args"), ...},
            "client_functions": [...],
            "compiled_modules": {"path": "compiled_js_path", ...},
        }
    """
    imports = parse_imports(source)
    imports = resolve_imports(imports, source_file, project_root)
    
    clean_source = strip_imports(source)
    
    # Collect all client functions from all imported modules
    all_client_fns = []
    compiled_modules = {}
    
    for imp in imports:
        if not imp['resolved_path']:
            continue
        
        if imp['resolved_path'] in compiled_modules:
            continue
        
        try:
            with open(imp['resolved_path']) as f:
                twm_src = f.read()
            
            compiled = compile_twm_with_imports(
                twm_src, imp['resolved_path'], project_root
            )
            
            compiled_modules[imp['resolved_path']] = compiled.get('compiled_path', '')
            
            all_client_fns.extend(compiled['client_functions'])
        except Exception:
            pass
    
    return {
        'imports': imports,
        'clean_source': clean_source,
        'client_functions': all_client_fns,
        'compiled_modules': compiled_modules,
    }


# ─── Function Call Detection (for build-time execution) ───────────────────────

_FUNC_CALL_RE = re.compile(
    r'^(?P<name>[A-Za-z_$][A-Za-z0-9_$]*)\s*\((?P<args>.*)\)\s*$',
    re.DOTALL,
)


def is_function_call(expr):
    """Check if an expression is a function call."""
    if not isinstance(expr, str):
        return None
    stripped = expr.strip()
    if not stripped:
        return None
    if stripped[0] in "\"'{[" or stripped in ("true", "false", "null", "none"):
        return None
    m = _FUNC_CALL_RE.match(stripped)
    if not m:
        return None
    return {"name": m.group("name"), "raw_args": m.group("args").strip()}


def _parse_args(raw_args):
    """Parse function call arguments."""
    raw = raw_args.strip()
    if not raw:
        return []
    try:
        return json.loads("[" + raw + "]")
    except json.JSONDecodeError:
        return [raw]


# ─── Hot Reload Support ────────────────────────────────────────────────────────

def get_lib_dependencies(source: str, source_file: str, project_root: str) -> List[str]:
    """Get all .twm file paths that a .tw page depends on."""
    imports = parse_imports(source)
    imports = resolve_imports(imports, source_file, project_root)
    return [imp['resolved_path'] for imp in imports if imp['resolved_path']]


# ─── Metadata API ─────────────────────────────────────────────────────────────

def extract_generate_metadata(source: str) -> Optional[Dict]:
    """
    Extract generateMetadata function from .tw source.
    
    Syntax:
        metadata {
            title "My Page"
            description "Page description"
            og-image "/images/og.png"
        }
    
    Or dynamic:
        generateMetadata {
            let data = getPageData()
            return {
                title data.title
                description data.description
            }
        }
    """
    # Static metadata block
    static_re = re.compile(r'\bmetadata\s*\{([^}]*)\}', re.DOTALL)
    m = static_re.search(source)
    if m:
        meta = {}
        for line in m.group(1).strip().split('\n'):
            line = line.strip()
            if not line:
                continue
            parts = line.split(None, 1)
            if len(parts) == 2:
                key, val = parts
                val = val.strip().strip('"').strip("'")
                meta[key] = val
        return {'type': 'static', 'data': meta}
    
    # Dynamic generateMetadata
    dyn_re = re.compile(r'\bgenerateMetadata\s*\{([^}]*)\}', re.DOTALL)
    m = dyn_re.search(source)
    if m:
        return {'type': 'dynamic', 'body': m.group(1).strip()}
    
    return None


# ─── ISR (Incremental Static Regeneration) ────────────────────────────────────

def extract_isr_config(source: str) -> Optional[Dict]:
    """
    Extract ISR configuration from .tw source.
    
    Syntax:
        revalidate 60    ← revalidate every 60 seconds
    
    Or in page block:
        page {
            revalidate 60
        }
    """
    # In page block
    page_re = re.compile(r'\brevalidate\s+(\d+)\s*', re.DOTALL)
    m = page_re.search(source)
    if m:
        seconds = int(m.group(1))
        if seconds > 0:
            return {'enabled': True, 'seconds': seconds}
    
    return None


# ─── Backward Compatibility ───────────────────────────────────────────────────

def execute_lib_function(twm_source, function_name, raw_args, *, module_id="", timeout=30):
    """
    Backward-compatible API for v0.7.x callers.
    
    Old signature: execute_lib_function(twm_source, fn_name, raw_args, *, module_id, timeout)
    
    This wrapper accepts the OLD signature: it compiles twm_source to a temp CJS file,
    then calls _execute_compiled which runs it via Node.js.
    """
    from .twm_parser import compile_twm_module_to_cjs
    
    try:
        cjs_code = compile_twm_module_to_cjs(twm_source, module_id=module_id or "<lib:" + function_name + ">")
    except Exception as exc:
        raise LibExecutionError(
            "Failed to compile lib module `" + module_id + "`: " + str(exc),
            suggestion="Check the .twm file for syntax errors."
        ) from exc

    fd_mod, mod_path = tempfile.mkstemp(suffix=".cjs", prefix="tw_lib_mod_")
    try:
        with os.fdopen(fd_mod, "w") as f:
            f.write(cjs_code)
    except Exception:
        os.close(fd_mod)
        raise

    try:
        args = _parse_args(raw_args)
        return _execute_compiled(mod_path, function_name, args, timeout=timeout)
    finally:
        try:
            os.unlink(mod_path)
        except OSError:
            pass

