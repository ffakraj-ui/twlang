"""
Module Boundary System for TW Framework.

Classifies every import as SERVER, CLIENT, or SHARED and enforces
that server-only code never enters client bundles.

Boundaries:
  SERVER  — .twm files, lib/ modules, database, filesystem, secrets
  CLIENT  — npm packages, browser APIs, DOM, WebSocket clients
  SHARED  — types, validation, pure utilities

Error codes: TW2000-TW2999
"""

from __future__ import annotations

import os
import re
from dataclasses import dataclass, field
from typing import Any, Dict, List, Optional, Set, Tuple

# ── Boundary constants ─────────────────────────────────────────────────────────

SERVER = "server"
CLIENT = "client"
SHARED = "shared"

# ── Known tw/* package boundaries ──────────────────────────────────────────────

TW_PACKAGE_BOUNDARIES: Dict[str, str] = {
    "tw/image": SHARED,       # renders HTML, no client JS needed
    "tw/state": CLIENT,       # reactive state runtime
    "tw/router": CLIENT,      # client-side routing
    "tw/form": CLIENT,         # form runtime
    "tw/realtime": CLIENT,    # websocket client
    "tw/auth": SHARED,         # server authority, client session info
    "tw/fetch": SHARED,        # can be server or client
    "tw/font": SHARED,         # font loading
    "tw/metadata": SHARED,    # meta tags
    "tw/server": SERVER,       # explicit server-only
    "tw/client": CLIENT,       # explicit client-only
}

# Imports that are always server-only
SERVER_ONLY_PATTERNS = {
    "fs", "path", "os", "child_process", "crypto",
    "tw/server", "tw/database", "tw/fs",
}

# File extensions that are always server-side
SERVER_EXTENSIONS = {".twm"}

# Indicators that a module uses server-only APIs
SERVER_API_PATTERNS = [
    re.compile(r'\brequire\s*\(\s*["\']fs["\']'),
    re.compile(r'\brequire\s*\(\s*["\']child_process["\']'),
    re.compile(r'\bprocess\.env\b'),
    re.compile(r'\brequire\s*\(\s*["\']node:'),
    re.compile(r'\bimport\s+.*from\s+["\']node:'),
    re.compile(r'\b__dirname\b'),
    re.compile(r'\b__filename\b'),
]

# Indicators that a module uses client-only APIs
CLIENT_API_PATTERNS = [
    re.compile(r'\bdocument\b'),
    re.compile(r'\bwindow\b'),
    re.compile(r'\bwindow\.'),
    re.compile(r'\blocalStorage\b'),
    re.compile(r'\bsessionStorage\b'),
    re.compile(r'\bnavigator\b'),
    re.compile(r'\bWebSocket\b'),
    re.compile(r'\bfetch\s*\('),
    re.compile(r'\baddEventListener\b'),
    re.compile(r'\bquerySelector\b'),
    re.compile(r'\bgetElementById\b'),
    re.compile(r'\bcreateElement\b'),
]


@dataclass
class ImportInfo:
    """Information about a single import statement."""
    path: str               # import path, e.g. "tw/state" or "chart.js"
    line: int = 0            # line number in source
    col: int = 0            # column number
    file: str = ""          # source file
    context: str = ""       # "client" or "server" or "shared" — the consuming context
    boundary: str = ""     # classified boundary


@dataclass
class BoundaryViolation:
    """A module boundary violation."""
    code: str
    message: str
    file: str = ""
    line: int = 0
    col: int = 0
    suggestion: str = ""


class ImportClassifier:
    """Classify imports as SERVER, CLIENT, or SHARED."""

    def classify_import(self, import_path: str) -> str:
        """Classify a single import path."""
        # Explicit server-only
        if import_path.startswith("tw/server") or import_path in SERVER_ONLY_PATTERNS:
            return SERVER

        # Explicit client-only
        if import_path.startswith("tw/client"):
            return CLIENT

        # Known tw/* packages
        if import_path in TW_PACKAGE_BOUNDARIES:
            return TW_PACKAGE_BOUNDARIES[import_path]

        # Other tw/* packages default to shared
        if import_path.startswith("tw/"):
            return SHARED

        # .twm files are always server
        if import_path.endswith(".twm"):
            return SERVER

        # @lib/ imports are server
        if import_path.startswith("@lib/"):
            return SERVER

        # npm packages (contain "/" or start with "@") are client by default
        # Also treat names with dots (like "chart.js") as npm packages
        if import_path.startswith("@") or "/" in import_path:
            return CLIENT
        if "." in import_path and not import_path.startswith("."):
            # Looks like an npm package name (e.g. "chart.js", "socket.io")
            return CLIENT

        # Bare names (TW components) are shared by default
        return SHARED

    def classify_module_source(self, source: str) -> str:
        """Classify a module by analyzing its source code."""
        has_server = any(p.search(source) for p in SERVER_API_PATTERNS)
        has_client = any(p.search(source) for p in CLIENT_API_PATTERNS)

        if has_server and has_client:
            # Module uses both — could be shared, but flag it
            return SHARED
        if has_server:
            return SERVER
        if has_client:
            return CLIENT
        return SHARED

    def validate_imports(self, imports: List[ImportInfo]) -> List[BoundaryViolation]:
        """Check for invalid cross-boundary imports."""
        violations = []
        for imp in imports:
            imp.boundary = self.classify_import(imp.path)
            if imp.context == CLIENT and imp.boundary == SERVER:
                violations.append(BoundaryViolation(
                    code="TW2000",
                    message=(
                        f'Client component cannot import server-only module: "{imp.path}"'
                    ),
                    file=imp.file,
                    line=imp.line,
                    col=imp.col,
                    suggestion=(
                        "Move this import to a server-only context (e.g. a .twm module), "
                        "use a server action to access server data, or import a shared "
                        "alternative instead."
                    ),
                ))
            elif imp.context == SERVER and imp.boundary == CLIENT:
                violations.append(BoundaryViolation(
                    code="TW2001",
                    message=(
                        f'Server module cannot import client-only module: "{imp.path}"'
                    ),
                    file=imp.file,
                    line=imp.line,
                    col=imp.col,
                    suggestion=(
                        "Client-only libraries (DOM, browser APIs) cannot run on the server. "
                        "Move this usage to a client component."
                    ),
                ))
        return violations

    def get_client_imports(self, imports: List[ImportInfo]) -> List[ImportInfo]:
        """Return only imports that should be included in client bundles."""
        result = []
        for imp in imports:
            boundary = imp.boundary or self.classify_import(imp.path)
            if boundary in (CLIENT, SHARED) and imp.context != SERVER:
                new_imp = ImportInfo(
                    path=imp.path, line=imp.line, col=imp.col,
                    file=imp.file, context=imp.context, boundary=boundary,
                )
                result.append(new_imp)
        return result

    def get_server_imports(self, imports: List[ImportInfo]) -> List[ImportInfo]:
        """Return only imports that are server-side."""
        return [
            imp for imp in imports
            if imp.boundary == SERVER
        ]

    def scan_source_imports(self, source: str, file_path: str = "") -> List[ImportInfo]:
        """Scan source code for import statements and classify them."""
        imports = []
        # Match: import "path"  or  import { x } from "path"  or  import Name from "path"
        pattern = re.compile(
            r'^\s*import\s+(?:\{[^}]+\}\s+from\s+|\w+\s+from\s+)?["\']([^"\']+)["\']',
            re.MULTILINE,
        )
        for match in pattern.finditer(source):
            line_num = source[:match.start()].count("\n") + 1
            imports.append(ImportInfo(
                path=match.group(1),
                line=line_num,
                col=match.start() - source.rfind("\n", 0, match.start()) - 1,
                file=file_path,
            ))
        return imports


# ── All known tw/* packages (for resolver integration) ───────────────────────

ALL_TW_PACKAGES: Set[str] = {
    "tw/image",
    "tw/state",
    "tw/router",
    "tw/form",
    "tw/fetch",
    "tw/realtime",
    "tw/auth",
    "tw/font",
    "tw/metadata",
    "tw/server",
    "tw/client",
}

# Aliases (component name → tw/* package)
TW_PACKAGE_ALIASES: Dict[str, str] = {
    "Image": "tw/image",
    "Link": "tw/router",
    "Form": "tw/form",
    "Field": "tw/form",
    "store": "tw/state",
    "socket": "tw/realtime",
    "useAuth": "tw/auth",
    "useFetch": "tw/fetch",
}


def is_tw_package(path: str) -> bool:
    """Check if an import path is a known tw/* package."""
    return path in ALL_TW_PACKAGES or path.startswith("tw/")


def get_package_boundary(path: str) -> str:
    """Get the boundary classification for a tw/* package."""
    return TW_PACKAGE_BOUNDARIES.get(path, SHARED)


__all__ = [
    "SERVER", "CLIENT", "SHARED",
    "TW_PACKAGE_BOUNDARIES", "ALL_TW_PACKAGES", "TW_PACKAGE_ALIASES",
    "ImportInfo", "BoundaryViolation", "ImportClassifier",
    "is_tw_package", "get_package_boundary",
]
