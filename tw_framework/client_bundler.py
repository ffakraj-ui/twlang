"""
TW Client-Side Bundler (v0.8.1)

A real client-side module bundler for TW Framework. Unlike the previous
approach (which simply copied a package's entry file), this module:

1. Resolves transitive dependencies — if `package-a` depends on `package-b`,
   both get bundled together.
2. Converts CommonJS modules to browser-compatible ESM wrappers.
3. Generates proper import maps for browser-native ESM resolution.
4. Handles both ESM and CJS package formats from node_modules.

How it works:
  - Reads each package's package.json to determine its format (ESM/CJS)
  - For ESM packages: the entry file is already browser-compatible
  - For CJS packages: wraps the module in a function scope that provides
    `module`, `exports`, `require` (mapped to pre-bundled deps)
  - Resolves the package's own dependencies recursively
  - Outputs a single self-contained JS file per top-level import
  - Generates an import map mapping bare specifiers to chunk URLs

Limitations (honest):
  - This is NOT a full webpack/turbopack replacement. It handles the
    common cases (simple CJS/ESM packages with resolved deps) but may
    fail on packages that use advanced bundler features (code splitting,
    dynamic requires, worker imports, CSS-in-JS, etc.).
  - Packages that do `require()` with dynamic/variable arguments cannot
    be statically resolved.
  - Packages that rely on Node.js built-in modules (fs, path, etc.)
    will get a stub that throws in the browser.
  - For complex packages, users should consider pre-bundling with
    esbuild/rollup and importing the pre-built bundle.
"""

from __future__ import annotations

import hashlib
import json
import os
import re
from dataclasses import dataclass, field
from typing import Any, Dict, List, Optional, Set, Tuple

from .module_boundaries import CLIENT, SERVER, SHARED


# ─── Data Structures ──────────────────────────────────────────────────────────

@dataclass
class BundledModule:
    """A single module that has been bundled for the browser."""
    name: str          # package name (e.g. "dayjs", "react")
    version: str = ""
    source: str = ""   # transformed JS source (ESM-compatible)
    format: str = "esm"  # "esm" or "cjs"
    dependencies: List[str] = field(default_factory=list)
    entry_point: str = ""
    is_builtin: bool = False  # Node.js built-in module


@dataclass
class BundleResult:
    """Result of bundling a set of imports."""
    chunks: Dict[str, str] = field(default_factory=dict)  # package_name -> chunk_url
    import_map: Dict[str, str] = field(default_factory=dict)  # bare specifier -> URL
    modules: Dict[str, BundledModule] = field(default_factory=dict)  # all bundled modules
    warnings: List[str] = field(default_factory=list)
    errors: List[str] = field(default_factory=list)


# ─── CJS → ESM Conversion ────────────────────────────────────────────────────

# Patterns for require() calls in CJS code
_REQUIRE_RE = re.compile(
    r'\brequire\s*\(\s*["\']([^"\']+)["\']\s*\)'
)

# Patterns for module.exports and exports.x = ...
_MODULE_EXPORTS_RE = re.compile(r'\bmodule\.exports\s*=')
_EXPORTS_ASSIGN_RE = re.compile(r'\bexports\.(\w+)\s*=')

# Node.js built-in modules that need browser stubs
NODE_BUILTINS = {
    "fs", "path", "os", "http", "https", "crypto", "url", "util",
    "stream", "events", "buffer", "child_process", "net", "tls",
    "zlib", "querystring", "assert", "dns", "cluster", "worker_threads",
    "process", "perf_hooks", "v8", "vm", "tty", "dgram",
}

# Browser-safe polyfills for common Node built-ins
BUILTIN_STUBS = {
    "process": """// Node.js process polyfill (TW browser stub)
var process = {
  env: {},
  argv: [],
  platform: "browser",
  version: "",
  nextTick: function(fn) { setTimeout(fn, 0); },
  cwd: function() { return "/"; },
  exit: function(code) { if (typeof window !== "undefined") window.close(); },
  on: function() {},
  stdout: { write: function() {} },
  stderr: { write: function() {} },
};
""",
    "buffer": """// Node.js Buffer polyfill (TW browser stub)
var Buffer = {
  isBuffer: function(x) { return x instanceof Uint8Array; },
  from: function(arr) { return new Uint8Array(arr); },
  alloc: function(size) { return new Uint8Array(size); },
  concat: function(list) {
    var total = list.reduce(function(a, b) { return a + b.length; }, 0);
    var result = new Uint8Array(total);
    var offset = 0;
    for (var i = 0; i < list.length; i++) {
      result.set(list[i], offset);
      offset += list[i].length;
    }
    return result;
  },
};
""",
    "stream": """// Node.js Stream polyfill (TW browser stub)
var Stream = function() {};
Stream.prototype.pipe = function() { return this; };
Stream.prototype.on = function() { return this; };
""",
    "events": """// Node.js EventEmitter polyfill (TW browser stub)
var EventEmitter = function() {
  this._events = {};
};
EventEmitter.prototype.on = function(event, fn) {
  if (!this._events[event]) this._events[event] = [];
  this._events[event].push(fn);
  return this;
};
EventEmitter.prototype.off = function(event, fn) {
  if (this._events[event]) {
    var idx = this._events[event].indexOf(fn);
    if (idx > -1) this._events[event].splice(idx, 1);
  }
  return this;
};
EventEmitter.prototype.emit = function(event) {
  var args = Array.prototype.slice.call(arguments, 1);
  var handlers = this._events[event] || [];
  handlers.forEach(function(fn) { try { fn.apply(null, args); } catch(e) {} });
  return this;
};
""",
    "path": """// Node.js path polyfill (TW browser stub)
var path = {
  join: function() { return Array.prototype.join.call(arguments, "/").replace(/\\/+/g, "/"); },
  resolve: function() { return Array.prototype.join.call(arguments, "/"); },
  dirname: function(p) { return p.split("/").slice(0, -1).join("/") || "."; },
  basename: function(p) { return p.split("/").pop(); },
  extname: function(p) { var i = p.lastIndexOf("."); return i < 0 ? "" : p.slice(i); },
  sep: "/",
};
""",
    "os": """// Node.js os polyfill (TW browser stub)
var os = {
  platform: function() { return "browser"; },
  hostname: function() { return ""; },
  tmpdir: function() { return "/tmp"; },
  cpus: function() { return []; },
  totalmem: function() { return 0; },
  freemem: function() { return 0; },
};
""",
    "crypto": """// Node.js crypto polyfill (TW browser stub)
var crypto = {
  createHash: function(algo) {
    return {
      update: function() { return this; },
      digest: function() { return ""; },
    };
  },
  randomBytes: function(n) { return new Uint8Array(n); },
};
""",
    "url": """// Node.js url polyfill (TW browser stub)
var url = {
  parse: function(u) { return new URL(u); },
  resolve: function(from, to) { return new URL(to, from).href; },
};
""",
    "util": """// Node.js util polyfill (TW browser stub)
var util = {
  inspect: function(obj) { return JSON.stringify(obj); },
  inherits: function() {},
  promisify: function(fn) { return function() { return new Promise(function(resolve, reject) { fn.apply(null, [].concat(Array.prototype.slice.call(arguments)).concat(function(err, val) { if (err) reject(err); else resolve(val); })); }); }; },
};
""",
    "http": """// Node.js http polyfill — use fetch in browser
var http = { get: function(url, cb) { fetch(url).then(function(r) { return r.text(); }).then(function(body) { cb(null, { statusCode: 200 }, body); }).catch(function(e) { cb(e); }); } };
""",
    "https": """// Node.js https polyfill — use fetch in browser
var https = http;
""",
    "fs": """// Node.js fs polyfill — not available in browser
var fs = {
  readFileSync: function() { throw new Error("fs is not available in the browser. Use fetch() instead."); },
  writeFileSync: function() { throw new Error("fs is not available in the browser."); },
  existsSync: function() { return false; },
  readdirSync: function() { throw new Error("fs is not available in the browser."); },
};
""",
}


def get_builtin_stub(name: str) -> Optional[str]:
    """Get a browser-safe stub for a Node.js built-in module."""
    # Handle node: prefix
    if name.startswith("node:"):
        name = name[5:]
    return BUILTIN_STUBS.get(name)


def is_node_builtin(name: str) -> bool:
    """Check if a module name is a Node.js built-in."""
    if name.startswith("node:"):
        name = name[5:]
    return name in NODE_BUILTINS


def convert_cjs_to_browser(cjs_source: str, module_name: str) -> str:
    """
    Convert a CommonJS module to a browser-compatible IIFE wrapper.

    This wraps the CJS code in a function scope that provides:
    - module: { exports: {} }
    - exports: (reference to module.exports)
    - require: a function that resolves to pre-bundled dependencies

    The result is self-contained and can be loaded via <script> tag.
    """
    # Find all require() calls and collect dependency names
    deps = set()
    for m in _REQUIRE_RE.finditer(cjs_source):
        dep = m.group(1)
        if not dep.startswith(".") and not dep.startswith("/"):
            deps.add(dep)

    # Build the wrapper
    lines = []
    lines.append(f"// TW Client Bundle: {module_name} (CJS → browser wrapper)")
    lines.append("(function() {")
    lines.append("  'use strict';")
    lines.append(f"  // Bundled dependencies: {', '.join(sorted(deps)) if deps else 'none'}")
    lines.append("")

    # Provide built-in stubs for Node.js modules
    stubs_added = set()
    for dep in sorted(deps):
        if is_node_builtin(dep):
            stub = get_builtin_stub(dep)
            if stub and dep not in stubs_added:
                stub_name = dep.replace("node:", "")
                # Sanitize: replace var declarations with window-scoped
                stub_clean = stub.replace(f"var {stub_name}", f"var __tw_stub_{stub_name}")
                lines.append(f"  // Stub for Node.js built-in: {dep}")
                lines.append(stub_clean)
                stubs_added.add(dep)

    # Create module/exports context
    lines.append("  var module = { exports: {} };")
    lines.append("  var exports = module.exports;")
    lines.append("")

    # Create require function that maps to bundled deps
    lines.append("  // require() shim — resolves to bundled modules")
    lines.append("  var __tw_require = function(name) {")

    # Add stub lookups for builtins
    for dep in sorted(deps):
        if is_node_builtin(dep):
            stub_name = dep.replace("node:", "")
            lines.append(f"    if (name === '{dep}' || name === '{stub_name}') return __tw_stub_{stub_name};")

    # Add lookups for npm packages (resolved by import map at runtime)
    for dep in sorted(deps):
        if not is_node_builtin(dep):
            lines.append(f"    if (name === '{dep}') return (window.__tw_npm && window.__tw_npm['{dep}']) || {{}};")

    lines.append("    throw new Error('Cannot require: ' + name);")
    lines.append("  };")
    lines.append("")

    # Inline the CJS source
    lines.append("  // --- Original module source ---")
    # Replace require() calls with __tw_require()
    transformed_source = _REQUIRE_RE.sub('__tw_require("\\1")', cjs_source)
    lines.append(transformed_source)
    lines.append("")

    # Export the module
    lines.append(f"  // Export {module_name}")
    lines.append("  if (typeof window !== 'undefined') {")
    lines.append("    window.__tw_npm = window.__tw_npm || {};")
    lines.append(f"    window.__tw_npm['{module_name}'] = module.exports;")
    lines.append("  }")
    lines.append("})();")

    return "\n".join(lines)


def convert_esm_to_browser(esm_source: str, module_name: str) -> str:
    """
    Convert an ESM module to a browser-compatible format.
    ESM modules are mostly already browser-compatible — we just need to
    ensure exports are properly registered.
    """
    lines = []
    lines.append(f"// TW Client Bundle: {module_name} (ESM)")
    lines.append("(function() {")
    lines.append("  'use strict';")
    lines.append("  var __tw_exports = {};")
    lines.append("")

    # For ESM, we keep the source mostly as-is but capture exports
    # Replace `export default X` with `__tw_exports.default = X`
    transformed = esm_source
    transformed = re.sub(
        r'\bexport\s+default\s+',
        '__tw_exports.default = ',
        transformed,
    )
    # Replace `export function name` with `function name; __tw_exports.name = name`
    transformed = re.sub(
        r'\bexport\s+function\s+(\w+)',
        r'function \1; __tw_exports.\1 = \1; function \1',
        transformed,
    )
    # Replace `export const/let/var name` with the declaration + export
    transformed = re.sub(
        r'\bexport\s+(const|let|var)\s+(\w+)',
        r'\1 \2; __tw_exports.\2 = \2; var _dummy',
        transformed,
    )
    # Replace `export { a, b, c }` with individual exports
    def _export_block(m):
        names = [n.strip().split(" as ")[0] for n in m.group(1).split(",")]
        return "; ".join(f"__tw_exports.{n} = {n}" for n in names) + ";"

    transformed = re.sub(r'\bexport\s*\{([^}]+)\}\s*;?', _export_block, transformed)

    lines.append(transformed)
    lines.append("")
    lines.append("  if (typeof window !== 'undefined') {")
    lines.append("    window.__tw_npm = window.__tw_npm || {};")
    lines.append(f"    window.__tw_npm['{module_name}'] = __tw_exports;")
    lines.append("  }")
    lines.append("})();")

    return "\n".join(lines)


# ─── Package Resolution ──────────────────────────────────────────────────────

def read_package_json(project_root: str, pkg_name: str) -> Optional[Dict[str, Any]]:
    """Read a package's package.json from node_modules."""
    pkg_path = os.path.join(project_root, "node_modules", pkg_name, "package.json")
    if not os.path.exists(pkg_path):
        return None
    try:
        with open(pkg_path, "r", encoding="utf-8") as f:
            return json.load(f)
    except (json.JSONDecodeError, OSError):
        return None


def get_package_entry_point(pkg_data: Dict[str, Any], project_root: str, pkg_name: str) -> Tuple[str, str]:
    """
    Get the entry point and format for a package.
    Returns (entry_file_path, format) where format is "esm" or "cjs".
    """
    # Priority: browser > module > main
    browser = pkg_data.get("browser")
    module_field = pkg_data.get("module")
    main_field = pkg_data.get("main", "index.js")

    # Check exports field (modern packages)
    exports = pkg_data.get("exports")
    if isinstance(exports, dict):
        dot_export = exports.get(".") or exports.get(".")
        if isinstance(dot_export, dict):
            # Prefer browser/import over require
            browser_export = dot_export.get("browser")
            import_export = dot_export.get("import")
            require_export = dot_export.get("require")
            if isinstance(browser_export, str):
                entry = browser_export
                fmt = "esm"
            elif isinstance(import_export, str):
                entry = import_export
                fmt = "esm"
            elif isinstance(require_export, str):
                entry = require_export
                fmt = "cjs"
            else:
                entry = main_field
                fmt = "cjs"
        elif isinstance(dot_export, str):
            entry = dot_export
            fmt = "esm"
        else:
            entry = main_field
            fmt = "cjs"
    elif isinstance(browser, str):
        entry = browser
        fmt = "esm"
    elif isinstance(browser, dict) and "." in browser:
        entry = browser["."]
        fmt = "esm"
    elif module_field:
        entry = module_field
        fmt = "esm"
    else:
        entry = main_field
        fmt = "cjs"

    entry_path = os.path.join(project_root, "node_modules", pkg_name, entry)
    return entry_path, fmt


def get_package_dependencies(pkg_data: Dict[str, Any]) -> List[str]:
    """Get a package's runtime dependencies (not devDependencies)."""
    deps = pkg_data.get("dependencies", {})
    if isinstance(deps, dict):
        return list(deps.keys())
    return []


def read_entry_file(entry_path: str) -> Optional[str]:
    """Read a JS entry file."""
    if not os.path.exists(entry_path):
        return None
    try:
        with open(entry_path, "r", encoding="utf-8") as f:
            return f.read()
    except OSError:
        return None




# ─── esbuild Detection (v0.8.1) ───────────────────────────────────────────────

_esbuild_cached = None  # None = not checked, True/False = checked
_esbuild_auto_install_attempted = False

def _esbuild_available() -> bool:
    """Check if esbuild is available (cached)."""
    global _esbuild_cached
    if _esbuild_cached is None:
        try:
            from .esbuild_integration import is_esbuild_available
            _esbuild_cached = is_esbuild_available()
        except Exception:
            _esbuild_cached = False
    return _esbuild_cached

def _try_auto_install_esbuild() -> bool:
    """
    Auto-install esbuild if not present (v0.8.37).
    
    When a complex npm package needs bundling and esbuild is not available,
    this function automatically runs `npm install esbuild` in the project root.
    This way the user doesn't have to manually install esbuild — it just works.
    
    Returns True if esbuild is available after the install attempt.
    """
    global _esbuild_cached, _esbuild_auto_install_attempted
    
    if _esbuild_available():
        return True
    
    if _esbuild_auto_install_attempted:
        return False  # Already tried, don't retry
    
    _esbuild_auto_install_attempted = True
    
    try:
        from .common import log
        from .npm_manager import find_package_manager
        
        # Find project root
        import os
        project_root = os.environ.get("TW_PROJECT_ROOT", os.getcwd())
        
        pm_name, pm_bin = find_package_manager(project_root)
        if not pm_bin:
            return False
        
        log("📦 esbuild not found — auto-installing for better bundling...", level="info")
        
        import subprocess
        if pm_name == "pnpm":
            cmd = [pm_bin, "add", "-D", "esbuild"]
        elif pm_name == "yarn":
            cmd = [pm_bin, "add", "--dev", "esbuild"]
        elif pm_name == "bun":
            cmd = [pm_bin, "add", "-d", "esbuild"]
        else:
            cmd = [pm_bin, "install", "--save-dev", "esbuild"]
        
        result = subprocess.run(
            cmd,
            capture_output=True,
            text=True,
            cwd=project_root,
            timeout=120,
        )
        
        if result.returncode == 0:
            log("  ✔ esbuild auto-installed successfully", level="info")
            # Reset cache and re-check
            _esbuild_cached = None
            # Also reset esbuild_integration cache
            try:
                from .esbuild_integration import _esbuild_path_cache
                import tw_framework.esbuild_integration as esi
                esi._esbuild_path = None
                esi._esbuild_version = None
            except Exception:
                pass
            return _esbuild_available()
        else:
            log(f"  ⚠️  esbuild auto-install failed: {result.stderr[:200]}", level="warning")
            log("  Falling back to IIFE bundler. You can manually install with: tw install --save-dev esbuild", level="warning")
            return False
    except Exception as e:
        log(f"  ⚠️  esbuild auto-install error: {e}", level="warning")
        return False

# ─── Main Bundler Class ───────────────────────────────────────────────────────

class ClientBundler:
    """
    Bundles npm packages for client-side (browser) use.

    Handles:
    - ESM packages (pass-through with export wrapping)
    - CJS packages (wrapping in IIFE with require shim)
    - Transitive dependency resolution
    - Node.js built-in stubs
    - Import map generation
    """

    def __init__(self, project_root: str = "", output_dir: str = ""):
        self.project_root = project_root
        self.output_dir = output_dir
        self._cache: Dict[str, Optional[BundledModule]] = {}

    def bundle_package(
        self,
        pkg_name: str,
        visited: Optional[Set[str]] = None,
        max_depth: int = 10,
        use_esbuild: Optional[bool] = None,
    ) -> Optional[BundledModule]:
        """
        Bundle a single npm package and its transitive dependencies.

        v0.8.1: Tries esbuild first (real bundling with tree-shaking,
        CJS→ESM, minification, transitive deps). Falls back to IIFE
        wrapper if esbuild is not available.

        Args:
            pkg_name: Package name (e.g. "react", "dayjs")
            visited: Set of already-visited packages (cycle detection)
            max_depth: Maximum recursion depth for dependency resolution
            use_esbuild: Force esbuild (True) or IIFE fallback (False).
                        None = auto-detect.

        Returns a BundledModule or None if the package cannot be bundled.
        """
        if visited is None:
            visited = set()

        # Cycle detection
        if pkg_name in visited:
            return self._cache.get(pkg_name)
        visited.add(pkg_name)

        # Cache check
        if pkg_name in self._cache:
            return self._cache[pkg_name]

        # Check if it's a Node.js built-in
        if is_node_builtin(pkg_name):
            stub_source = get_builtin_stub(pkg_name) or ""
            mod = BundledModule(
                name=pkg_name,
                source=stub_source,
                format="esm",
                is_builtin=True,
            )
            self._cache[pkg_name] = mod
            return mod

        # Check if package is installed
        if not self.project_root:
            self._cache[pkg_name] = None
            return None

        pkg_data = read_package_json(self.project_root, pkg_name)
        if not pkg_data:
            self._cache[pkg_name] = None
            return None

        # Get entry point and format
        entry_path, fmt = get_package_entry_point(pkg_data, self.project_root, pkg_name)
        source = read_entry_file(entry_path)

        if not source:
            # Try index.js fallback
            entry_path = os.path.join(
                self.project_root, "node_modules", pkg_name, "index.js"
            )
            source = read_entry_file(entry_path)
            if not source:
                self._cache[pkg_name] = None
                return None
            fmt = "cjs"

        # ── v0.8.1: Try esbuild first (real bundling) ────────────────────
        if use_esbuild is None:
            use_esbuild = _esbuild_available()

        if use_esbuild and self.output_dir:
            esbuild_source = self._bundle_with_esbuild(pkg_name, entry_path)
            if esbuild_source:
                dep_names = get_package_dependencies(pkg_data)
                mod = BundledModule(
                    name=pkg_name,
                    version=pkg_data.get("version", ""),
                    source=esbuild_source,
                    format="esbuild",
                    dependencies=dep_names,
                    entry_point=entry_path,
                )
                self._cache[pkg_name] = mod
                return mod
            # If esbuild fails, fall through to IIFE wrapper

        # ── Fallback: IIFE wrapper approach ──────────────────────────────
        # Resolve transitive dependencies
        dep_names = get_package_dependencies(pkg_data)
        bundled_deps = []

        if max_depth > 0:
            for dep_name in dep_names:
                # Skip peer dependencies and optional dependencies
                if dep_name.startswith("@types/"):
                    continue
                dep_mod = self.bundle_package(dep_name, visited, max_depth - 1, use_esbuild=use_esbuild)
                if dep_mod:
                    bundled_deps.append(dep_name)

        # Convert to browser-compatible format
        if fmt == "esm":
            browser_source = convert_esm_to_browser(source, pkg_name)
        else:
            browser_source = convert_cjs_to_browser(source, pkg_name)

        mod = BundledModule(
            name=pkg_name,
            version=pkg_data.get("version", ""),
            source=browser_source,
            format=fmt,
            dependencies=bundled_deps,
            entry_point=entry_path,
        )
        self._cache[pkg_name] = mod
        return mod

    def _bundle_with_esbuild(self, pkg_name: str, entry_path: str) -> Optional[str]:
        """
        Bundle a package using esbuild (v0.8.1).

        This produces a real browser-compatible bundle with:
        - CJS → ESM conversion
        - Tree shaking (dead code elimination)
        - Transitive dependency resolution
        - Minification
        - Node.js built-in polyfills (via define)

        Returns the bundled JS source, or None on failure.
        """
        from .esbuild_integration import find_esbuild, bundle_with_esbuild
        import tempfile

        cmd = find_esbuild()
        if not cmd:
            return None

        # Write to a temp file, then read it back
        fd, tmp_output = tempfile.mkstemp(suffix=".js", prefix="tw_esbuild_")
        os.close(fd)

        try:
            success, message = bundle_with_esbuild(
                entry_point=entry_path,
                output_path=tmp_output,
                project_root=self.project_root,
                minify=False,  # Don't minify here — chunk writer handles naming
                format="iife",
                global_name=pkg_name.replace("-", "_").replace("/", "_").replace("@", ""),
                define={"process.env.NODE_ENV": '"production"'},
                sourcemap=False,
            )

            if not success:
                return None

            with open(tmp_output, "r", encoding="utf-8") as f:
                return f.read()
        except Exception:
            return None
        finally:
            try:
                os.unlink(tmp_output)
            except OSError:
                pass

    def bundle_imports(
        self,
        imports: List[Any],
        output_dir: Optional[str] = None,
    ) -> BundleResult:
        """
        Bundle a list of imports for the browser.

        v0.8.1 fixes:
        - Transitive deps are now written to disk AND added to import map
          (previously they were only in memory — caused silent browser failures).
        - esbuild fallback now generates a warning so developers know.
        - Script tag order uses topological sort (dependencies first).

        Args:
            imports: List of ImportInfo objects or strings
            output_dir: Output directory for chunk files

        Returns a BundleResult with chunk URLs and import map.
        """
        out_dir = output_dir or self.output_dir
        result = BundleResult()
        visited: Set[str] = set()

        # ── Detect esbuild availability — auto-install if missing (v0.8.37) ──
        esbuild_available = _esbuild_available()
        if not esbuild_available:
            # Try auto-installing esbuild (v0.8.37)
            esbuild_available = _try_auto_install_esbuild()
        
        if not esbuild_available:
            result.warnings.append(
                "esbuild is not installed — using fallback IIFE bundler. "
                "Complex npm packages may not bundle correctly. "
                "Install with: tw install --save-dev esbuild"
            )

        # Collect package names to bundle
        pkg_names = []
        for imp in imports:
            if hasattr(imp, "path"):
                path = imp.path
                boundary = getattr(imp, "boundary", "")
                if boundary == SERVER:
                    continue
            else:
                path = str(imp)

            if path.startswith("tw/") or path.startswith("@/") or path.startswith("./") or path.startswith("../"):
                continue

            if path not in pkg_names:
                pkg_names.append(path)

        # Bundle each top-level package
        for pkg_name in pkg_names:
            if is_node_builtin(pkg_name):
                stub = get_builtin_stub(pkg_name)
                if stub:
                    result.modules[pkg_name] = BundledModule(
                        name=pkg_name, source=stub, format="esm", is_builtin=True
                    )
                continue

            mod = self.bundle_package(pkg_name, visited)
            if mod is None:
                result.warnings.append(
                    f"Package '{pkg_name}' not found in node_modules. "
                    f"Run: tw install {pkg_name}"
                )
                continue

            result.modules[pkg_name] = mod

            # Check if esbuild was tried but failed (Fix #3)
            if esbuild_available and mod.format != "esbuild" and self.output_dir:
                result.warnings.append(
                    f"esbuild bundling failed for '{pkg_name}' — "
                    f"fell back to IIFE wrapper. Bundle may be incomplete."
                )

            # Write chunk file for top-level package
            chunk_url = self._write_chunk(mod, out_dir, result)
            if chunk_url:
                result.chunks[pkg_name] = chunk_url
                result.import_map[pkg_name] = chunk_url
                if not pkg_name.startswith("@"):
                    result.import_map[f"{pkg_name}/"] = chunk_url

        # ── Fix #2: Write ALL transitive dependency chunks to disk ────────
        # Previously deps were only in self._cache (memory) — never written
        # to disk, never in import_map. Browser would silently fail.
        #
        # Now: iterate over self._cache to find ALL bundled modules that
        # haven't been chunked yet, and write them.
        for dep_name, dep_mod in self._cache.items():
            if dep_mod is None:
                continue
            if dep_mod.is_builtin:
                # Built-in stubs are inlined into the packages that use them
                continue
            if dep_name in result.chunks:
                # Already chunked as a top-level package
                continue
            if not dep_mod.source:
                continue

            # This is a transitive dependency — write it to disk (Fix #2)
            chunk_url = self._write_chunk(dep_mod, out_dir, result)
            if chunk_url:
                result.chunks[dep_name] = chunk_url
                result.import_map[dep_name] = chunk_url
                if not dep_name.startswith("@"):
                    result.import_map[f"{dep_name}/"] = chunk_url
                # Also register in result.modules so render_chunk_script_tags
                # can see the dependency graph
                if dep_name not in result.modules:
                    result.modules[dep_name] = dep_mod

        return result

    def _write_chunk(
        self,
        mod: BundledModule,
        out_dir: str,
        result: BundleResult,
    ) -> Optional[str]:
        """Write a module's source to a chunk file and return its URL."""
        if not mod.source:
            return None

        # Compute content hash for cache-busting filename
        digest = hashlib.sha256(mod.source.encode("utf-8")).hexdigest()[:12]
        safe_name = mod.name.replace("/", "_").replace("@", "").replace(".", "-")
        filename = f"{safe_name}.{digest}.js"

        if not out_dir:
            # In-memory: return virtual URL
            return f"/_tw/chunks/npm/{filename}"

        chunk_dir = os.path.join(out_dir, "_tw", "chunks", "npm")
        os.makedirs(chunk_dir, exist_ok=True)
        chunk_path = os.path.join(chunk_dir, filename)

        # Prepend dependency stubs if any
        full_source = ""
        for dep in mod.dependencies:
            dep_mod = result.modules.get(dep)
            if dep_mod and dep_mod.is_builtin and dep_mod.source:
                full_source += dep_mod.source + "\n\n"

        full_source += mod.source

        if not os.path.exists(chunk_path):
            try:
                with open(chunk_path, "w", encoding="utf-8") as f:
                    f.write(full_source)
            except OSError as e:
                result.errors.append(f"Failed to write chunk for {mod.name}: {e}")
                return None

        return f"/_tw/chunks/npm/{filename}"

    def render_import_map_script(self, import_map: Dict[str, str]) -> str:
        """Render an import map as a <script type='importmap'> tag."""
        if not import_map:
            return ""
        map_json = json.dumps({"imports": import_map}, indent=2)
        return '<script type="importmap">\n' + map_json + '\n</script>'

    def render_chunk_script_tags(self, chunks: Dict[str, str]) -> str:
        """
        Render <script> tags for loading bundled chunks in dependency order.

        v0.8.1 fix: Uses topological sort so that if package A depends on
        package B, B's <script> tag comes first.  Previously this used
        alphabetical sort which could load a package before its deps.
        """
        if not chunks:
            return ""

        # Build dependency graph from result.modules
        # Each module's .dependencies lists what it needs loaded first
        ordered_names = self._topological_sort(chunks)

        tags = []
        for pkg_name in ordered_names:
            url = chunks.get(pkg_name)
            if url:
                tags.append(f'<script src="{url}"></script>')
        return "\n".join(tags)

    def _topological_sort(self, chunks: Dict[str, str]) -> List[str]:
        """
        Sort package names so that dependencies come before dependents.

        Uses Kahn's algorithm.  If a dependency cycle is detected, falls
        back to alphabetical order for the remaining packages.
        """
        # Collect all chunked package names
        all_names = set(chunks.keys())

        # Build adjacency: for each package, which other chunked packages
        # does it depend on?
        deps_map: Dict[str, Set[str]] = {}
        for name in all_names:
            mod = self._cache.get(name)
            if mod and mod.dependencies:
                # Only count deps that are also in our chunk set
                deps_map[name] = set(mod.dependencies) & all_names
            else:
                deps_map[name] = set()

        # Kahn's algorithm
        result: List[str] = []
        # Start with packages that have no dependencies
        ready = sorted([n for n in all_names if not deps_map[n]])
        remaining = set(all_names) - set(ready)

        while ready:
            name = ready.pop(0)
            result.append(name)
            # Remove this package from everyone's dependency lists
            for other in list(remaining):
                if name in deps_map.get(other, set()):
                    deps_map[other].discard(name)
                    if not deps_map[other]:
                        ready.append(other)
                        remaining.discard(other)

        # Any remaining packages have cycles — add alphabetically
        if remaining:
            result.extend(sorted(remaining))

        return result


__all__ = [
    "ClientBundler",
    "BundledModule",
    "BundleResult",
    "convert_cjs_to_browser",
    "convert_esm_to_browser",
    "is_node_builtin",
    "get_builtin_stub",
    "NODE_BUILTINS",
    "BUILTIN_STUBS",
]
