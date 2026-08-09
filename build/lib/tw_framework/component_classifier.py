"""
Component Classifier for TW Framework.

Automatically classifies components as STATIC, SERVER, CLIENT, or SHARED
based on their content and imports.

Classification rules:
  STATIC  → No state, no events, no client imports, no browser APIs
  SERVER  → Uses server-only imports (database, filesystem, .twm)
  CLIENT  → Uses state, events, browser APIs, client imports, WebSocket
  SHARED  → Pure rendering logic, no side effects
"""

from __future__ import annotations

import re
from dataclasses import dataclass
from typing import Any, Dict, List, Optional, Set, Tuple

from .module_boundaries import CLIENT, SERVER, SHARED, ImportClassifier

# ── Classification constants ───────────────────────────────────────────────────

STATIC = "static"

# Patterns that indicate a component needs client-side JS
CLIENT_INDICATORS = [
    re.compile(r'\bstate\s*\{'),
    re.compile(r'\bon:\w+'),
    re.compile(r'\bbind:'),
    re.compile(r'\bshow:'),
    re.compile(r'\btw-ref\b'),
    re.compile(r'\btw-text\b'),
    re.compile(r'\btw-html\b'),
    re.compile(r'\btw-for\b'),
    re.compile(r'\btw-class\b'),
    re.compile(r'import\s+.*from\s+"tw/state"'),
    re.compile(r'import\s+.*from\s+"tw/router"'),
    re.compile(r'import\s+.*from\s+"tw/realtime"'),
    re.compile(r'import\s+.*from\s+"tw/form"'),
    re.compile(r'import\s+.*from\s+"tw/client'),
    re.compile(r'\bWebSocket\b'),
    re.compile(r'\bsocket\s*\('),
    re.compile(r'\buseAuth\s*\('),
    re.compile(r'\buseFetch\s*\('),
    re.compile(r'\bstore\s*\('),
    re.compile(r'\bLink\s*\{'),
]

# Patterns that indicate a component uses server-only APIs
SERVER_INDICATORS = [
    re.compile(r'\bload\s+@\w+\.twm\b'),
    re.compile(r'import\s+.*from\s+"tw/server"'),
    re.compile(r'import\s+.*from\s+"tw/database"'),
    re.compile(r'import\s+.*from\s+"tw/fs"'),
    re.compile(r'\baction\s*\('),
    re.compile(r'\bserver_action\s*\('),
]

# Explicit classification directive
EXPLICIT_CLIENT_RE = re.compile(r'\bclient\s+(true|1|yes)\b', re.IGNORECASE)
EXPLICIT_SERVER_RE = re.compile(r'\bserver\s+(true|1|yes)\b', re.IGNORECASE)
EXPLICIT_STATIC_RE = re.compile(r'\bstatic\s+(true|1|yes)\b', re.IGNORECASE)


@dataclass
class ComponentClassification:
    """Result of classifying a component."""
    name: str
    classification: str  # STATIC, SERVER, CLIENT, SHARED
    reasons: List[str]
    needs_client_js: bool
    needs_state: bool = False
    needs_router: bool = False
    needs_forms: bool = False
    needs_realtime: bool = False
    needs_auth_client: bool = False
    needs_fetch: bool = False
    client_imports: List[str] = None

    def __post_init__(self):
        if self.client_imports is None:
            self.client_imports = []


class ComponentClassifier:
    """Classify components as STATIC/SERVER/CLIENT/SHARED."""

    def __init__(self):
        self.import_classifier = ImportClassifier()

    def classify(
        self,
        name: str,
        source: str = "",
        imports: Optional[List] = None,
    ) -> ComponentClassification:
        """Classify a component by analyzing its source and imports."""
        reasons = []
        classification = STATIC
        needs_client_js = False
        needs_state = False
        needs_router = False
        needs_forms = False
        needs_realtime = False
        needs_auth_client = False
        needs_fetch = False
        client_imports = []

        # Check explicit classification first
        if EXPLICIT_STATIC_RE.search(source):
            return ComponentClassification(
                name=name, classification=STATIC,
                reasons=["explicitly marked as static"],
                needs_client_js=False,
            )
        if EXPLICIT_SERVER_RE.search(source):
            return ComponentClassification(
                name=name, classification=SERVER,
                reasons=["explicitly marked as server"],
                needs_client_js=False,
            )
        if EXPLICIT_CLIENT_RE.search(source):
            classification = CLIENT
            needs_client_js = True
            reasons.append("explicitly marked as client")

        # Check for client indicators
        for pattern in CLIENT_INDICATORS:
            match = pattern.search(source)
            if match:
                classification = CLIENT
                needs_client_js = True
                matched_text = match.group(0)
                reasons.append(f"uses client feature: {matched_text}")

                # Determine specific capabilities needed
                if "tw/state" in matched_text or "store" in matched_text or "state" in matched_text:
                    needs_state = True
                if "tw/router" in matched_text or "Link" in matched_text:
                    needs_router = True
                if "tw/form" in matched_text:
                    needs_forms = True
                if "tw/realtime" in matched_text or "socket" in matched_text or "WebSocket" in matched_text:
                    needs_realtime = True
                if "useAuth" in matched_text:
                    needs_auth_client = True
                if "useFetch" in matched_text:
                    needs_fetch = True

        # Check imports for client packages
        if imports:
            for imp in imports:
                boundary = self.import_classifier.classify_import(imp.path if hasattr(imp, 'path') else str(imp))
                if boundary == CLIENT:
                    classification = CLIENT
                    needs_client_js = True
                    client_imports.append(imp.path if hasattr(imp, 'path') else str(imp))
                    reasons.append(f"imports client package: {imp.path if hasattr(imp, 'path') else imp}")

                # Check for specific tw/* packages
                imp_path = imp.path if hasattr(imp, 'path') else str(imp)
                if imp_path == "tw/state":
                    needs_state = True
                elif imp_path == "tw/router":
                    needs_router = True
                elif imp_path == "tw/form":
                    needs_forms = True
                elif imp_path == "tw/realtime":
                    needs_realtime = True
                elif imp_path == "tw/auth":
                    needs_auth_client = True
                elif imp_path == "tw/fetch":
                    needs_fetch = True

        # Check for server indicators
        for pattern in SERVER_INDICATORS:
            if pattern.search(source):
                if classification != CLIENT:
                    classification = SERVER
                    reasons.append("uses server-only API")
                break

        # If no indicators matched, it's static
        if not reasons:
            reasons.append("no client or server indicators found")

        return ComponentClassification(
            name=name,
            classification=classification,
            reasons=reasons,
            needs_client_js=needs_client_js,
            needs_state=needs_state,
            needs_router=needs_router,
            needs_forms=needs_forms,
            needs_realtime=needs_realtime,
            needs_auth_client=needs_auth_client,
            needs_fetch=needs_fetch,
            client_imports=client_imports,
        )

    def classify_page(
        self,
        source: str,
        page_ast=None,
        imports: Optional[List] = None,
    ) -> ComponentClassification:
        """Classify an entire page to determine its capabilities."""
        return self.classify("__page__", source, imports)


__all__ = [
    "STATIC",
    "ComponentClassification",
    "ComponentClassifier",
]
