"""
JS/NPM Ecosystem Interop for TW Framework.

Allows TW pages and components to import npm packages and ES modules.
Handles client-side bundling, server-only package isolation, and dynamic imports.

Error codes: TW3000-TW3999
"""

from __future__ import annotations

import hashlib
import json
import logging
import os
import re
from dataclasses import dataclass, field
from typing import Any, Dict, List, Optional, Set, Tuple

from .module_boundaries import CLIENT, SERVER, SHARED, ImportClassifier, ImportInfo

logger = logging.getLogger(__name__)


@dataclass
class NPMPackage:
    """Resolved npm package info."""
    name: str
    version: str = ""
    entry_point: str = ""
    format: str = "esm"  # esm, cjs, umd
    boundary: str = CLIENT
    dependencies: List[str] = field(default_factory=list)
    browser_entry: str = ""
    module_entry: str = ""
    main_entry: str = ""


class JSInterop:
    """Handles npm package imports and ES module bundling."""

    # Packages that are always server-only
    SERVER_ONLY_NPM = {
        "express", "fastify", "mongoose", "pg", "mysql2",
        "redis", "nodemailer", "bcrypt", "jsonwebtoken",
        "passport", "connect-mongo", "dotenv",
    }

    # Packages that are browser-safe by default
    CLIENT_SAFE_NPM = {
        "chart.js", "d3", "three", "phaser",
        "@tiptap/core", "@tiptap/react",
        "socket.io-client", "ws",
        "alpinejs", "htmx.org",
        "gsap", "framer-motion",
        "react", "react-dom", "vue", "svelte",
        "sortablejs", "dragula",
        "quill", "codemirror", "monaco-editor",
        "animejs", "lottie-web",
        "dayjs", "date-fns", "luxon",
        "zod", "yup", "ajv",
        "lodash", "ramda",
    }

    def __init__(self, project_root: str = ""):
        self.project_root = project_root
        self.classifier = ImportClassifier()
        self._package_cache: Dict[str, Optional[NPMPackage]] = {}

    def resolve_npm_package(self, name: str) -> Optional[NPMPackage]:
        """Resolve an npm package to its entry point."""
        if name in self._package_cache:
            return self._package_cache[name]

        # Check node_modules
        if self.project_root:
            pkg_json_path = os.path.join(
                self.project_root, "node_modules", name, "package.json"
            )
            if os.path.exists(pkg_json_path):
                pkg = self._read_package_json(pkg_json_path, name)
                self._package_cache[name] = pkg
                return pkg

        # Check if it's a known client-safe package
        if name in self.CLIENT_SAFE_NPM:
            pkg = NPMPackage(
                name=name,
                boundary=CLIENT,
                format="esm",
            )
            self._package_cache[name] = pkg
            return pkg

        # Check if it's a known server-only package
        if name in self.SERVER_ONLY_NPM:
            pkg = NPMPackage(
                name=name,
                boundary=SERVER,
                format="cjs",
            )
            self._package_cache[name] = pkg
            return pkg

        # Unknown package — default to client
        pkg = NPMPackage(name=name, boundary=CLIENT)
        self._package_cache[name] = pkg
        return pkg

    def _read_package_json(self, path: str, name: str) -> NPMPackage:
        """Read package.json and extract entry points."""
        try:
            with open(path) as f:
                data = json.load(f)
        except (json.JSONDecodeError, OSError):
            return NPMPackage(name=name)

        pkg = NPMPackage(
            name=name,
            version=data.get("version", ""),
        )

        # Determine entry point priority: browser > module > main
        browser = data.get("browser")
        if isinstance(browser, str):
            pkg.browser_entry = browser
            pkg.entry_point = browser
            pkg.format = "esm"
        elif isinstance(browser, dict):
            # browser field can be a map
            pkg.browser_entry = browser.get(".", data.get("module", data.get("main", "")))
            pkg.entry_point = pkg.browser_entry
            pkg.format = "esm"

        if not pkg.entry_point:
            module_entry = data.get("module")
            if module_entry:
                pkg.module_entry = module_entry
                pkg.entry_point = module_entry
                pkg.format = "esm"

        if not pkg.entry_point:
            main_entry = data.get("main", "index.js")
            pkg.main_entry = main_entry
            pkg.entry_point = main_entry
            pkg.format = "cjs"

        # Check exports field (modern packages)
        exports = data.get("exports")
        if isinstance(exports, dict):
            browser_export = exports.get("browser") or exports.get(".")
            if isinstance(browser_export, dict):
                import_val = browser_export.get("import")
                if import_val:
                    pkg.entry_point = import_val
                    pkg.format = "esm"
            elif isinstance(browser_export, str):
                pkg.entry_point = browser_export
                pkg.format = "esm"

        # Dependencies
        pkg.dependencies = list(data.get("dependencies", {}).keys())

        # Classify boundary
        if name in self.SERVER_ONLY_NPM:
            pkg.boundary = SERVER
        elif name in self.CLIENT_SAFE_NPM:
            pkg.boundary = CLIENT
        else:
            pkg.boundary = CLIENT  # default for npm

        return pkg

    def bundle_client_imports(
        self,
        imports: List[ImportInfo],
        output_dir: str,
    ) -> Dict[str, str]:
        """
        Bundle client-side npm imports into per-package chunks.
        Returns {package_name: chunk_url}.
        """
        chunk_map = {}
        chunk_dir = os.path.join(output_dir, "_tw", "chunks", "npm")
        os.makedirs(chunk_dir, exist_ok=True)

        for imp in imports:
            if imp.boundary != CLIENT:
                continue

            pkg = self.resolve_npm_package(imp.path)
            if not pkg:
                continue

            if pkg.name in chunk_map:
                continue

            # Try to read the actual package file
            js_content = self._read_package_entry(pkg)
            if not js_content:
                # Generate a stub that loads from CDN or node_modules
                js_content = self._generate_npm_loader(pkg)

            digest = hashlib.sha256(
                js_content.encode("utf-8")
            ).hexdigest()[:12]
            filename = f"{pkg.name.replace('/', '_').replace('@', '')}.{digest}.js"
            chunk_path = os.path.join(chunk_dir, filename)

            if not os.path.exists(chunk_path):
                with open(chunk_path, "w", encoding="utf-8") as f:
                    f.write(js_content)

            chunk_map[pkg.name] = f"/_tw/chunks/npm/{filename}"

        return chunk_map

    def _read_package_entry(self, pkg: NPMPackage) -> Optional[str]:
        """Read the actual JS file from node_modules."""
        if not self.project_root or not pkg.entry_point:
            return None

        entry_path = os.path.join(
            self.project_root, "node_modules", pkg.name, pkg.entry_point
        )
        if os.path.exists(entry_path):
            try:
                with open(entry_path, encoding="utf-8") as f:
                    return f.read()
            except OSError:
                return None
        return None

    def _generate_npm_loader(self, pkg: NPMPackage) -> str:
        """Generate a loader stub for an npm package."""
        return f"""// TW npm loader: {pkg.name}
// This is a generated loader. For production, install the package:
//   npm install {pkg.name}
(function() {{
  'use strict';
  var _module = {{exports: {{}}}};
  // Placeholder — replace with actual package code
  if (typeof window !== 'undefined') {{
    window.__tw = window.__tw || {{}};
    window.__tw.npm = window.__tw.npm || {{}};
    window.__tw.npm['{pkg.name}'] = _module.exports;
  }}
}})();
"""

    def detect_dynamic_imports(self, source: str) -> List[Dict[str, Any]]:
        """Find import() calls for lazy loading."""
        results = []
        # Match: import("package") or import('package')
        pattern = re.compile(
            r'import\s*\(\s*["\']([^"\']+)["\']\s*\)'
        )
        for match in pattern.finditer(source):
            line = source[:match.start()].count("\n") + 1
            results.append({
                "path": match.group(1),
                "line": line,
                "dynamic": True,
            })
        return results

    def validate_server_isolation(
        self,
        imports: List[ImportInfo],
    ) -> List[Dict[str, str]]:
        """Ensure server-only packages don't leak into client bundles."""
        errors = []
        for imp in imports:
            if imp.context == CLIENT:
                pkg = self.resolve_npm_package(imp.path)
                if pkg and pkg.boundary == SERVER:
                    errors.append({
                        "code": "TW3000",
                        "message": (
                            f'Server-only npm package "{imp.path}" '
                            f'cannot be imported in a client component.'
                        ),
                        "file": imp.file,
                        "line": str(imp.line),
                        "suggestion": (
                            "Move this import to a .twm server module "
                            "or server action."
                        ),
                    })
        return errors


__all__ = ["NPMPackage", "JSInterop"]
