from typing import Any, Dict, Generator, List, Optional

import os
import re
import json
import ast
import copy
import shutil
import hashlib
import difflib
import argparse
import logging
import contextlib
import tempfile
import threading

# TW Image system (first-party tw/ components)
from .tw_image.component import BUILTIN_IMAGE_COMPONENTS

# Full-stack architecture imports (v0.6.0)
from .scoped_css import find_scoped_stylesheet, process_scoped_css, generate_scope_id
from .image_optimizer import render_optimized_image, is_optimizable_image, auto_alt_from_filename
from .module_boundaries import (
    ALL_TW_PACKAGES, TW_PACKAGE_BOUNDARIES, TW_PACKAGE_ALIASES,
    ImportClassifier, ImportInfo, is_tw_package, get_package_boundary,
)
from .component_classifier import ComponentClassifier
from .tw_image.component import BUILTIN_IMAGE_COMPONENTS as _BUILTIN_TW_COMPONENTS, render_image_component as _render_tw_image
_BUILTIN_TW_COMPONENTS = set(_BUILTIN_TW_COMPONENTS) | {"Icon"}
from .runtime_loader import PageCapability, RuntimeLoader

# Tailwind CSS utility class support for .tss files
try:
    from .tailwind_map import expand_tailwind_line, expand_tailwind_class
except ImportError:
    def expand_tailwind_line(line):
        return None
    def expand_tailwind_class(cls):
        return None
from .icons import get_icon_svg, ICONS as TW_ICONS
import concurrent.futures
import unicodedata
import errno
from collections import OrderedDict
from dataclasses import dataclass

from .common import content_hash, log
from .lib_executor import LibExecutionError, execute_lib_function, is_function_call

logger = logging.getLogger(__name__)

# Cross-process file locks (best-effort). This prevents concurrent `tw build`
# processes from corrupting shared JSON artifacts (manifest/graphs) mid-write.
try:
    import fcntl  # type: ignore
except ImportError:  # pragma: no cover
    fcntl = None


@contextlib.contextmanager
def _file_lock(target_path: str, *, shared: bool) -> Generator[Any, None, None]:
    lock_path = str(target_path) + ".lock"
    os.makedirs(os.path.dirname(lock_path), exist_ok=True)
    if fcntl is None:
        yield
        return
    with open(lock_path, "w", encoding="utf-8") as lock_file:
        # Some filesystems (notably Android shared storage via FUSE /sdcard)
        # don't implement POSIX file locks and raise ENOSYS/EOPNOTSUPP.
        # In that case, fall back to a no-op lock (best-effort).
        locked = False
        try:
            fcntl.flock(lock_file, fcntl.LOCK_SH if shared else fcntl.LOCK_EX)
            locked = True
        except OSError as e:
            if e.errno not in {errno.ENOSYS, errno.EOPNOTSUPP, errno.EINVAL}:
                raise
        try:
            yield
        finally:
            if locked:
                fcntl.flock(lock_file, fcntl.LOCK_UN)

# Reactivity module (lazy import to avoid circular)
_reactivity = None
def _get_reactivity() -> Any:
    global _reactivity
    if _reactivity is None:
        from . import reactivity as _reactivity
    return _reactivity


PROJECT_ROOT = "../MySite"
HOME_DIR = os.path.join(PROJECT_ROOT, "[home]")
COMPONENTS_DIR = os.path.join(HOME_DIR, "components")
PAGES_DIR = os.path.join(HOME_DIR, "pages")
ASSETS_DIR = os.path.join(HOME_DIR, "assets")
LAYOUTS_DIR = os.path.join(HOME_DIR, "layouts")
API_DIR = os.path.join(HOME_DIR, "api")
INDEX_FILE = os.path.join(HOME_DIR, "index.tw")
STYLE_FILE = os.path.join(HOME_DIR, "style.tss")
CONFIG_FILE = os.path.join(PROJECT_ROOT, "tw.config")

INTERNAL_DIR = os.path.join(PROJECT_ROOT, ".tw")
CACHE_DIR = os.path.join(INTERNAL_DIR, "cache")
MANIFEST_DIR = os.path.join(INTERNAL_DIR, "manifest")
COMPILER_DIR = os.path.join(INTERNAL_DIR, "compiler")

# v0.8.48 (Issue 2): Backup / temporary file extensions that should never be
# treated as framework source files (.tw / .tss / .twm).  These are produced
# by editors (`*.bak`, `*.backup`, `*.old`, `*.tmp`, `*~`) and would otherwise
# risk being picked up by discovery scans or loose `".tw" in filename` checks.
BACKUP_EXTENSIONS = {".bak", ".backup", ".old", ".tmp", ".swp", ".swo"}


def _is_backup_or_temp_file(filename: str) -> bool:
    """Return True if *filename* looks like an editor backup / temp file."""
    name = filename.lower()
    if name.endswith("~"):
        return True
    ext = os.path.splitext(name)[1]
    return ext in BACKUP_EXTENSIONS


PUBLIC_DIR = os.path.join(PROJECT_ROOT, "dist")
BUILD_DIR = PUBLIC_DIR
PUBLIC_ASSETS_DIR = os.path.join(PUBLIC_DIR, "assets")
CHUNKS_DIR = os.path.join(COMPILER_DIR, "chunks")
CHUNKS_PUBLIC_DIR = os.path.join(PUBLIC_DIR, "_tw", "static", "chunks")
CHUNKS_URL_PREFIX = "/_tw/static/chunks/"
BUILD_MANIFEST_FILE = os.path.join(MANIFEST_DIR, "build-manifest.json")
HASH_DB_FILE = os.path.join(CACHE_DIR, "hash-db.json")
DEPENDENCY_GRAPH_FILE = os.path.join(CACHE_DIR, "dependency-graph.json")
DEFAULT_WORKERS = max(1, min(32, os.cpu_count() or 1))
MINIFY_OUTPUT = False
CURRENT_ENV_NAME = "development"
ASSET_URL_MAP = {}
BUILD_MANIFEST_VERSION = 2
DEPENDENCY_GRAPH_VERSION = 2
# Folder route groups: `(marketing)` should be ignored in routes
ROUTE_GROUP_DIR_RE = re.compile(r"^\(.*\)$")

VOID_TAGS = {
    "img", "input", "hr", "br", "meta", "link", "col",
    "embed", "source", "track", "wbr", "area", "base",
}

BOOLEAN_ATTRS = {
    "checked", "disabled", "controls", "selected", "required",
    "readonly", "multiple", "autofocus", "autoplay", "loop",
    "muted", "hidden", "open",
}

CSS_PROPERTIES = {
    "display", "position", "top", "right", "bottom", "left",
    "float", "clear", "overflow", "overflow-x", "overflow-y",
    "z-index", "visibility",
    "width", "height", "min-width", "max-width", "min-height", "max-height",
    "margin", "margin-top", "margin-right", "margin-bottom", "margin-left",
    "padding", "padding-top", "padding-right", "padding-bottom", "padding-left",
    "border", "border-top", "border-right", "border-bottom", "border-left",
    "border-width", "border-style", "border-color", "border-radius",
    "box-sizing", "box-shadow", "outline",
    "background", "background-color", "background-image", "background-size",
    "background-position", "background-repeat", "background-attachment",
    "color", "font", "font-size", "font-family", "font-weight", "font-style",
    "font-variant", "line-height", "letter-spacing", "word-spacing",
    "text-align", "text-decoration", "text-transform", "text-shadow",
    "white-space", "word-break", "word-wrap",
    "flex", "flex-direction", "flex-wrap", "flex-flow",
    "justify-content", "align-items", "align-self", "align-content",
    "flex-grow", "flex-shrink", "flex-basis", "order", "gap",
    "grid", "grid-template", "grid-template-columns", "grid-template-rows",
    "grid-column", "grid-row", "grid-gap", "column-gap", "row-gap",
    "transition", "animation", "transform", "opacity", "cursor",
    "list-style", "pointer-events", "user-select", "content",
    "radius", "shadow", "bg",
    # v0.8.48 (Issue C): vendor-prefixed properties were silently dropped
    # because _is_new_tss_declaration() didn't recognize them, causing them
    # to be merged into the previous declaration's value and lost.
    "-webkit-background-clip", "-webkit-text-fill-color",
    "-webkit-box-shadow", "-webkit-transform", "-webkit-transition",
    "-webkit-animation", "-webkit-appearance", "-webkit-tap-highlight-color",
    "-webkit-user-select", "-webkit-font-smoothing",
    "-moz-appearance", "-moz-user-select", "-moz-box-shadow",
    "-moz-transform", "-moz-transition", "-moz-tab-size",
    "-ms-user-select", "-ms-transform", "-ms-overflow-style",
    "-o-transform", "-o-transition",
    # Non-prefixed versions that were also missing
    "background-clip", "text-fill-color", "object-fit", "object-position",
    "filter", "backdrop-filter", "-webkit-backdrop-filter",
    "clip-path", "-webkit-clip-path", "mask", "-webkit-mask",
    "aspect-ratio", "writing-mode", "text-orientation",
    "scroll-behavior", "overscroll-behavior", "gap",
    # v0.8.48 (bug #4): border/outline per-side longhands were missing, which
    # broke multi-property-per-line splitting (`border-top-color` wasn't
    # recognized as a property, so it got swallowed into the previous value).
    "border-top-color", "border-right-color", "border-bottom-color", "border-left-color",
    "border-top-style", "border-right-style", "border-bottom-style", "border-left-style",
    "border-top-width", "border-right-width", "border-bottom-width", "border-left-width",
    "border-top-left-radius", "border-top-right-radius",
    "border-bottom-left-radius", "border-bottom-right-radius",
    "outline-color", "outline-style", "outline-width", "outline-offset",
}

CSS_ALIASES = {
    "radius": "border-radius",
    "shadow": "box-shadow",
    "font": "font-size",
    "bg": "background",
}

NUMERIC_CSS = {
    "border-radius", "padding", "padding-top", "padding-right",
    "padding-bottom", "padding-left", "margin", "margin-top",
    "margin-right", "margin-bottom", "margin-left",
    "width", "height", "min-width", "max-width", "min-height", "max-height",
    "font-size", "gap", "column-gap", "row-gap", "top", "right", "bottom",
    "left", "border-width", "letter-spacing", "word-spacing", "line-height",
}

HTML_ATTRIBUTES = {
    "id", "class", "href", "src", "alt", "type", "name", "value",
    "placeholder", "action", "method", "target", "rel", "title",
    "for", "rows", "cols", "colspan", "rowspan", "tabindex",
    "aria-label", "aria-hidden", "aria-describedby", "role",
    "checked", "disabled", "selected", "required", "readonly",
    "multiple", "autofocus", "autoplay", "loop", "muted", "controls",
    "hidden", "open", "spellcheck", "autocomplete", "enctype",
    "min", "max", "step", "pattern", "accept", "loading", "decoding",
    "fetchpriority", "width", "height", "sizes", "srcset",
    # v0.8.48 (Issue 5): Meta / head attributes that also happen to be CSS
    # property names.  Without listing them here, `classify_known_prop()`
    # returns "css" and they get rendered as inline `style="…"` instead of
    # real HTML attributes — producing garbled output like
    # `<meta style="content: …">` instead of `<meta content="…">`.
    "content", "charset", "http-equiv", "property",
}

EVENTS = {
    "click", "dblclick", "change", "input", "submit", "focus", "blur",
    "keydown", "keyup", "keypress", "mouseover", "mouseout",
    "mouseenter", "mouseleave", "mousedown", "mouseup",
    "load", "resize", "scroll", "contextmenu",
}

ROUTER_KEYS = {"link", "goto"}

NUM_RE = re.compile(r"^-?\d+(\.\d+)?$")
# Template placeholders: `{brandName}` (single braces)
INTERPOLATION_RE = re.compile(r"\{([^{}]+)\}")
SCRIPT_PLACEHOLDER_RE = re.compile(r"^__TWSCRIPT(\d+)__$")
TWM_SCRIPT_PLACEHOLDER_RE = re.compile(r"^__TWTWM(\d+)__$")
TAG_NAME_RE = re.compile(r"^[A-Za-z][A-Za-z0-9_-]*$")
DYNAMIC_FILE_RE = re.compile(r"^\[(\w+)\]\.tw$")
CATCH_ALL_FILE_RE = re.compile(r"^\[\.\.\.(\w+)\]\.tw$")
OPTIONAL_CATCH_ALL_FILE_RE = re.compile(r"^\[\[\.\.\.(\w+)\]\]\.tw$")

INLINE_SCRIPTS = {}
INLINE_TWM_SCRIPTS = {}
_SCRIPT_COUNTER = 0
_TWM_SCRIPT_COUNTER = 0
# Chunk URL cache: digest -> public URL.
# Keep this bounded in long-lived dev/serve sessions to avoid unbounded memory.
_CHUNK_CACHE: "OrderedDict[str, str]" = OrderedDict()
_CHUNK_CACHE_MAX_DEFAULT = 2048
_COMPONENT_AST_CACHE = {}
_COMPONENT_EXISTS_CACHE = {}
_COMPONENT_PATH_CACHE = {}
_LAYOUT_CACHE = {}
_LAYOUT_META_CACHE = {}
_COMPONENT_DEP_GRAPH_CACHE = {}
_COMPONENT_STYLESHEET_PATHS = {}
_CHUNK_LOCK = threading.Lock()
_SCRIPT_LOCK = threading.Lock()
# Single coarse lock for shared compiler caches used by ThreadPoolExecutor workers.
_CACHE_LOCK = threading.RLock()
_LIB_LOCK = threading.Lock()  # Protects _LIB_MODULES

# Layout-level directives (layouts are treated as raw HTML templates, so we scan & strip these lines)
LAYOUT_RESPONSIVE_RE = re.compile(
    r"(?m)^\s*tw@responsive\s*(?:=\s*)?(true|false|\"true\"|\"false\"|'true'|'false')\s*$"
)

IMPORT_RE = re.compile(r'\bimport\s+"([^"]+)"')
# v0.8.48: default import form — import Image from "tw/image" (bug #3)
IMPORT_DEFAULT_RE = re.compile(r'\bimport\s+[A-Za-z_][A-Za-z0-9_]*\s+from\s+"([^"]+)"')
IMPORT_ES6_RE = re.compile(r'\bimport\s+\{([^}]+)\}\s+from\s+"([^"]+)"')
_ES6_IMPORTS = []  # v0.8.43
LAYOUT_RE = re.compile(r'\blayout\s+(?:"([^"]+)"|([^\s{}]+))')
LOAD_RE = re.compile(r'(?<![\w:])\bload\s+(?:"([^"]+)"|(@[^\s{}"\']+))')
COMPONENT_LOAD_RE = re.compile(r'(?m)^[ \t]*load\s+(?:"([^"]+)"|(@[^\s{}"\']+))[ \t]*$')
LAYOUT_LOAD_RE = re.compile(r'(?m)^[ \t]*load\s+(?:"([^"]+)"|(@[^\s{}"\']+))[ \t]*$')


@dataclass
class BuildOptions:
    force: bool = False
    workers: int = DEFAULT_WORKERS


@dataclass
class Token:
    type: str
    value: str
    line: int
    col: int


@dataclass
class Diagnostic:
    """Unified diagnostic for TW Framework."""
    severity: str = "error"
    code: str = ""
    message: str = ""
    file_path: str = ""
    line: int = 0
    col: int = 0
    end_line: int = 0
    end_col: int = 0
    suggestion: str = ""
    notes: list = None
    phase: str = ""
    exception_type: str = ""
    # New fields for enhanced diagnostics
    category: str = "compiler"
    relative_path: str = ""
    absolute_path: str = ""
    source_snippet: str = ""
    highlight: str = ""
    reason: str = ""
    expected: str = ""
    found: str = ""
    why: str = ""
    doc_link: str = ""
    parser_state: str = ""
    traceback: str = ""

    def __post_init__(self) -> None:
        if not self.relative_path and self.file_path:
            try:
                self.relative_path = os.path.relpath(self.file_path, PROJECT_ROOT)
            except (ValueError, OSError):
                self.relative_path = self.file_path
        if not self.absolute_path and self.file_path:
            self.absolute_path = os.path.abspath(self.file_path)
        if not self.reason and self.message:
            self.reason = self.message
        if not self.code:
            self.code = "TW0000"
        if self.notes is None:
            self.notes = []

    def to_new_diagnostic(self) -> Any:
        """Convert to the new diagnostics.Diagnostic for unified formatting."""
        from .diagnostics import Diagnostic as NewDiag
        return NewDiag(
            id=self.code,
            category=self.category,
            severity=self.severity,
            relative_path=self.relative_path,
            absolute_path=self.absolute_path,
            line=self.line,
            col=self.col,
            source_snippet=self.source_snippet,
            highlight=self.highlight,
            reason=self.reason,
            expected=self.expected,
            found=self.found,
            why=self.why,
            doc_link=self.doc_link,
            parser_state=self.parser_state,
            exception_type=self.exception_type,
            traceback=self.traceback,
        )


class CompilerError(Exception):
    def __init__(self, message, token=None, file_path=None, suggestion=None, code="TW1000", notes=None, category="parser", parser_state="") -> None:
        super().__init__(message)
        self.message = message
        self.token = token
        self.file_path = file_path
        self.suggestion = suggestion
        self.code = code
        self.notes = list(notes or [])
        self.category = category
        self.parser_state = parser_state

    def to_diagnostic(self, fallback_file_path=None) -> Any:
        line = getattr(self.token, "line", 0) or 0
        col = getattr(self.token, "col", 0) or 0
        return Diagnostic(
            severity="error",
            code=self.code or "TW1000",
            message=self.message,
            file_path=self.file_path or fallback_file_path or "",
            line=line,
            col=col,
            end_line=line,
            end_col=col,
            suggestion=self.suggestion,
            notes=list(self.notes or []),
            category=self.category,
            parser_state=self.parser_state,
        )


class DiagnosticEmitter:
    """Formats diagnostics using the unified engine."""

    def __init__(self, file_path, source) -> None:
        self.file_path = file_path
        self.source = source
        self.lines = source.splitlines()

    def format(self, err, debug: bool = False) -> Any:
        from .diagnostics import Diagnostic as NewDiagnostic, format_advanced_error

        if isinstance(err, Diagnostic):
            diag = err
        elif isinstance(err, CompilerError):
            diag = err.to_diagnostic(self.file_path)
        else:
            diag = Diagnostic(
                severity="error",
                code="TW0000",
                message=str(err),
                file_path=self.file_path,
            )

        if diag.line and self.lines and diag.line <= len(self.lines):
            line_text = self.lines[diag.line - 1]
            diag.source_snippet = f"{diag.line:>4} | {line_text}"
            gutter_len = len(f"{diag.line:>4} | ")
            diag.highlight = " " * (gutter_len + max(diag.col - 1, 0)) + "^"

        new_diag = NewDiagnostic.from_legacy(diag)
        return format_advanced_error(new_diag, project_root=PROJECT_ROOT)


def print_diagnostic(diagnostic, debug: bool = False) -> None:
    path = diagnostic.file_path or ""
    source = ""
    if path and os.path.exists(path):
        try:
            source = read_text_file(path)
        except (OSError, UnicodeDecodeError):
            source = ""
    emitter = DiagnosticEmitter(path, source)
    log(emitter.format(diagnostic, debug=debug), level=diagnostic.severity)


def _mojibake_score(text) -> Any:
    return sum(text.count(ch) for ch in ("Ã", "Â", "â", "ð"))


def _repair_common_mojibake(text) -> Any:
    """
    Best-effort repair for UTF-8 text that was previously decoded as latin-1/cp1252
    and then saved again as plain text, for example:
    - `â€¢` -> `•`
    - `â€”` -> `—`
    - `ðŸš€` -> `🚀`
    """
    if not text or not any(ch in text for ch in ("Ã", "Â", "â", "ð")):
        return text
    candidates = []
    for encoding in ("cp1252", "latin-1"):
        try:
            candidates.append(text.encode(encoding).decode("utf-8"))
        except UnicodeError:
            continue
    if not candidates:
        return text
    repaired = min(candidates, key=_mojibake_score)
    return repaired if _mojibake_score(repaired) < _mojibake_score(text) else text


def normalize_source_text(text) -> Any:
    if not text:
        return text
    text = text.lstrip("\ufeff")
    text = unicodedata.normalize("NFC", text)
    return _repair_common_mojibake(text)


def read_text_file(path) -> Any:
    with open(path, "r", encoding="utf-8") as f:
        return normalize_source_text(f.read())


def get_incremental_cache(project_root: str = PROJECT_ROOT) -> Any:
    """Return an IncrementalCache instance for the given project."""
    from .incremental_cache import IncrementalCache
    return IncrementalCache(project_root)


def get_dependency_graph(project_root: str = PROJECT_ROOT) -> Any:
    """Return a DependencyGraph instance for the given project."""
    from .dependency_graph import DependencyGraph
    return DependencyGraph(project_root)


def get_framework_version() -> str:
    """Return the current TW Framework version string."""
    return "1.0.0"


def detect_tw_project(root: str) -> Any:
    """Check if the given directory contains a TW Framework project."""
    config_path = os.path.join(root, "tw.config")
    return os.path.isfile(config_path)


def normalize_path(path) -> Any:
    return os.path.normpath(path)


def resolve_source_path(path, base_dir) -> Any:
    value = str(path or "")
    if value.startswith("@./"):
        value = value[3:]
        return normalize_path(os.path.join(HOME_DIR, value))
    if value.startswith("@../"):
        value = value[1:]
        return normalize_path(os.path.join(base_dir, value))
    project_relative = value.startswith("@")
    if value.startswith("@"):
        value = value[1:]
    if os.path.isabs(value) or re.match(r"^[A-Za-z]:[\\/]", value):
        return normalize_path(value)
    if project_relative:
        return normalize_path(os.path.join(PROJECT_ROOT, value))
    return normalize_path(os.path.join(base_dir, value))


def minify_html_content(text: str):
    # FIX #144: Enhanced HTML minifier — also strips HTML comments,
    # removes leading/trailing whitespace per line, and collapses
    # multiple blank lines. Preserves <pre>, <textarea>, <script> content.
    _protected = []
    def _protect(m):
        _protected.append(m.group(0))
        return f"__TW_PROTECT_{len(_protected) - 1}__"
    text = re.sub(r"<(pre|textarea|script)\b[^>]*>.*?</\1>", _protect, text, flags=re.S | re.I)
    # Remove HTML comments (but keep IE conditional comments if any)
    # Strip HTML comments but preserve TW framework build markers
    text = re.sub(r"<!--(?!\[if)(?!.{0,20}\[TW\])(?!.{0,20}Zero-JS).*?-->", "", text, flags=re.S)
    # Collapse whitespace between tags: `>   <` -> `><`
    text = re.sub(r">\s+<", "><", text)
    # Collapse multiple spaces inside text to single
    text = re.sub(r"[ \t]{2,}", " ", text)
    # Remove blank lines
    text = re.sub(r"\n\s*\n+", "\n", text)
    # Restore protected blocks
    for i, block in enumerate(_protected):
        text = text.replace(f"__TW_PROTECT_{i}__", block)
    return text.strip()


def minify_css_content(text: str):
    # FIX #144: Enhanced CSS minifier — strips last semicolons in rules,
    # removes empty rules, trims units from zero values, removes leading zeros.
    text = re.sub(r"/\*.*?\*/", "", text, flags=re.S)
    text = re.sub(r"\s+", " ", text)
    text = re.sub(r"\s*([{}:;,>~+])\s*", r"\1", text)
    text = re.sub(r";}", "}", text)
    text = re.sub(r"[^{}]+\{\s*}", "", text)
    text = re.sub(r"\b0(px|em|rem|%|pt|pc|in|cm|mm|ex|ch|vw|vh|vmin|vmax)\b", "0", text)
    text = re.sub(r"(?<![\w.])0\.([0-9])", r".\1", text)
    return text.strip()

def minify_js_content(text: str):
    # FIX #144: Enhanced JS minifier — strips block + line comments safely,
    # removes trailing whitespace, collapses multiple semicolons.
    # Strip block comments: /* ... */
    text = re.sub(r"/\*.*?\*/", "", text, flags=re.S)
    # Process line by line
    out_lines = []
    for line in text.splitlines():
        stripped = line.strip()
        if not stripped:
            continue
        # Skip standalone comment lines (be conservative with inline //)
        if stripped.startswith("//"):
            continue
        # Strip trailing single-line comments that are clearly comments
        # (not inside strings) — only when // is preceded by whitespace or start
        stripped = re.sub(r"(?<!:)//.*$", "", stripped)
        # Collapse multiple semicolons
        stripped = re.sub(r";{2,}", ";", stripped)
        out_lines.append(stripped)
    return "".join(out_lines).strip()

def parse_config_scalar(raw) -> Any:
    if isinstance(raw, (int, float, bool)) or raw is None:
        return raw
    if not isinstance(raw, str):
        return raw

    stripped = raw.strip()
    if not stripped:
        return ""
    if (stripped.startswith('"') and stripped.endswith('"')) or (stripped.startswith("'") and stripped.endswith("'")):
        return stripped[1:-1]
    return parse_literal_value(stripped)


def get_config_value(config, *path, default=None) -> Any:
    if not isinstance(config, dict) or not path:
        return default

    current = config
    for part in path:
        if isinstance(current, dict) and part in current:
            current = current[part]
            continue
        dotted = ".".join(path)
        if dotted in config:
            return config[dotted]
        return default
    return current


def normalize_route_directory(rel_dir) -> Any:
    if not rel_dir or rel_dir == ".":
        return ""
    parts = []
    for part in rel_dir.split(os.sep):
        if not part or ROUTE_GROUP_DIR_RE.match(part):
            continue
        parts.append(part)
    return os.path.join(*parts) if parts else ""


def resolve_static_asset_url(value) -> Any:
    if not isinstance(value, str):
        return value
    if value in ASSET_URL_MAP:
        return ASSET_URL_MAP[value]
    return value


def safe_relpath(path, start) -> Any:
    try:
        return os.path.relpath(path, start)
    except (ValueError, OSError):
        return path


def load_build_manifest() -> Any:
    if not os.path.exists(BUILD_MANIFEST_FILE):
        return {"version": BUILD_MANIFEST_VERSION, "pages": {}}
    try:
        with _file_lock(BUILD_MANIFEST_FILE, shared=True):
            with open(BUILD_MANIFEST_FILE, "r", encoding="utf-8") as f:
                data = json.load(f)
        if not isinstance(data, dict):
            return {"version": BUILD_MANIFEST_VERSION, "pages": {}}
        data.setdefault("version", BUILD_MANIFEST_VERSION)
        data.setdefault("pages", {})
        return data
    except (OSError, json.JSONDecodeError, ValueError, TypeError):
        logger.warning("Failed to load build manifest; using empty manifest", exc_info=True)
        return {"version": BUILD_MANIFEST_VERSION, "pages": {}}


def save_build_manifest(manifest) -> None:
    os.makedirs(os.path.dirname(BUILD_MANIFEST_FILE), exist_ok=True)
    manifest = dict(manifest or {})
    manifest["version"] = BUILD_MANIFEST_VERSION
    manifest.setdefault("pages", {})
    with _file_lock(BUILD_MANIFEST_FILE, shared=False):
        # Backup-before-write so a crash mid-write always has a fallback.
        # (The primary protection is temp-file + atomic rename, but backups are
        # helpful when the file is later corrupted by external factors.)
        try:
            if os.path.exists(BUILD_MANIFEST_FILE):
                shutil.copy2(BUILD_MANIFEST_FILE, BUILD_MANIFEST_FILE + ".bak")
        except (OSError, shutil.Error):
            logger.warning("Failed to write build manifest backup", exc_info=True)
        dir_path = os.path.dirname(BUILD_MANIFEST_FILE)
        with tempfile.NamedTemporaryFile("w", encoding="utf-8", dir=dir_path, delete=False) as tmp:
            tmp_path = tmp.name
            json.dump(manifest, tmp, indent=2, sort_keys=True)
            tmp.flush()
            os.fsync(tmp.fileno())
        os.replace(tmp_path, BUILD_MANIFEST_FILE)


def save_dependency_graph(dependency_map) -> None:
    os.makedirs(os.path.dirname(DEPENDENCY_GRAPH_FILE), exist_ok=True)
    metadata = {}
    if isinstance(dependency_map, dict) and "forward" in dependency_map:
        metadata = dict(dependency_map.get("metadata") or {})
        forward_map = dependency_map.get("forward") or {}
    else:
        forward_map = dependency_map or {}
    reverse = {}
    normalized_forward = {}
    for page_key, dependencies in sorted(forward_map.items()):
        normalized_deps = sorted(normalize_path(dep) for dep in dependencies)
        normalized_forward[page_key] = normalized_deps
        for dependency in dependencies:
            dep_key = normalize_path(dependency)
            reverse.setdefault(dep_key, []).append(page_key)
    payload = {
        "version": DEPENDENCY_GRAPH_VERSION,
        "forward": normalized_forward,
        "reverse": {dep: sorted(set(pages)) for dep, pages in sorted(reverse.items())},
        "metadata": metadata,
    }
    with _file_lock(DEPENDENCY_GRAPH_FILE, shared=False):
        # Backup-before-write (same rationale as build manifest).
        try:
            if os.path.exists(DEPENDENCY_GRAPH_FILE):
                shutil.copy2(DEPENDENCY_GRAPH_FILE, DEPENDENCY_GRAPH_FILE + ".bak")
        except (OSError, shutil.Error):
            logger.warning("Failed to write dependency graph backup", exc_info=True)
        dir_path = os.path.dirname(DEPENDENCY_GRAPH_FILE)
        with tempfile.NamedTemporaryFile("w", encoding="utf-8", dir=dir_path, delete=False) as tmp:
            tmp_path = tmp.name
            json.dump(payload, tmp, indent=2, sort_keys=True)
            tmp.flush()
            os.fsync(tmp.fileno())
        os.replace(tmp_path, DEPENDENCY_GRAPH_FILE)


def file_fingerprint(path: str) -> Optional[Dict[str, Any]]:
    if not os.path.exists(path):
        return None
    stat = os.stat(path)
    return {
        "size": stat.st_size,
        "mtime_ns": stat.st_mtime_ns,
    }


def compute_dependency_signature(paths) -> Any:
    digest = hashlib.sha1()
    for path in sorted(normalize_path(p) for p in paths):
        digest.update(path.encode("utf-8"))
        fp = file_fingerprint(path)
        if fp is None:
            digest.update(b"|missing")
        else:
            digest.update(f"|{fp['size']}|{fp['mtime_ns']}".encode("utf-8"))
    return digest.hexdigest()


def collect_dependency_fingerprints(paths) -> Any:
    fingerprints = {}
    for path in sorted(normalize_path(p) for p in paths):
        fingerprints[path] = file_fingerprint(path)
    return fingerprints


def describe_dependency_delta(previous_fingerprints, current_fingerprints) -> Any:
    previous_fingerprints = previous_fingerprints or {}
    current_fingerprints = current_fingerprints or {}
    for path in sorted(set(previous_fingerprints) | set(current_fingerprints)):
        before = previous_fingerprints.get(path)
        after = current_fingerprints.get(path)
        if before != after:
            rel = safe_relpath(path, PROJECT_ROOT)
            if before is None:
                return f"dependency added: {rel}"
            if after is None:
                return f"dependency removed: {rel}"
            return f"dependency changed: {rel}"
    return "dependency changed"


def page_cache_key(page_info) -> Any:
    return normalize_path(page_info["path"])


def cleanup_outputs(paths) -> None:
    for path in paths or []:
        if os.path.exists(path):
            os.remove(path)


def remove_deleted_page_outputs(old_manifest, current_page_keys) -> Any:
    removed = 0
    old_keys = set(old_manifest.get("pages", {}).keys())
    for stale_key in sorted(old_keys - current_page_keys):
        entry = old_manifest["pages"].pop(stale_key, None)
        if entry:
            cleanup_outputs(entry.get("outputs", []))
            removed += 1
    return removed


class PageNode:
    def __init__(self) -> None:
        self.title = ""
        # Backwards compatible:
        # - Old: `page.layout` was a single string (eg "main")
        # - New: `page.layouts` is a chain (outer -> inner), eg ["base", "docs"]
        self.layout = None
        self.layouts = []
        self.render_mode = "static"
        self.revalidate = None
        self.cache_by = None
        self.cache_size = None
        self.redirect_to = None
        self.rewrite_to = None
        self.head = HeadNode()
        self.body = []
        self.loaded_sheets = []
        self.loaded_json = []
        # `.twm` modules loaded via `load @./file.twm` (compiled into a page JS bundle)
        self.loaded_modules = []
        # Local `SCRIPT { ... }` blocks (treated as `.twm` modules)
        self.local_modules = []
        # Explicit client-side lifecycle hooks (never auto-run unless declared)
        # Example:
        #   on load init init
        self.on_load_inits = []
        self.let_vars = {}
        # Optional responsive helpers (enabled via `tw@responsive true|false`)
        self.responsive = False
        # Client-side reactive state variables (state { ... } block)
        self.state_vars = {}
        # generateStaticParams: path to JSON file for dynamic route pre-rendering
        self.generate_static_params = None
        # Source file path for reactivity detection
        self._tw_source_path = ""


class HeadNode:
    def __init__(self) -> None:
        self.metas = []
        self.icon = None
        self.seo = {}


class ElementNode:
    def __init__(self, tag, text=None, token=None, file_path=None) -> None:
        self.tag = tag
        self.text = text
        self.children = []
        self.attrs = []
        self.inline_style = []
        self.events = []
        self.router = {}
        self.token = token
        self.file_path = file_path


class ComponentNode:
    def __init__(self, name, token=None, file_path=None) -> None:
        self.tag = "__component__"
        self.name = name
        self.props = []
        self.children = []
        self.token = token
        self.file_path = file_path


class ForNode:
    def __init__(self, var_name, list_expr) -> None:
        self.tag = "__for__"
        self.var_name = var_name
        self.list_expr = list_expr
        self.children = []


class IfNode:
    def __init__(self, condition) -> None:
        self.tag = "__if__"
        self.condition = condition
        self.children = []
        self.else_children = []


class LetNode:
    def __init__(self, name, value, type_annotation=None) -> None:
        self.tag = "__let__"
        self.name = name
        self.value = value
        self.type_annotation = type_annotation  # e.g. "number", "string", "boolean", "array", "object", "null", "any"


def _node_has_client_js(node) -> bool:
    """Recursively check if a node tree needs client-side framework JS.

    Returns True if the node (or any descendant) has:
    - Events (on:click, etc.) → needs event runtime
    - Router keys (link, redirect) → needs router runtime
    - Client components (lazy components)
    - State vars → needs reactivity runtime
    - TWM modules → needs module bundle
    """
    if isinstance(node, ElementNode):
        if node.events or node.router:
            return True
        for child in node.children:
            if _node_has_client_js(child):
                return True
    elif isinstance(node, ComponentNode):
        # Components may have lazy prop
        for attr_name, _ in getattr(node, "props", []):
            if attr_name == "lazy":
                return True
        for child in getattr(node, "children", []):
            if _node_has_client_js(child):
                return True
    elif isinstance(node, (ForNode, IfNode)):
        for child in getattr(node, "children", []):
            if _node_has_client_js(child):
                return True
    # ScriptNode and ScriptTagNode are user-written JS — they are NOT
    # framework JS, so they don't count against Zero-JS. The page still
    # gets 0 KB of *framework* runtime JS.
    return False


def is_zero_js_page(page, body_html: str = "", needs_router_runtime: bool = False,
                    raw_source: str = "", reactive_enabled: bool = False) -> bool:
    """Detect if a page qualifies for Zero-JS output.

    A page is Zero-JS when it has:
    - No state vars
    - No events on any element
    - No router keys
    - No client/lazy components
    - No TWM modules
    - No on-load inits
    - No reactivity
    - No router runtime needed

    When True, ALL framework runtime JS is skipped — zero KB of framework JS.
    User-written ``script { ... }`` blocks are NOT framework JS and are still
    included in the output.
    """
    # State / reactivity
    if getattr(page, "state_vars", None):
        return False
    if reactive_enabled:
        return False
    # On-load inits
    if getattr(page, "on_load_inits", None):
        return False
    # TWM modules
    if getattr(page, "loaded_modules", None):
        return False
    if getattr(page, "local_modules", None):
        return False
    # Router runtime
    if needs_router_runtime:
        return False
    # Recursively check body nodes for events, router, lazy components
    for node in getattr(page, "body", []) or []:
        if _node_has_client_js(node):
            return False

    # Check for tw/* package imports that require client JS (v0.6.0)
    try:
        _classifier = ImportClassifier()
        source = raw_source or ""
        if source:
            page_imports = _classifier.scan_source_imports(source)
            for imp in page_imports:
                boundary = _classifier.classify_import(imp.path)
                if boundary == "client":
                    return False
    except Exception:
        pass

    return True


class ScriptNode:
    def __init__(self, raw_js, token=None, file_path=None) -> None:
        self.tag = "__script__"
        self.raw_js = raw_js
        self.children = []
        self.token = token
        self.file_path = file_path


class ScriptTagNode:
    """
    Declarative external script loader (Next.js <Script>-like).

    Parsed from:
      script { src "..." strategy afterInteractive|beforeInteractive|lazyOnload }

    This is NOT raw JS. It is always explicit and safe by default.
    """

    def __init__(self, src: str, strategy: str = "afterInteractive", token=None, file_path=None) -> None:
        self.tag = "__script_tag__"
        self.src = src
        self.strategy = strategy
        self.children = []
        self.token = token
        self.file_path = file_path


class StyleSheetNode:
    def __init__(self) -> None:
        self.rules = []


class RuleNode:
    def __init__(self, selector) -> None:
        self.selector = selector
        self.declarations = []
        self.children = []


def is_identifier_boundary_char(ch) -> Any:
    return not (ch.isalnum() or ch == "_")


def tokenize(code, allow_inline_scripts=False) -> Any:
    global _SCRIPT_COUNTER
    global _TWM_SCRIPT_COUNTER

    tokens = []
    i = 0
    line = 1
    col = 1
    n = len(code)

    def advance_one() -> Any:
        nonlocal i, line, col
        ch = code[i]
        i += 1
        if ch == "\n":
            line += 1
            col = 1
        else:
            col += 1
        return ch

    def advance_count(count) -> None:
        for _ in range(count):
            advance_one()

    # Basic operator/punctuation tokens that can appear inside expressions / literals
    TWO_CHAR_OPS = {"==", "!=", ">=", "<=", "&&", "||"}
    ONE_CHAR_OPS = set("[](),:=+-*/.%<>!")

    def skip_block_comment():
        # Assumes current position is at `/*`
        nonlocal i
        advance_count(2)
        while i < n:
            if code[i] == "*" and i + 1 < n and code[i + 1] == "/":
                advance_count(2)
                return
            advance_one()
        # Unterminated block comment: treat as EOF (do not crash the tokenizer)
        return

    def read_string(quote_char) -> bool:
        nonlocal i
        start_line, start_col = line, col
        advance_one()  # consume opening quote
        value = []
        while i < n:
            if code[i] == quote_char:
                advance_one()
                tokens.append(Token("STRING", "".join(value), start_line, start_col))
                return True
            if code[i] == "\\" and i + 1 < n:
                advance_one()
                value.append(advance_one())
            else:
                value.append(advance_one())
        raise CompilerError("Unterminated string literal", Token("STRING", "", start_line, start_col))

    def read_inline_script_block(open_token) -> bool:
        """
        Parse `script { ... }` as a single placeholder token, but do brace matching
        in a JS-aware way (ignore braces inside strings and comments) so nested
        braces / quotes don't break the tokenizer.
        """
        nonlocal i
        global _SCRIPT_COUNTER
        # We are positioned right after the `script` word, and next non-ws char is `{`
        # Consume whitespace then `{`
        while i < n and code[i] in " \t\r\n":
            if code[i] == "\n":
                # Preserve newlines for error reporting consistency
                tokens.append(Token("NL", "\n", line, col))
            advance_one()
        if i >= n or code[i] != "{":
            return False
        advance_one()  # consume `{`

        depth = 1
        body = []
        mode = "code"  # code|string_d|string_s|template|line_comment|block_comment
        quote = ""

        while i < n:
            ch = code[i]

            if mode == "line_comment":
                if ch == "\n":
                    mode = "code"
                body.append(advance_one())
                continue

            if mode == "block_comment":
                if ch == "*" and i + 1 < n and code[i + 1] == "/":
                    body.append(advance_one())
                    body.append(advance_one())
                    mode = "code"
                    continue
                body.append(advance_one())
                continue

            if mode in {"string_d", "string_s"}:
                body.append(advance_one())
                if ch == "\\" and i < n:
                    body.append(advance_one())
                    continue
                if (mode == "string_d" and ch == '"') or (mode == "string_s" and ch == "'"):
                    mode = "code"
                continue

            if mode == "template":
                body.append(advance_one())
                if ch == "\\" and i < n:
                    body.append(advance_one())
                    continue
                if ch == "`":
                    mode = "code"
                continue

            # mode == "code"
            if ch == "/" and i + 1 < n and code[i + 1] == "/":
                body.append(advance_one())
                body.append(advance_one())
                mode = "line_comment"
                continue
            if ch == "/" and i + 1 < n and code[i + 1] == "*":
                body.append(advance_one())
                body.append(advance_one())
                mode = "block_comment"
                continue
            if ch == '"':
                mode = "string_d"
                body.append(advance_one())
                continue
            if ch == "'":
                mode = "string_s"
                body.append(advance_one())
                continue
            if ch == "`":
                mode = "template"
                body.append(advance_one())
                continue

            if ch == "{":
                depth += 1
                body.append(advance_one())
                continue
            if ch == "}":
                depth -= 1
                if depth == 0:
                    advance_one()  # consume final `}`
                    with _SCRIPT_LOCK:
                        uid = _SCRIPT_COUNTER
                        _SCRIPT_COUNTER += 1
                        INLINE_SCRIPTS[uid] = "".join(body)
                    tokens.append(Token("WORD", f"__TWSCRIPT{uid}__", open_token.line, open_token.col))
                    return True
                body.append(advance_one())
                continue

            body.append(advance_one())

        raise CompilerError("Unterminated `script { ... }` block", token=open_token)

    def read_inline_twm_block(open_token) -> bool:
        """
        Parse top-level `SCRIPT { ... }` as a single placeholder token, using the
        same brace-matching strategy as inline JS scripts.

        The content is NOT executed as-is; it is compiled as a `.twm` module and
        registered into the TW module registry for explicit execution via events.
        """
        nonlocal i
        global _TWM_SCRIPT_COUNTER
        # Consume whitespace then `{`
        while i < n and code[i] in " \t\r\n":
            if code[i] == "\n":
                tokens.append(Token("NL", "\n", line, col))
            advance_one()
        if i >= n or code[i] != "{":
            return False
        advance_one()  # consume `{`

        depth = 1
        body = []
        mode = "code"  # code|string_d|string_s|template|line_comment|block_comment

        while i < n:
            ch = code[i]

            if mode == "line_comment":
                if ch == "\n":
                    mode = "code"
                body.append(advance_one())
                continue

            if mode == "block_comment":
                if ch == "*" and i + 1 < n and code[i + 1] == "/":
                    body.append(advance_one())
                    body.append(advance_one())
                    mode = "code"
                    continue
                body.append(advance_one())
                continue

            if mode in {"string_d", "string_s"}:
                body.append(advance_one())
                if ch == "\\" and i < n:
                    body.append(advance_one())
                    continue
                if (mode == "string_d" and ch == '"') or (mode == "string_s" and ch == "'"):
                    mode = "code"
                continue

            if mode == "template":
                body.append(advance_one())
                if ch == "\\" and i < n:
                    body.append(advance_one())
                    continue
                if ch == "`":
                    mode = "code"
                continue

            # mode == "code"
            if ch == "/" and i + 1 < n and code[i + 1] == "/":
                body.append(advance_one())
                body.append(advance_one())
                mode = "line_comment"
                continue
            if ch == "/" and i + 1 < n and code[i + 1] == "*":
                body.append(advance_one())
                body.append(advance_one())
                mode = "block_comment"
                continue
            if ch == '"':
                mode = "string_d"
                body.append(advance_one())
                continue
            if ch == "'":
                mode = "string_s"
                body.append(advance_one())
                continue
            if ch == "`":
                mode = "template"
                body.append(advance_one())
                continue

            if ch == "{":
                depth += 1
                body.append(advance_one())
                continue
            if ch == "}":
                depth -= 1
                if depth == 0:
                    advance_one()  # consume final `}`
                    with _SCRIPT_LOCK:
                        uid = _TWM_SCRIPT_COUNTER
                        _TWM_SCRIPT_COUNTER += 1
                        INLINE_TWM_SCRIPTS[uid] = "".join(body)
                    tokens.append(Token("WORD", f"__TWTWM{uid}__", open_token.line, open_token.col))
                    return True
                body.append(advance_one())
                continue

            body.append(advance_one())

        raise CompilerError("Unterminated `SCRIPT { ... }` block", token=open_token)

    while i < n:
        ch = code[i]

        # Preserve newline as a token so value parsing can stop at EOL reliably.
        if ch == "\n":
            tokens.append(Token("NL", "\n", line, col))
            advance_one()
            continue
        if ch in " \t\r":
            advance_one()
            continue

        if ch == "/" and i + 1 < n and code[i + 1] == "/":
            while i < n and code[i] != "\n":
                advance_one()
            continue
        if ch == "/" and i + 1 < n and code[i + 1] == "*":
            skip_block_comment()
            continue

        if ch in "{}":
            tokens.append(Token("BRACE", ch, line, col))
            advance_one()
            continue

        if ch in {'"', "'"}:
            read_string(ch)
            continue

        # Unquoted path-style token: `@./relative/path.ext` (used by `load @path`).
        # Read greedily so dots/slashes inside the path don't get split into
        # separate ONE_CHAR_OPS tokens.
        if ch == "@":
            at_start_line, at_start_col = line, col
            at_chars = []
            while i < n and code[i] not in ' \t\r\n{}"\'':
                at_chars.append(advance_one())
            tokens.append(Token("WORD", "".join(at_chars), at_start_line, at_start_col))
            continue

        # Operators / punctuation as standalone tokens (helps expression parsing)
        if i + 1 < n and (code[i:i + 2] in TWO_CHAR_OPS):
            tokens.append(Token("WORD", code[i:i + 2], line, col))
            advance_count(2)
            continue
        if ch in ONE_CHAR_OPS:
            tokens.append(Token("WORD", ch, line, col))
            advance_one()
            continue

        start_line, start_col = line, col
        word = []
        # Read until whitespace, braces, quotes, or common operators.
        # Exceptions kept as part of the word:
        #  - `-` between two alnum chars: kebab-case identifiers like
        #    `aria-label`, `data-foo`.
        #  - `:` right after `on` or `bind`: reactive directives like
        #    `on:click`, `bind:value` (see reactivity.py).
        while i < n:
            ch = code[i]
            if ch in ' \t\r\n{}"\'' or ch in ONE_CHAR_OPS:
                if (
                    ch == "-"
                    and word
                    and word[-1].isalnum()
                    and i + 1 < n
                    and code[i + 1].isalnum()
                ):
                    word.append(advance_one())
                    continue
                if (
                    ch == ":"
                    and "".join(word) in ("on", "bind")
                    and i + 1 < n
                    and (code[i + 1].isalnum() or code[i + 1] == "_")
                ):
                    word.append(advance_one())
                    continue
                if (
                    ch == "."
                    and word
                    and word[-1].isdigit()
                    and i + 1 < n
                    and code[i + 1].isdigit()
                ):
                    word.append(advance_one())
                    continue
                break
            word.append(advance_one())
        word = "".join(word)
        if not word:
            continue

        if allow_inline_scripts and word == "script":
            prev_ok = len(tokens) == 0 or is_identifier_boundary_char(code[max(i - len(word) - 1, 0)]) if i - len(word) - 1 >= 0 else True
            if prev_ok:
                if read_inline_script_block(Token("WORD", "script", start_line, start_col)):
                    continue

        if allow_inline_scripts and word == "SCRIPT":
            prev_ok = len(tokens) == 0 or is_identifier_boundary_char(code[max(i - len(word) - 1, 0)]) if i - len(word) - 1 >= 0 else True
            if prev_ok:
                if read_inline_twm_block(Token("WORD", "SCRIPT", start_line, start_col)):
                    continue

        tokens.append(Token("WORD", word, start_line, start_col))

    return tokens


def tokenize_tw(code) -> Any:
    return tokenize(code, allow_inline_scripts=True)


def classify_known_prop(name) -> str:
    nl = name.lower()
    if nl in ROUTER_KEYS:
        return "router"
    if (
        nl.startswith("bind:")
        or nl.startswith("on:")
        or nl.startswith("show:")
        or nl.startswith("tw-")
        or nl.startswith("tw:")
    ):
        return "attr"
    if nl in EVENTS or (nl.startswith("on") and nl[2:] in EVENTS):
        return "event"
    if nl in HTML_ATTRIBUTES or nl.startswith("data-") or nl.startswith("aria-"):
        return "attr"
    if nl in CSS_PROPERTIES or nl in CSS_ALIASES:
        return "css"
    return "unknown"


def normalize_css_prop(name) -> Any:
    return CSS_ALIASES.get(name.lower(), name.lower())


def normalize_attr_name(name) -> Any:
    return name if any(c.isupper() for c in name) else name.lower()


def component_exists(name) -> Any:
    # Built-in tw/ components (tw/image, etc.) — always exist
    if name in _BUILTIN_TW_COMPONENTS or name.lower() in _BUILTIN_TW_COMPONENTS:
        return True
    with _CACHE_LOCK:
        if name in _COMPONENT_EXISTS_CACHE:
            return _COMPONENT_EXISTS_CACHE[name]
    path = resolve_component_path(name)
    found = bool(path and os.path.exists(path))
    with _CACHE_LOCK:
        _COMPONENT_EXISTS_CACHE[name] = found
    return found


def is_component_name(name: str):
    # Only treat it as a component if it actually exists.
    # This avoids errors like `Section {}` being treated as a missing component.
    return component_exists(name)


def resolve_component_path(name: str):
    # 1) Support nested component folders via `import "ui/Button"` (path-like names)
    name = str(name or "")
    if not name:
        raise CompilerError("Component name cannot be empty")
    if "\x00" in name:
        raise CompilerError(
            f"Invalid component name: `{name}`",
            suggestion="Remove null bytes from the component name.",
        )
    if ".." in name:
        raise CompilerError(
            f"Invalid component name: `{name}`",
            suggestion="Component names cannot contain `..` segments.",
        )
    if os.path.isabs(name) or re.match(r"^[A-Za-z]:[\\/]", name):
        raise CompilerError(
            f"Invalid component name: `{name}`",
            suggestion="Use a component name relative to `[home]/components/`, not an absolute path.",
        )
    treat_backslash_as_sep = (os.sep == "\\")
    if "/" in name or (treat_backslash_as_sep and "\\" in name):
        rel = name.replace("\\", "/").lstrip("/")
        # Block path traversal / absolute paths
        rel_norm = os.path.normpath(rel).replace("\\", "/")
        if rel_norm.startswith("../") or rel_norm == ".." or rel_norm.startswith("/"):
            raise CompilerError(
                f"Invalid component import path: `{name}`",
                suggestion="Use a path relative to `[home]/components/` without `..` segments.",
            )
        return os.path.join(COMPONENTS_DIR, rel_norm + ".tw")

    # 2) Fast path: direct component file
    direct = os.path.join(COMPONENTS_DIR, f"{name}.tw")
    if os.path.exists(direct):
        return direct

    # 3) Fallback: search in subfolders (allows organizing components in nested dirs)
    with _CACHE_LOCK:
        if name in _COMPONENT_PATH_CACHE:
            return _COMPONENT_PATH_CACHE[name]
    found = ""
    if os.path.isdir(COMPONENTS_DIR):
        target = f"{name}.tw"
        for root, _, files in os.walk(COMPONENTS_DIR):
            # v0.8.48 (Issue 2): skip editor backup files (.bak, .old, ~, etc.)
            files = [f for f in files if not _is_backup_or_temp_file(f)]
            if target in files:
                found = os.path.join(root, target)
                break
    with _CACHE_LOCK:
        _COMPONENT_PATH_CACHE[name] = found or direct
        return _COMPONENT_PATH_CACHE[name]


def component_name_from_path(path) -> Any:
    full_path = normalize_path(path)
    try:
        rel_path = os.path.relpath(full_path, COMPONENTS_DIR).replace("\\", "/")
    except (ValueError, OSError):
        return ""
    if rel_path.startswith("../") or rel_path == "..":
        return ""
    if not rel_path.lower().endswith(".tw"):
        return ""
    return rel_path[:-3]


def resolve_load_target(raw_path, base_dir, *, token=None, location="load") -> Dict[str, Any]:
    rel_path = str(raw_path or "")
    if not rel_path:
        raise CompilerError(f"{location}: path cannot be empty", token=token)
    if "\x00" in rel_path:
        raise CompilerError(
            f"{location}: invalid path `{rel_path}`",
            token=token,
            suggestion="Remove null bytes from the path.",
        )

    requested_path = resolve_source_path(rel_path, base_dir)
    base_candidate = requested_path
    root, ext = os.path.splitext(base_candidate)

    candidates = []
    if ext:
        candidates.append(base_candidate)
    else:
        candidates.extend(
            [
                base_candidate + ".tw",
                base_candidate + ".twm",
                base_candidate + ".tss",
                base_candidate + ".json",
                base_candidate,
            ]
        )

    existing = []
    seen = set()
    for candidate in candidates:
        normalized = normalize_path(candidate)
        if normalized in seen:
            continue
        seen.add(normalized)
        if os.path.exists(normalized):
            existing.append(normalized)

    display_path = rel_path if rel_path.startswith("@") else f"@{rel_path}"
    if not existing:
        expected = ", ".join(f"`{candidate}`" for candidate in candidates[:3])
        raise CompilerError(
            f"{location}: file not found for `{display_path}`",
            token=token,
            suggestion=f"Expected one of: {expected}",
        )

    if len(existing) > 1:
        choices = ", ".join(f"`{candidate}`" for candidate in existing)
        raise CompilerError(
            f"{location}: ambiguous path `{display_path}`",
            token=token,
            suggestion=f"Add an explicit extension. Matches: {choices}",
        )

    full_path = existing[0]
    if os.path.isdir(full_path):
        raise CompilerError(
            f"{location}: expected a file but got a directory: `{full_path}`",
            token=token,
            suggestion="Point `load` to a file such as `.tw`, `.twm`, `.tss`, or `.json`.",
        )

    resolved_ext = os.path.splitext(full_path)[1].lower()
    kind_map = {
        ".tw": "component",
        ".twm": "module",
        ".tss": "stylesheet",
        ".json": "json",
    }
    if resolved_ext not in kind_map:
        raise CompilerError(
            f"{location}: unsupported file type `{resolved_ext or '<none>'}` for `{full_path}`",
            token=token,
            suggestion="`load` currently supports `.tw`, `.twm`, `.tss`, and `.json` files.",
        )

    return {
        "kind": kind_map[resolved_ext],
        "full_path": full_path,
        "display_path": display_path,
    }


def extract_directives_from_source(raw, base_dir) -> Dict[str, Any]:
    imports = IMPORT_RE.findall(raw)
    for default_path in IMPORT_DEFAULT_RE.findall(raw):
        if default_path not in imports:
            imports.append(default_path)
    es6_imports = IMPORT_ES6_RE.findall(raw)
    layouts = []
    for quoted, bare in LAYOUT_RE.findall(raw):
        name = quoted or bare
        if name:
            layouts.append(name)
    stylesheets = []
    json_files = []
    component_files = []
    module_files = []
    for quoted, atpath in LOAD_RE.findall(raw):
        load_info = resolve_load_target(quoted or atpath, base_dir)
        if load_info["kind"] == "json":
            json_files.append(load_info["full_path"])
        elif load_info["kind"] == "stylesheet":
            stylesheets.append(load_info["full_path"])
        elif load_info["kind"] == "module":
            module_files.append(load_info["full_path"])
        else:
            component_files.append(load_info["full_path"])
    return {
        "imports": imports,
        "es6_imports": es6_imports,
        "layouts": layouts,
        "stylesheets": stylesheets,
        "json_files": json_files,
        "component_files": component_files,
        "module_files": module_files,
    }
    # v0.8.43: ES6 import paths
    for _names, _path in es6_imports:
        _resolved = resolve_source_path(_path.strip(), base_dir)
        for _ext in ["", ".js", ".ts", ".mjs"]:
            _candidate = _resolved + _ext
            if os.path.isfile(_candidate) and _candidate not in module_files:
                module_files.append(_candidate)
                break


def collect_component_dependencies(name, stack=None, seen=None) -> Any:
    with _CACHE_LOCK:
        if name in _COMPONENT_DEP_GRAPH_CACHE:
            return set(_COMPONENT_DEP_GRAPH_CACHE[name])

    stack = list(stack or [])
    seen = seen or set()

    if name in stack:
        chain = " -> ".join(stack + [name])
        raise CompilerError(
            f"Circular component import detected: {chain}",
            file_path=resolve_component_path(name),
            suggestion="Keep the import graph acyclic, or move shared code into a separate component.",
        )

    # Built-in tw/ components — no filesystem deps
    if name in _BUILTIN_TW_COMPONENTS or name.lower() in _BUILTIN_TW_COMPONENTS:
        return set()

    path = resolve_component_path(name)
    if not os.path.exists(path):
        raise CompilerError(
            f"Component not found: `{name}`",
            file_path=path,
            suggestion=f"Expected file: `{path}`",
        )

    if name in seen:
        return set()

    seen.add(name)
    raw = read_text_file(path)
    deps = {normalize_path(path)}
    directives = extract_directives_from_source(raw, os.path.dirname(path))
    deps.update(normalize_path(sheet) for sheet in directives.get("stylesheets", []))
    deps.update(normalize_path(payload) for payload in directives.get("json_files", []))

    for child_name in directives["imports"]:
        deps.update(collect_component_dependencies(child_name, stack + [name], seen))

    with _CACHE_LOCK:
        _COMPONENT_DEP_GRAPH_CACHE[name] = sorted(deps)
    return set(deps)


def collect_page_dependencies(tw_path) -> Any:
    tw_path = normalize_path(tw_path)
    base_dir = os.path.dirname(tw_path)
    raw = read_text_file(tw_path)
    directives = extract_directives_from_source(raw, base_dir)

    deps = {tw_path, normalize_path(CONFIG_FILE)}
    sibling_json = normalize_path(tw_path[:-3] + ".json")
    file_name = os.path.basename(tw_path)
    if classify_dynamic_route_file(file_name) and os.path.exists(sibling_json):
        deps.add(sibling_json)
    if os.path.exists(STYLE_FILE):
        deps.add(normalize_path(STYLE_FILE))

    for stylesheet_path in directives["stylesheets"]:
        deps.add(stylesheet_path)
    for json_path in directives.get("json_files", []):
        deps.add(json_path)
    for module_path in directives.get("module_files", []):
        deps.add(module_path)
    for component_path in directives.get("component_files", []):
        deps.add(component_path)
        component_name = component_name_from_path(component_path)
        if component_name:
            deps.update(collect_component_dependencies(component_name))

    for layout_name in directives["layouts"]:
        layout_path = normalize_path(os.path.join(LAYOUTS_DIR, f"{layout_name}.tw"))
        deps.add(layout_path)
        if os.path.exists(layout_path):
            layout_raw = read_text_file(layout_path)
            for quoted, atpath in LAYOUT_LOAD_RE.findall(layout_raw):
                load_info = resolve_load_target(quoted or atpath, HOME_DIR, location="layout load")
                loaded_path = load_info["full_path"]
                deps.add(loaded_path)
                if load_info["kind"] == "component" and os.path.exists(loaded_path):
                    # one level deep: if that component itself loads a stylesheet, track it too
                    inner_raw = read_text_file(loaded_path)
                    for q2, a2 in COMPONENT_LOAD_RE.findall(inner_raw):
                        inner_load_info = resolve_load_target(
                            q2 or a2,
                            os.path.dirname(loaded_path),
                            location="component load",
                        )
                        deps.add(inner_load_info["full_path"])

    for component_name in directives["imports"]:
        deps.update(collect_component_dependencies(component_name))

    return sorted(deps)


def route_path_from_page_info(page_info, item=None) -> str:
    # App Router pages have a canonical url_path — use it directly.
    # This avoids the double-nesting bug where rel_dir="about" + name="about"
    # produces "/about/about" (fixed v0.8.2).
    url_path = page_info.get("url_path")
    if url_path:
        if item and page_info.get("type") == "dynamic":
            dyn = resolve_dynamic_segments(page_info, item)
            if dyn:
                # Replace the dynamic segment placeholder in url_path
                seg = "/".join(dyn)
                param = page_info.get("param", "")
                if param and param in url_path:
                    return url_path.replace(f"[{param}]", seg).replace(f"[...{param}]", seg)
                return f"{url_path.rstrip('/')}/{seg}" if seg else url_path
        return url_path

    route_parts = []
    rel_dir = page_info.get("rel_dir", "")
    if rel_dir:
        route_parts.append(rel_dir)
    if page_info.get("type") == "dynamic":
        route_parts.extend(resolve_dynamic_segments(page_info, item or {}))
    else:
        name = page_info.get("name", "index")
        if name != "index":
            # App Router: name may already be part of rel_dir (e.g. rel_dir="about", name="about")
            # Don't duplicate — only append if name is not already the last segment of rel_dir
            is_app_router = page_info.get("app_router", False)
            if is_app_router:
                rel_segments = rel_dir.split("/") if rel_dir else []
                if rel_segments and rel_segments[-1] == name:
                    pass  # name already in rel_dir, skip
                else:
                    route_parts.append(name)
            else:
                route_parts.append(name)
    route = "/" + "/".join(filter(None, route_parts))
    return route or "/"


def collect_page_metadata(page_info, page_ast=None, route_path=None, *, pipeline="legacy", item=None) -> Dict[str, Any]:
    page_ast = page_ast or load_page_ast_from_file(page_info["path"])
    raw = read_text_file(page_info["path"])
    directives = extract_directives_from_source(raw, os.path.dirname(page_info["path"]))
    layouts = list(getattr(page_ast, "layouts", None) or [])
    if not layouts and getattr(page_ast, "layout", None):
        layouts = [page_ast.layout]
    return {
        "pipeline": pipeline,
        "route_path": route_path or route_path_from_page_info(page_info, item=item),
        "page_type": page_info.get("type", "static"),
        "route_kind": page_info.get("route_kind", "static"),
        "param": page_info.get("param"),
        "render_mode": getattr(page_ast, "render_mode", "static"),
        "revalidate": getattr(page_ast, "revalidate", None),
        "cache_by": getattr(page_ast, "cache_by", None),
        "cache_size": getattr(page_ast, "cache_size", None),
        "layouts": layouts,
        "components": sorted(set(directives.get("imports", []))),
        "source": normalize_path(page_info["path"]),
    }


def get_public_env(config=None) -> dict:
    """Returns only the env vars explicitly allow-listed for client-facing
    pages via `env: public: "A, B, C"` in tw.config. Everything else in
    os.environ is server-only and never reaches page render context."""
    if config is None:
        config = load_config()
    raw = get_config_value(config, "env", "public", default="")
    if isinstance(raw, str):
        names = [part.strip() for part in raw.split(",") if part.strip()]
    elif isinstance(raw, (list, tuple)):
        names = [str(part).strip() for part in raw if str(part).strip()]
    else:
        names = []
    return {name: os.environ[name] for name in names if name in os.environ}


def create_request_context(route_path, params=None) -> Dict[str, Any]:
    return {"path": route_path or "/", "params": dict(params or {}), "env": get_public_env()}


def build_page_context(page_info, page_ast=None, tw_path=None, *, item=None, route_path=None, request_params=None) -> Any:
    tw_path = tw_path or page_info["path"]
    page_ast = page_ast or load_page_ast_from_file(tw_path)
    params = dict(request_params or {})
    context = create_base_context(page_ast, tw_path)
    if isinstance(item, dict):
        context.update(item)
    if page_info.get("type") == "dynamic":
        param_name = page_info.get("param")
        segments = resolve_dynamic_segments(page_info, item or {})
        if param_name:
            params.setdefault(param_name, "/".join(segments))
            if page_info.get("route_kind") != "single":
                params.setdefault(param_name + "Segments", segments)
    context.update(params)
    resolved_route = route_path or route_path_from_page_info(page_info, item=item)
    context["_tw_route"] = resolved_route or "/"
    context["request"] = create_request_context(resolved_route or "/", params)
    return context


def parse_literal_value(raw) -> Any:
    if isinstance(raw, (int, float, bool)) or raw is None:
        return raw
    if not isinstance(raw, str):
        return raw

    stripped = raw.strip()
    lower = stripped.lower()
    if lower == "true":
        return True
    if lower == "false":
        return False
    if lower in {"null", "none"}:
        return None
    if NUM_RE.match(stripped):
        return float(stripped) if "." in stripped else int(stripped)
    if (stripped.startswith("{") and stripped.endswith("}")) or (stripped.startswith("[") and stripped.endswith("]")):
        try:
            return json.loads(stripped)
        except json.JSONDecodeError:
            # Allow trailing commas and a slightly more forgiving literal syntax
            # via Python's safe literal parser.
            try:
                return ast.literal_eval(stripped)
            except (ValueError, SyntaxError):
                # Optional debug: surface parsing failures instead of silently swallowing.
                if os.environ.get("TW_WARN_LITERAL_PARSE", "").strip().lower() in {"1", "true", "yes", "on"}:
                    log(f"⚠️ Literal parse failed, treating as string: {raw!r}", level="warning")
                return raw
    if stripped.startswith('"') and stripped.endswith('"') and len(stripped) >= 2:
        try:
            return json.loads(stripped)
        except json.JSONDecodeError:
            return stripped[1:-1]
    return raw


def to_bool(value) -> Any:
    if isinstance(value, bool):
        return value
    if isinstance(value, (int, float)):
        return value != 0
    if value is None:
        return False
    if isinstance(value, str):
        return value.strip().lower() not in {"", "0", "false", "none", "null"}
    if isinstance(value, (list, tuple, dict, set)):
        return len(value) > 0
    return bool(value)


def resolve_path(path, context) -> Any:
    current = context
    for part in path.split("."):
        if isinstance(current, dict) and part in current:
            current = current[part]
        else:
            return None
    return current


def _transform_logic_operators(expr) -> Any:
    expr = expr.replace("&&", " and ")
    expr = expr.replace("||", " or ")
    expr = re.sub(r"(?<![=!<>])!(?!=)", " not ", expr)
    return expr


def _safe_eval(node, context) -> Any:
    if isinstance(node, ast.Expression):
        return _safe_eval(node.body, context)

    if isinstance(node, ast.Constant):
        return node.value

    if isinstance(node, ast.Name):
        if node.id in {"true", "false", "null", "none"}:
            return {"true": True, "false": False, "null": None, "none": None}[node.id]
        return context.get(node.id)

    if isinstance(node, ast.Attribute):
        base = _safe_eval(node.value, context)
        if isinstance(base, dict):
            return base.get(node.attr)
        return getattr(base, node.attr, None)

    if isinstance(node, ast.Subscript):
        base = _safe_eval(node.value, context)
        index = _safe_eval(node.slice, context)
        try:
            return base[index]
        except (TypeError, KeyError, IndexError):
            return None

    if isinstance(node, ast.Index):
        return _safe_eval(node.value, context)

    if isinstance(node, ast.List):
        return [_safe_eval(item, context) for item in node.elts]

    if isinstance(node, ast.Tuple):
        return tuple(_safe_eval(item, context) for item in node.elts)

    if isinstance(node, ast.Dict):
        return {
            _safe_eval(k, context): _safe_eval(v, context)
            for k, v in zip(node.keys, node.values)
        }

    if isinstance(node, ast.BoolOp):
        if isinstance(node.op, ast.And):
            for value_node in node.values:
                result = _safe_eval(value_node, context)
                if not to_bool(result):
                    return result
            return result
        if isinstance(node.op, ast.Or):
            for value_node in node.values:
                result = _safe_eval(value_node, context)
                if to_bool(result):
                    return result
            return result

    if isinstance(node, ast.UnaryOp):
        value = _safe_eval(node.operand, context)
        if isinstance(node.op, ast.Not):
            return not to_bool(value)
        if isinstance(node.op, ast.USub):
            return -value
        if isinstance(node.op, ast.UAdd):
            return +value

    if isinstance(node, ast.BinOp):
        left = _safe_eval(node.left, context)
        right = _safe_eval(node.right, context)
        if isinstance(node.op, ast.Add):
            return left + right
        if isinstance(node.op, ast.Sub):
            return left - right
        if isinstance(node.op, ast.Mult):
            return left * right
        if isinstance(node.op, ast.Div):
            return left / right
        if isinstance(node.op, ast.Mod):
            return left % right

    if isinstance(node, ast.Compare):
        left = _safe_eval(node.left, context)
        for op, comparator_node in zip(node.ops, node.comparators):
            right = _safe_eval(comparator_node, context)
            ok = False
            if isinstance(op, ast.Eq):
                ok = left == right
            elif isinstance(op, ast.NotEq):
                ok = left != right
            elif isinstance(op, ast.Gt):
                ok = left > right
            elif isinstance(op, ast.GtE):
                ok = left >= right
            elif isinstance(op, ast.Lt):
                ok = left < right
            elif isinstance(op, ast.LtE):
                ok = left <= right
            elif isinstance(op, ast.In):
                ok = left in right
            elif isinstance(op, ast.NotIn):
                ok = left not in right
            else:
                raise ValueError("Unsupported comparison operator")
            if not ok:
                return False
            left = right
        return True

    raise ValueError(f"Unsupported expression node: {type(node).__name__}")


def evaluate_expression(expr, context) -> Any:
    expr = expr.strip()
    if not expr:
        return ""
    try:
        transformed = _transform_logic_operators(expr)
        tree = ast.parse(transformed, mode="eval")
        return _safe_eval(tree, context)
    except (SyntaxError, ValueError):
        value = resolve_path(expr, context)
        if value is not None:
            return value
        return None
    except Exception as err:
        # Do not silently swallow runtime errors (e.g. ZeroDivisionError) without any clue.
        # FIX #142: TW_STRICT_EVAL=1 raises errors instead of silent fallback.
        # When unset (default), TW gracefully degrades to static rendering.
        if os.environ.get("TW_STRICT_EVAL", "").strip().lower() in {"1", "true", "yes", "on"}:
            raise
        log(
            f"⚠️ Expression eval failed: {expr!r} ({type(err).__name__}: {err})",
            level="warning",
        )
        value = resolve_path(expr, context)
        if value is not None:
            return value
        return None


PLACEHOLDER_MOUSTACHE_RE = re.compile(r"\{\{([^{}]+)\}\}")
RESERVED_EXPR_NAMES = {"true", "false", "null", "none"}


def extract_placeholder_expressions(text) -> Any:
    if text is None or "{" not in str(text):
        return []
    expressions = []
    for match in PLACEHOLDER_MOUSTACHE_RE.finditer(str(text)):
        expr = match.group(1).strip()
        if expr:
            expressions.append(expr)
    for match in INTERPOLATION_RE.finditer(str(text)):
        expr = match.group(1).strip()
        if expr:
            expressions.append(expr)
    return expressions


class ExpressionNameCollector(ast.NodeVisitor):
    def __init__(self) -> None:
        self.names = []

    def visit_Name(self, node) -> None:
        self.names.append(node.id)


def collect_expression_names(expr) -> Any:
    expr = str(expr or "").strip()
    if not expr:
        return []
    try:
        transformed = _transform_logic_operators(expr)
        tree = ast.parse(transformed, mode="eval")
    except (SyntaxError, ValueError):
        return []
    collector = ExpressionNameCollector()
    collector.visit(tree)
    names = []
    seen = set()
    for name in collector.names:
        if name in RESERVED_EXPR_NAMES or name in seen:
            continue
        seen.add(name)
        names.append(name)
    return names


def build_diagnostic(severity, code, message, file_path, token=None, suggestion=None, notes=None) -> Any:
    line = getattr(token, "line", 0) or 0
    col = getattr(token, "col", 0) or 0
    return Diagnostic(
        severity=severity,
        code=code,
        message=message,
        file_path=file_path or "",
        line=line,
        col=col,
        end_line=line,
        end_col=col,
        suggestion=suggestion,
        notes=list(notes or []),
    )


def collect_known_scope_names(context) -> Any:
    names = set(context.keys() if isinstance(context, dict) else [])
    names.update({"config", "site", "env", "request", "props", "children"})
    return names


def _is_likely_literal_text(expr: str) -> bool:
    """Heuristic: detect expressions that are likely literal documentation text,
    not real TW interpolation.

    Returns True when the expression inside ``{...}`` looks like:
    - JS destructuring: ``{ to, subject, message }`` (commas)
    - JS/TS code: contains ``=``, ``;``, ``function``, ``const``, ``let``
    - Template strings with spaces and words that aren't valid expressions

    These patterns are common in documentation pages that show code examples
    inside ``p "..."`` text.  Suppressing TW2001 for them prevents false
    positives that break ``--prod`` builds.
    """
    expr = str(expr or "").strip()
    if not expr:
        return True

    # Multiple comma-separated identifiers → JS destructuring or list
    # e.g. "to, subject, message"
    if "," in expr:
        return True

    # Contains assignment, semicolons, or JS keywords → code snippet
    code_indicators = ("=", ";", "function", "const ", "let ", "var ",
                       "=>", "return ", "await ", "async ", "import ",
                       "export ", "require(", "new ", "class ")
    if any(ind in expr for ind in code_indicators):
        return True

    # Contains more than 2 space-separated tokens → likely prose, not an expression
    # But allow "count + 1" (2 words with operator) and "item.title" (1 word)
    words = expr.split()
    if len(words) > 2:
        return True

    return False


def analyze_expression_symbols(expr, scope_names, diagnostics, token=None, file_path=None, label="expression") -> None:
    # Suppress TW2001 warnings for expressions that are likely literal
    # documentation text rather than real TW interpolation.  This prevents
    # false positives when documentation pages show code examples containing
    # braces like ``{ to, subject, message }`` or ``{variable}``.
    if _is_likely_literal_text(expr):
        return

    for name in collect_expression_names(expr):
        if name.startswith("_tw_") or name in scope_names:
            continue
        diagnostics.append(build_diagnostic(
            "warning",
            "TW2001",
            f"Undefined symbol `{name}` in {label}.",
            file_path=file_path or getattr(token, "file_path", "") or "",
            token=token,
            suggestion="Define the symbol, use JSON load/let/import, or remove braces if you want literal placeholder text.",
            notes=[f"Expression: {expr}"],
        ))


def analyze_interpolated_text(text, scope_names, diagnostics, token=None, file_path=None, label="template") -> None:
    for expr in extract_placeholder_expressions(text):
        analyze_expression_symbols(expr, scope_names, diagnostics, token=token, file_path=file_path, label=label)


def _append_unique_diagnostic(diagnostics, diagnostic, seen_keys) -> None:
    key = (
        diagnostic.severity,
        diagnostic.code,
        diagnostic.file_path,
        diagnostic.line,
        diagnostic.col,
        diagnostic.message,
    )
    if key in seen_keys:
        return
    seen_keys.add(key)
    diagnostics.append(diagnostic)


def analyze_nodes_semantics(nodes, scope_names, diagnostics, file_path, component_stack=None, seen_keys=None) -> None:
    current_scope = set(scope_names)
    component_stack = list(component_stack or [])
    seen_keys = seen_keys if seen_keys is not None else set()

    for node in nodes or []:
        token = getattr(node, "token", None)
        node_file_path = getattr(node, "file_path", None) or file_path

        if isinstance(node, LetNode):
            analyze_interpolated_text(node.value, current_scope, diagnostics, token=token, file_path=node_file_path, label=f"`let {node.name}` value")
            current_scope.add(node.name)
            continue

        if isinstance(node, ForNode):
            analyze_expression_symbols(node.list_expr, current_scope, diagnostics, token=token, file_path=node_file_path, label=f"`for {node.var_name} in ...`")
            child_scope = set(current_scope)
            child_scope.add(node.var_name)
            analyze_nodes_semantics(node.children, child_scope, diagnostics, node_file_path, component_stack=component_stack, seen_keys=seen_keys)
            continue

        if isinstance(node, IfNode):
            analyze_expression_symbols(node.condition, current_scope, diagnostics, token=token, file_path=node_file_path, label="`if` condition")
            analyze_nodes_semantics(node.children, current_scope, diagnostics, node_file_path, component_stack=component_stack, seen_keys=seen_keys)
            analyze_nodes_semantics(node.else_children, current_scope, diagnostics, node_file_path, component_stack=component_stack, seen_keys=seen_keys)
            continue

        if isinstance(node, ComponentNode):
            prop_names = set()
            for key, raw_value in node.props:
                prop_names.add(key)
                analyze_interpolated_text(raw_value, current_scope, diagnostics, token=token, file_path=node_file_path, label=f"component prop `{node.name}.{key}`")
            analyze_nodes_semantics(node.children, current_scope, diagnostics, node_file_path, component_stack=component_stack, seen_keys=seen_keys)
            if node.name not in component_stack:
                try:
                    component_nodes = load_component_ast(node.name)
                    component_path = resolve_component_path(node.name)
                    component_scope = set(current_scope)
                    component_scope.update(prop_names)
                    component_scope.update({"props", "children"})
                    analyze_nodes_semantics(
                        component_nodes,
                        component_scope,
                        diagnostics,
                        component_path,
                        component_stack=component_stack + [node.name],
                        seen_keys=seen_keys,
                    )
                except CompilerError:
                    # Component analysis should not crash page-level semantic analysis.
                    # Missing/broken components are handled elsewhere as diagnostics.
                    pass
                except Exception:
                    logger.exception("Unexpected error while analyzing component `%s` semantics", node.name)
            continue

        if isinstance(node, ElementNode):
            # Element TEXT content is user-facing text, not code.
            # {var} in text is either real interpolation (var is defined → works)
            # or literal documentation text (var not defined → shows literal {var}).
            # Neither case should produce TW2001 warnings that break --prod builds.
            # So we skip analyze_interpolated_text for node.text.
            # We still analyze attributes, styles, events, and router — those are
            # code contexts where undefined variables are real bugs.
            seen_attrs = set()
            for attr_name, raw_value in node.attrs:
                if attr_name in seen_attrs:
                    _append_unique_diagnostic(
                        diagnostics,
                        build_diagnostic(
                            "warning",
                            "TW2002",
                            f"Duplicate attribute `{attr_name}` on `<{node.tag}>`.",
                            file_path=node_file_path,
                            token=token,
                            suggestion="Remove the duplicate attribute to keep the final HTML predictable.",
                        ),
                        seen_keys,
                    )
                seen_attrs.add(attr_name)
                analyze_interpolated_text(raw_value, current_scope, diagnostics, token=token, file_path=node_file_path, label=f"`{node.tag}` attribute `{attr_name}`")
            for css_name, raw_value in node.inline_style:
                analyze_interpolated_text(raw_value, current_scope, diagnostics, token=token, file_path=node_file_path, label=f"`{node.tag}` style `{css_name}`")
            for event_name, raw_handler in node.events:
                analyze_interpolated_text(raw_handler, current_scope, diagnostics, token=token, file_path=node_file_path, label=f"`{node.tag}` event `{event_name}`")
            for router_key, raw_value in (node.router or {}).items():
                analyze_interpolated_text(raw_value, current_scope, diagnostics, token=token, file_path=node_file_path, label=f"`{node.tag}` router `{router_key}`")
            analyze_nodes_semantics(node.children, current_scope, diagnostics, node_file_path, component_stack=component_stack, seen_keys=seen_keys)


def analyze_page_semantics(page_ast, context, tw_path, page_info=None) -> Any:
    diagnostics = []
    seen_keys = set()
    scope_names = collect_known_scope_names(context)
    if page_info and page_info.get("type") == "dynamic":
        scope_names.add(page_info.get("param", ""))
        if page_info.get("route_kind") != "single":
            scope_names.add(page_info.get("param", "") + "Segments")

    analyze_interpolated_text(page_ast.title, scope_names, diagnostics, file_path=tw_path, label="page title")
    analyze_interpolated_text(page_ast.redirect_to, scope_names, diagnostics, file_path=tw_path, label="page redirect")
    analyze_interpolated_text(page_ast.rewrite_to, scope_names, diagnostics, file_path=tw_path, label="page rewrite")
    analyze_interpolated_text(page_ast.head.icon, scope_names, diagnostics, file_path=tw_path, label="head icon")
    for meta in page_ast.head.metas:
        for key, raw_value in meta.items():
            analyze_interpolated_text(raw_value, scope_names, diagnostics, file_path=tw_path, label=f"head meta `{key}`")
    for key, raw_value in page_ast.head.seo.items():
        analyze_interpolated_text(raw_value, scope_names, diagnostics, file_path=tw_path, label=f"head seo `{key}`")

    analyze_nodes_semantics(page_ast.body, scope_names, diagnostics, tw_path, seen_keys=seen_keys)
    deduped = []
    dedupe_keys = set()
    for diagnostic in diagnostics:
        _append_unique_diagnostic(deduped, diagnostic, dedupe_keys)
    return deduped


def eval_condition(expr, context) -> Any:
    return to_bool(evaluate_expression(expr, context))


def interpolate(text, context) -> Any:
    if text is None or "{" not in str(text):
        return text

    def repl(match) -> Any:
        value = evaluate_expression(match.group(1), context)
        return match.group(0) if value is None else str(value)

    # Support moustache-style placeholders: `{{brandName}}`
    # (common habit from other template engines)
    rendered = re.sub(r"\{\{([^{}]+)\}\}", repl, str(text))

    return INTERPOLATION_RE.sub(repl, rendered)


def _append_px_if_numeric(token) -> Any:
    stripped = str(token).strip()
    if NUM_RE.match(stripped):
        return "0" if float(stripped) == 0 else f"{stripped}px"
    return stripped


def _split_css_tokens_outside_parens(value) -> Any:
    tokens = []
    current = []
    depth = 0
    for ch in value:
        if ch == "(":
            depth += 1
            current.append(ch)
            continue
        if ch == ")":
            depth = max(0, depth - 1)
            current.append(ch)
            continue
        if ch.isspace() and depth == 0:
            if current:
                tokens.append("".join(current))
                current = []
            continue
        current.append(ch)
    if current:
        tokens.append("".join(current))
    return tokens


def _normalize_css_function_args(value) -> Any:
    def repl(match) -> Any:
        fn = match.group(1)
        args = match.group(2)
        parts = re.split(r"(\s*,\s*|\s+)", args)
        converted = []
        for part in parts:
            if not part or re.fullmatch(r"\s*,\s*|\s+", part):
                converted.append(part)
                continue
            converted.append(_append_px_if_numeric(part))
        return f"{fn}({''.join(converted)})"

    return re.sub(r"\b(translate(?:3d|X|Y|Z)?|blur)\(([^)]*)\)", repl, value)


def _normalize_border_like_value(value) -> Any:
    tokens = _split_css_tokens_outside_parens(value)
    if tokens and NUM_RE.match(tokens[0]):
        tokens[0] = _append_px_if_numeric(tokens[0])
    return " ".join(tokens)


def _normalize_shadow_value(value) -> Any:
    tokens = _split_css_tokens_outside_parens(value)
    normalized = []
    for token in tokens:
        normalized.append(_append_px_if_numeric(token) if NUM_RE.match(token) else token)
    return " ".join(normalized)


def _normalize_at_rule_selector(selector) -> Any:
    if not selector.lstrip().startswith("@media"):
        return selector
    return re.sub(
        r"((?:min|max)-(?:width|height)\s*:\s*)(-?\d+(?:\.\d+)?)\b",
        lambda m: f"{m.group(1)}{_append_px_if_numeric(m.group(2))}",
        selector,
    )


def finalize_css_value(css_prop, raw_value, context) -> Any:
    value = interpolate(raw_value, context)
    if value is None:
        value = ""
    if css_prop in NUMERIC_CSS and isinstance(value, (int, float)):
        if css_prop == "line-height":
            return str(value)
        return _append_px_if_numeric(value)
    if isinstance(value, str):
        stripped = value.strip()
        if len(stripped) >= 2 and (
            (stripped[0] == '"' and stripped[-1] == '"')
            or (stripped[0] == "'" and stripped[-1] == "'")
        ):
            stripped = stripped[1:-1]
        stripped = _normalize_css_function_args(stripped)
        if css_prop == "line-height" and NUM_RE.match(stripped):
            return stripped
        if css_prop in {"border", "border-top", "border-right", "border-bottom", "border-left", "outline"}:
            return _normalize_border_like_value(stripped)
        if css_prop in {"box-shadow", "text-shadow"}:
            return _normalize_shadow_value(stripped)
        if css_prop in NUMERIC_CSS:
            if NUM_RE.match(stripped):
                return _append_px_if_numeric(stripped)
            # Multi-value numeric shorthand (eg `padding 12 18` or `margin 8 12 8 12`)
            parts = [p for p in stripped.split() if p]
            if parts and all(NUM_RE.match(p) for p in parts):
                return " ".join(_append_px_if_numeric(p) for p in parts)
        return stripped
    return str(value)


def classify_known_keywords() -> Any:
    return {
        "let", "if", "else", "for", "each", "in", "as", "import",
        "layout", "head", "body", "title", "load", "page",
        *EVENTS, *ROUTER_KEYS,
    }


def peek(tokens, i) -> Any:
    return tokens[i] if i < len(tokens) else None


def collect_until_block(tokens, i) -> Any:
    parts = []
    while i < len(tokens) and not (tokens[i].type == "BRACE" and tokens[i].value == "{"):
        if tokens[i].type != "NL":
            parts.append(tokens[i].value)
        i += 1
    return " ".join(parts).strip(), i


def collect_until_eol(tokens, i, stop_on_block_open=False) -> Any:
    """
    Collect tokens into an expression string until newline / block end.
    - STRING tokens are re-quoted to preserve valid JSON/Python literal parsing.
    - Supports multi-token literals like: ["a", "b",]
    - Supports inline JSON objects: let x = {"key": "value"}
    """
    parts = []
    depth = 0  # bracket/paren nesting [ ]
    brace_depth = 0  # JSON object brace nesting { }
    while i < len(tokens):
        tok = tokens[i]
        if tok.type == "WORD" and tok.value == ";" and depth == 0 and brace_depth == 0:
            break
        if tok.type == "NL" and depth == 0 and brace_depth == 0:
            break
        if tok.type == "BRACE":
            if tok.value == "{" and depth == 0 and brace_depth == 0:
                # If stop_on_block_open and we already have parts, this { starts a new TW block
                if stop_on_block_open and parts:
                    break
                # If not stop_on_block_open, { at top level is always a TW block
                if not stop_on_block_open:
                    break
                # stop_on_block_open=True and parts is empty: this { starts a JSON object literal
                brace_depth += 1
                parts.append(tok.value)
                i += 1
                continue
            elif tok.value == "{" and brace_depth > 0:
                brace_depth += 1
                parts.append(tok.value)
                i += 1
                continue
            elif tok.value == "}" and brace_depth > 0:
                brace_depth -= 1
                parts.append(tok.value)
                i += 1
                continue
            elif tok.value == "}" and depth == 0:
                break
            # depth > 0 — inside brackets, treat { } as JSON object delimiters
            if depth > 0:
                parts.append(tok.value)
                i += 1
                continue
            break

        if tok.type == "WORD":
            if tok.value in {"[", "("}:
                depth += 1
            elif tok.value in {"]", ")"} and depth > 0:
                depth -= 1
            parts.append(tok.value)
        elif tok.type == "STRING":
            parts.append(json.dumps(tok.value))
        i += 1

    expr = " ".join(parts).strip()
    return expr, i


def is_statement_separator(token) -> bool:
    return bool(token) and (
        token.type == "NL" or (token.type == "WORD" and token.value == ";")
    )


def parse_value_token(tokens, i) -> Any:
    token = peek(tokens, i)
    if not token:
        return True, i
    if is_statement_separator(token):
        return True, i + 1
    expr, j = collect_until_eol(tokens, i, stop_on_block_open=True)
    if not expr:
        return True, j
    return parse_literal_value(expr), j


def unknown_property_error(token, is_component=False) -> None:
    candidates = set(CSS_PROPERTIES) | set(CSS_ALIASES) | set(HTML_ATTRIBUTES) | set(EVENTS) | set(ROUTER_KEYS)
    if is_component:
        return None
    guess = difflib.get_close_matches(token.value.lower(), sorted(candidates), n=1)
    suggestion = (
        f"Did you mean `{guess[0]}`?"
        if guess
        else "Known keys are CSS properties, HTML attributes, events, router keys, or child elements."
    )
    raise CompilerError(
        f"Unknown property or invalid child start: `{token.value}`",
        token=token,
        suggestion=suggestion,
    )


def looks_like_child_start(tokens, i) -> bool:
    token = peek(tokens, i)
    nxt = peek(tokens, i + 1)
    if not token or token.type != "WORD":
        return False
    if token.value.lower() in classify_known_keywords():
        return True
    if SCRIPT_PLACEHOLDER_RE.match(token.value):
        return True
    if not TAG_NAME_RE.match(token.value):
        return False
    if nxt and nxt.type == "BRACE" and nxt.value == "{":
        return True
    if nxt and nxt.type == "STRING":
        return True
    return False


def extract_component_load_directive(raw, base_dir) -> Any:
    """Scans a component/.tw source for top-level `load "x.tss"` / `load @x.tss`
    lines, strips them ALL out (so the main element parser never sees them),
    and returns the parsed stylesheets (or None if nothing was loaded).

    v0.8.48 (Issue 7): Previously only the FIRST `load` line was resolved and
    stripped — additional `load` lines were silently left in `raw`, tokenized as
    regular elements, and produced nothing.  Now every match is resolved and
    stripped, mirroring how `resolve_layout_loads` handles layouts."""
    matches = list(COMPONENT_LOAD_RE.finditer(raw))
    if not matches:
        return raw, None
    sheets = []
    for m in matches:
        quoted, atpath = m.group(1), m.group(2)
        load_info = resolve_load_target(quoted or atpath, base_dir, location="component load")
        if load_info["kind"] != "stylesheet":
            raise CompilerError(
                f"component load: expected a stylesheet but found `{load_info['full_path']}`",
                suggestion="Inside a component file, `load` currently supports `.tss` stylesheets.",
            )
        full_path = load_info["full_path"]
        sheets.append(build_tss_ast_from_text(read_text_file(full_path)))
    # Strip ALL load lines so the element parser never sees them
    raw = COMPONENT_LOAD_RE.sub("", raw)
    return raw, sheets


def load_component_ast(name) -> Any:
    # Built-in tw/ components — no AST file, handled at render time
    if name in _BUILTIN_TW_COMPONENTS or name.lower() in _BUILTIN_TW_COMPONENTS:
        return []
    with _CACHE_LOCK:
        if name in _COMPONENT_AST_CACHE:
            return copy.deepcopy(_COMPONENT_AST_CACHE[name])
    collect_component_dependencies(name)
    path = resolve_component_path(name)
    if not os.path.exists(path):
        raise FileNotFoundError(f"Component not found: {path}")
    raw = read_text_file(path)
    raw, comp_sheets = extract_component_load_directive(raw, os.path.dirname(path))
    if comp_sheets:
        with _CACHE_LOCK:
            _COMPONENT_STYLESHEET_PATHS[normalize_path(path)] = comp_sheets
    tokens = tokenize_tw(raw)
    nodes, _ = build_elements(tokens, 0, path, raw)
    with _CACHE_LOCK:
        _COMPONENT_AST_CACHE[name] = nodes
    return copy.deepcopy(nodes)


def load_layout(name) -> Any:
    with _CACHE_LOCK:
        if name in _LAYOUT_CACHE:
            return _LAYOUT_CACHE[name]
    path = os.path.join(LAYOUTS_DIR, f"{name}.tw")
    if not os.path.exists(path):
        raise FileNotFoundError(f"Layout not found: {path}")
    raw = read_text_file(path)

    with _CACHE_LOCK:
        meta = dict(_LAYOUT_META_CACHE.get(name) or {})
    # Scan directive: `tw@responsive true|false` (line-based)
    m = LAYOUT_RESPONSIVE_RE.search(raw or "")
    if m:
        meta["responsive"] = to_bool(parse_config_scalar(m.group(1)))
        raw = LAYOUT_RESPONSIVE_RE.sub("", raw, count=1).lstrip("\n")
    with _CACHE_LOCK:
        _LAYOUT_META_CACHE[name] = meta

    raw = resolve_layout_loads(raw, HOME_DIR)

    with _CACHE_LOCK:
        _LAYOUT_CACHE[name] = raw
    return raw


def resolve_layout_loads(raw, base_dir) -> Any:
    """Lets a layout file pull in a component (header/footer etc.) or a
    stylesheet via `load "path"` / `load @path`, so it shows on every page
    that uses this layout — without the layout needing real TW parsing.
    Paths are resolved relative to `[home]/`, same as `./components/...`
    inside a component's own `load`."""

    def repl(m) -> Any:
        quoted, atpath = m.group(1), m.group(2)
        load_info = resolve_load_target(quoted or atpath, base_dir, location="layout load")
        full_path = load_info["full_path"]

        if load_info["kind"] == "component":
            comp_raw = read_text_file(full_path)
            comp_raw, comp_sheet = extract_component_load_directive(comp_raw, os.path.dirname(full_path))
            comp_tokens = tokenize_tw(comp_raw)
            comp_nodes, _ = build_elements(comp_tokens, 0, full_path, comp_raw)
            html, _needs_router, _head = render_elements_html(comp_nodes, {}, collect_head_scripts=False)
            if comp_sheet is not None:
                html = f"<style>\n{render_css(comp_sheet, {})}</style>\n{html}"
            return html

        if load_info["kind"] != "stylesheet":
            raise CompilerError(
                f"layout load: expected a component or stylesheet but found `{full_path}`",
                suggestion="Layouts can `load` `.tw` component files and `.tss` stylesheets.",
            )
        sheet = build_tss_ast_from_text(read_text_file(full_path))
        return f"<style>\n{render_css(sheet, {})}</style>"

    return LAYOUT_LOAD_RE.sub(repl, raw)


def get_layout_meta(name: str):
    # Ensures layout is loaded at least once (populates meta cache)
    with _CACHE_LOCK:
        loaded = name in _LAYOUT_CACHE
    if not loaded:
        try:
            load_layout(name)
        except FileNotFoundError:
            # v0.8.48 (Issue A): don't propagate the raw traceback —
            # emit a clean one-line warning and return empty meta so
            # the build can continue (the page still renders, just
            # without that layout's responsive flag).
            expected = os.path.join(LAYOUTS_DIR, f"{name}.tw")
            logger.warning(
                "TW: named layout `%s` is referenced but not found "
                "(expected: %s). Create the file or remove the `layout \"%s\"` key.",
                name, expected, name,
            )
            return {}
    with _CACHE_LOCK:
        return dict(_LAYOUT_META_CACHE.get(name, {}) or {})


# ═══════════════════════════════════════════════════════════════════════════
# App Router — Layout as Component System (v0.7.0)
# ═══════════════════════════════════════════════════════════════════════════
# layout.tw files are parsed as TW components (not raw HTML templates).
# They support {children} slot where page content gets injected.
# Nested layouts compose: root → (main) → blog → page.

_LAYOUT_AST_CACHE = {}
_LAYOUT_AST_CACHE_LOCK = threading.RLock()


def load_layout_ast(file_path: str) -> Any:
    """
    Parse a layout.tw file as a TW component (PageNode).

    Unlike load_layout() which returns raw HTML string, this returns a
    PageNode with parsed body elements, head, loaded_sheets, etc.

    The layout body may contain a special `children` element or
    `{children}` text marker which gets replaced with page content.
    """
    with _LAYOUT_AST_CACHE_LOCK:
        if file_path in _LAYOUT_AST_CACHE:
            return _LAYOUT_AST_CACHE[file_path]

    if not os.path.exists(file_path):
        raise FileNotFoundError(f"Layout file not found: {file_path}")

    raw = read_text_file(file_path)
    tokens = tokenize_tw(raw)
    page = build_tw_ast(tokens, os.path.dirname(file_path), file_path, raw)
    page._tw_source_path = file_path

    # Resolve any `load` directives in the layout (stylesheets, components)
    raw_dir = os.path.dirname(file_path)
    # load directives are already handled by build_tw_ast via parse_load

    with _LAYOUT_AST_CACHE_LOCK:
        _LAYOUT_AST_CACHE[file_path] = page
    return page


def render_layout_body(layout_page: Any, children_html: str, context: dict) -> tuple:
    """
    Render a layout's body, replacing {children} with page content.

    Returns (rendered_html, needs_router_runtime, head_scripts).
    """
    body_nodes = layout_page.body

    # Split body at {children} marker
    # Look for a text node or element with "children" tag
    before_children = []
    after_children = []
    found_children = False

    for node in body_nodes:
        if not found_children:
            # Check for {children} in text nodes
            if hasattr(node, "tag") and node.tag == "text":
                text = getattr(node, "text", "")
                if "{children}" in str(text):
                    # Split text at {children}
                    parts = str(text).split("{children}", 1)
                    if parts[0].strip():
                        before_children.append(
                            type(node)(parts[0]) if hasattr(type(node), "__call__") else node
                        )
                    if len(parts) > 1 and parts[1].strip():
                        after_children.append(
                            type(node)(parts[1]) if hasattr(type(node), "__call__") else node
                        )
                    found_children = True
                    continue
                before_children.append(node)
            elif hasattr(node, "tag") and node.tag == "children":
                # Explicit <children> element
                found_children = True
                continue
            else:
                before_children.append(node)
        else:
            after_children.append(node)

    # If no {children} found, just append children at the end
    if not found_children:
        before_children = body_nodes
        after_children = []

    # Render before-children nodes
    before_html, needs_router_before, head_before = render_elements_html(
        before_children, context
    )

    # Render after-children nodes
    after_html, needs_router_after, head_after = render_elements_html(
        after_children, context
    )

    needs_router = needs_router_before or needs_router_after
    head_scripts = head_before + head_after

    rendered = before_html + after_html
    # Replace {children} markers (rendered by render_elements_html for nested children nodes)
    # with the actual page content
    if "{children}" in rendered:
        rendered = rendered.replace("{children}", children_html)
    elif children_html.strip() and children_html.strip() not in rendered:
        # No {children} marker — append children (guard against duplication)
        rendered = before_html + "\n" + children_html + "\n" + after_html
    return rendered, needs_router, head_scripts


def compose_nested_layouts(
    layout_files: list,
    page_body_html: str,
    page_title: str,
    page_head_extras: str,
    page_style_blocks: str,
    page_runtime_scripts: str,
    context: dict,
    page: Any = None,
    zero_js: bool = False,
) -> str:
    """
    Compose nested layouts around page body.

    layout_files: list of layout.tw file paths (root → innermost)
    page_body_html: rendered page body HTML
    page_title: page title
    page_head_extras: head extras from page
    page_style_blocks: style blocks from page
    page_runtime_scripts: runtime scripts from page

    Returns the final HTML document.
    """
    if not layout_files:
        # No layouts — use default document
        return build_default_document(
            page_title,
            page_head_extras,
            page_style_blocks,
            page_body_html,
            page_runtime_scripts,
            page=page,
            context=context,
            zero_js=zero_js,
        )

    # Start with page body as the innermost content
    children_html = page_body_html
    all_head_extras = page_head_extras
    all_style_blocks = page_style_blocks
    all_runtime_scripts = page_runtime_scripts
    accumulated_head_scripts = []
    needs_router = False

    # Compose layouts from innermost to outermost
    for layout_file in reversed(layout_files):
        try:
            layout_page = load_layout_ast(layout_file)
        except Exception as e:
            logger.exception("Failed to load layout: %s", layout_file)
            continue

        # Merge layout's loaded sheets into style blocks
        if layout_page.loaded_sheets:
            _layout_sheets = _dedupe_loaded_sheets(layout_page.loaded_sheets)
            layout_css = "\n\n".join(
                render_css(sheet, context) for sheet in _layout_sheets
            )
            all_style_blocks = f"  <style>\n{layout_css}\n  </style>\n" + all_style_blocks

        # Merge layout's head
        layout_head_extras = render_head_extras(layout_page.head, context)
        all_head_extras = layout_head_extras + all_head_extras

        # Render layout body with {children} replaced
        rendered_body, layout_needs_router, layout_head = render_layout_body(
            layout_page, children_html, context
        )

        if layout_needs_router:
            needs_router = True
        accumulated_head_scripts = layout_head + accumulated_head_scripts

        children_html = rendered_body

    # The outermost layout provides the document structure
    outermost_layout = load_layout_ast(layout_files[0])

    # Build the final document
    meta_html, data_script, build_comments = _build_tw_signature(page, context, zero_js=zero_js)
    enhanced_head = (meta_html + data_script + "".join(accumulated_head_scripts) + all_head_extras).rstrip()

    # Check if outermost layout has page block with title
    layout_title = outermost_layout.title or page_title

    # Build final HTML document
    style_block = all_style_blocks.rstrip()
    scripts = all_runtime_scripts or ""

    if needs_router and not zero_js:
        scripts = scripts + f'\n<script src="{get_router_runtime_url()}"></script>'

    final_html = f"""{build_comments}<!DOCTYPE html>
<html lang="en">
<head>
{enhanced_head}
  <title>{html_escape(layout_title)}</title>
{style_block}
</head>
<body>
{children_html}
{scripts}
</body>
</html>"""

    # Apply reactivity if needed
    if page and not zero_js:
        raw_source = ""
        try:
            if getattr(page, "_tw_source_path", ""):
                raw_source = read_text_file(page._tw_source_path)
        except (OSError, UnicodeDecodeError):
            raw_source = ""

        from .reactivity import has_reactivity, parse_state_block
        reactive_enabled = bool(raw_source and has_reactivity(raw_source))
        page_state = getattr(page, "state_vars", {}) or {}
        if reactive_enabled:
            page_state.update(parse_state_block(raw_source))

        if page_state or reactive_enabled:
            final_html = _inject_reactivity_runtime(final_html, raw_source, page_state)

        on_load = getattr(page, "on_load_inits", []) or []
        if on_load:
            final_html = _inject_on_load_inits(final_html, on_load)

    return final_html


def load_external_stylesheet(rel_path, base_dir) -> Any:
    full_path = resolve_source_path(rel_path, base_dir)
    if not os.path.exists(full_path):
        raise FileNotFoundError(f"load: stylesheet not found -> {full_path}")
    return build_tss_ast_from_text(read_text_file(full_path))


def write_chunk(content, ext) -> Any:
    if MINIFY_OUTPUT and ext == "js":
        content = minify_js_content(content)
    digest = content_hash(content, length=8)
    with _CHUNK_LOCK:
        if digest in _CHUNK_CACHE:
            # LRU update
            _CHUNK_CACHE.move_to_end(digest)
            return _CHUNK_CACHE[digest]
        fname = f"{digest}.{ext}"
        os.makedirs(CHUNKS_DIR, exist_ok=True)
        out_path = os.path.join(CHUNKS_DIR, fname)
        try:
            # Atomic create: avoids TOCTOU between exists() and write.
            with open(out_path, "x", encoding="utf-8") as f:
                f.write(content)
        except FileExistsError:
            pass
        url = CHUNKS_URL_PREFIX + fname
        _CHUNK_CACHE[digest] = url
        _CHUNK_CACHE.move_to_end(digest)
        # Bound cache size (configurable via env)
        max_raw = os.environ.get("TW_CHUNK_CACHE_MAX", "").strip()
        max_entries = _CHUNK_CACHE_MAX_DEFAULT
        if max_raw:
            try:
                max_entries = int(max_raw)
            except ValueError:
                max_entries = _CHUNK_CACHE_MAX_DEFAULT
        max_entries = max(0, int(max_entries))
        if max_entries and len(_CHUNK_CACHE) > max_entries:
            while max_entries and len(_CHUNK_CACHE) > max_entries:
                _CHUNK_CACHE.popitem(last=False)
        return url


def _parse_es6_import(tokens, i) -> Any:
    """Parse ES6 import: import { fn1, fn2 } from "@/lib/file"."""
    i += 1  # skip {
    names = []
    while i < len(tokens):
        tok = peek(tokens, i)
        if not tok:
            raise CompilerError("Unterminated ES6 import")
        if tok.type == "BRACE" and tok.value == "}":
            i += 1
            break
        if tok.type == "WORD":
            names.append(tok.value)
        i += 1
    from_tok = peek(tokens, i)
    if not from_tok or from_tok.type != "WORD" or from_tok.value != "from":
        raise CompilerError("Expected `from` after import names",
            token=from_tok, suggestion='import { name } from "path"')
    i += 1
    path_tok = peek(tokens, i)
    if not path_tok or path_tok.type != "STRING":
        raise CompilerError("Expected path after `from`",
            token=path_tok, suggestion='import { fn } from "@/lib/file"')
    i += 1
    try:
        _ES6_IMPORTS.append({"names": names, "path": path_tok.value})
    except NameError:
        pass
    return None, i


def parse_import(tokens, i) -> Any:
    i += 1
    token = peek(tokens, i)
    # v0.8.43: ES6 import { fn } from "path"
    if token and token.type == "BRACE" and token.value == "{":
        return _parse_es6_import(tokens, i)
    # v0.8.48: ES6-style default import: import Image from "tw/image"
    # (previously only the bare-string form `import "tw/image"` worked, but
    #  docs/examples show the `from` form — see bug #3).
    if token and token.type == "WORD" and token.value not in {"let", "if", "for", "each", "import", "children"}:
        next_tok = peek(tokens, i + 1)
        if next_tok and next_tok.type == "WORD" and next_tok.value == "from":
            path_tok = peek(tokens, i + 2)
            if not path_tok or path_tok.type != "STRING":
                raise CompilerError("Expected path after `from`",
                    token=path_tok, suggestion='import Image from "tw/image"')
            name = path_tok.value
            end_i = i + 3
            if name in _BUILTIN_TW_COMPONENTS or name.lower() in _BUILTIN_TW_COMPONENTS:
                return None, end_i
            if not component_exists(name):
                raise CompilerError(
                    f"Imported component not found: `{name}`",
                    token=path_tok,
                    suggestion=f"Expected file: `{os.path.join(COMPONENTS_DIR, name + '.tw')}`",
                )
            load_component_ast(name)
            return None, end_i
    if not token or token.type != "STRING":
        raise CompilerError("Expected component name after `import`", token=peek(tokens, i - 1))
    name = token.value
    # Built-in tw/ components (tw/image, etc.) — skip file resolution
    if name in _BUILTIN_TW_COMPONENTS or name.lower() in _BUILTIN_TW_COMPONENTS:
        return None, i + 1
    if not component_exists(name):
        raise CompilerError(
            f"Imported component not found: `{name}`",
            token=token,
            suggestion=f"Expected file: `{os.path.join(COMPONENTS_DIR, name + '.tw')}`",
        )
    load_component_ast(name)
    return None, i + 1


def _collect_used_component_names(nodes, found=None) -> Any:
    found = found or set()
    for node in nodes or []:
        if getattr(node, "tag", "") == "__component__" and getattr(node, "name", ""):
            found.add(node.name)
        _collect_used_component_names(getattr(node, "children", []) or [], found)
        _collect_used_component_names(getattr(node, "else_children", []) or [], found)
    return found



# --- Lib function execution ---
_LIB_MODULES = {}


def register_lib_module(source, module_id=""):
    try:
        from .twm_parser import parse_twm_functions
        _result = parse_twm_functions(source)
        funcs = _result["functions"] if isinstance(_result, dict) else _result
        with _LIB_LOCK:
            for fn in funcs:
                _LIB_MODULES[fn["name"]] = {
                    "source": source,
                    "module_id": module_id or fn["name"],
            }
    except Exception:
        pass


def _try_execute_lib_function(func_name, raw_args, token=None):
    if func_name not in _LIB_MODULES:
        return func_name + "(" + raw_args + ")"
    mod_info = _LIB_MODULES[func_name]
    try:
        result = execute_lib_function(
            mod_info["source"],
            func_name,
            raw_args,
            module_id=mod_info["module_id"],
        )
        return result
    except LibExecutionError as exc:
        raise CompilerError(
            "Lib function error: " + exc.message,
            token=token,
            suggestion=exc.suggestion or "Check the .twm lib file for errors.",
            code="TW2401",
        )


VALID_TYPES = {"string", "number", "boolean", "array", "object", "null", "any"}


def infer_value_type(value) -> str:
    """Map a Python value to a TW type name."""
    if value is None:
        return "null"
    if isinstance(value, bool):
        return "boolean"
    if isinstance(value, (int, float)):
        return "number"
    if isinstance(value, str):
        return "string"
    if isinstance(value, (list, tuple)):
        return "array"
    if isinstance(value, dict):
        return "object"
    return "any"


def check_type_annotation(type_annotation, value, token=None, name=None) -> None:
    """Validate that `value` is compatible with `type_annotation`.

    Raises CompilerError on mismatch. `any` always passes.
    """
    if type_annotation is None or type_annotation == "any":
        return
    actual = infer_value_type(value)
    # `null` is compatible with `object`, `array`, `null`, and `any`
    if actual == "null" and type_annotation in {"object", "array", "null", "any"}:
        return
    if actual != type_annotation:
        label = f"`{name}`" if name else "value"
        raise CompilerError(
            f"Type error: {label} is annotated as `{type_annotation}` but got `{actual}`.",
            token=token,
            suggestion=f"Change the value to match `{type_annotation}`, or update the annotation.",
        )


def parse_let(tokens, i) -> Any:
    start = peek(tokens, i)
    i += 1
    name_token = peek(tokens, i)
    if not name_token or name_token.type != "WORD":
        raise CompilerError("Expected variable name after `let`", token=start)
    i += 1

    # Optional type annotation: `let name: type = value`
    type_annotation = None
    if peek(tokens, i) and peek(tokens, i).type == "WORD" and peek(tokens, i).value == ":":
        i += 1  # consume ":"
        type_token = peek(tokens, i)
        if not type_token or type_token.type != "WORD":
            raise CompilerError("Expected type name after `:`", token=peek(tokens, i - 1))
        type_name = type_token.value.lower()
        if type_name not in VALID_TYPES:
            raise CompilerError(
                f"Unknown type `{type_token.value}`. Valid types: {', '.join(sorted(VALID_TYPES))}",
                token=type_token,
            )
        type_annotation = type_name
        i += 1

    if peek(tokens, i) and peek(tokens, i).type == "WORD" and peek(tokens, i).value == "=":
        i += 1
    value, i = parse_value_token(tokens, i)

    # If value is a string that looks like a function call, try to execute it
    if isinstance(value, str):
        call_info = is_function_call(value)
        if call_info:
            value = _try_execute_lib_function(call_info["name"], call_info["raw_args"], name_token)

    # Type-check the value against the annotation at parse time
    if type_annotation:
        check_type_annotation(type_annotation, value, name_token, name_token.value)

    return LetNode(name_token.value, value, type_annotation=type_annotation), i


def parse_if(tokens, i, file_path, source) -> Any:
    start = peek(tokens, i)
    i += 1
    condition, i = collect_until_block(tokens, i)
    if not condition:
        raise CompilerError("Missing condition in `if` block", token=start)
    if not peek(tokens, i) or peek(tokens, i).type != "BRACE" or peek(tokens, i).value != "{":
        raise CompilerError("Expected `{` after `if` condition", token=peek(tokens, i - 1))
    i += 1
    node = IfNode(condition)
    node.children, i = build_elements(tokens, i, file_path, source, require_closing_brace=True, start_token=start)
    if peek(tokens, i) and peek(tokens, i).type == "WORD" and peek(tokens, i).value == "else":
        i += 1
        if not peek(tokens, i) or peek(tokens, i).type != "BRACE" or peek(tokens, i).value != "{":
            raise CompilerError("Expected `{` after `else`", token=peek(tokens, i - 1))
        i += 1
        node.else_children, i = build_elements(tokens, i, file_path, source, require_closing_brace=True, start_token=start)
    return node, i


def parse_for(tokens, i, file_path, source) -> Any:
    start = peek(tokens, i)
    i += 1
    var_token = peek(tokens, i)
    if not var_token or var_token.type != "WORD":
        raise CompilerError("Expected loop variable after `for`", token=start)
    i += 1
    if not peek(tokens, i) or peek(tokens, i).type != "WORD" or peek(tokens, i).value != "in":
        raise CompilerError("Expected `in` inside `for` loop", token=peek(tokens, i))
    i += 1
    list_expr, i = collect_until_block(tokens, i)
    if not list_expr:
        raise CompilerError("Expected iterable expression after `in`", token=peek(tokens, i - 1))
    if not peek(tokens, i) or peek(tokens, i).type != "BRACE" or peek(tokens, i).value != "{":
        raise CompilerError("Expected `{` after `for ... in ...`", token=peek(tokens, i - 1))
    i += 1
    node = ForNode(var_token.value, list_expr)
    node.children, i = build_elements(tokens, i, file_path, source, require_closing_brace=True, start_token=start)
    return node, i


def parse_each(tokens, i, file_path, source) -> Any:
    """
    Syntax sugar:
      each links as link { ... }
    Equivalent to:
      for link in links { ... }
    """
    start = peek(tokens, i)
    i += 1

    # collect expr until `as`
    expr_parts = []
    while i < len(tokens):
        tok = peek(tokens, i)
        if tok.type == "NL":
            i += 1
            continue
        if tok.type == "WORD" and tok.value == "as":
            break
        if tok.type == "BRACE":
            raise CompilerError("Expected `as <var>` inside `each`", token=tok)
        expr_parts.append(tok.value if tok.type == "WORD" else json.dumps(tok.value))
        i += 1

    if not expr_parts:
        raise CompilerError("Expected iterable expression after `each`", token=start)
    list_expr = " ".join(expr_parts).strip()

    if not peek(tokens, i) or peek(tokens, i).type != "WORD" or peek(tokens, i).value != "as":
        raise CompilerError("Expected `as` inside `each`", token=peek(tokens, i) or start)
    i += 1

    var_token = peek(tokens, i)
    if not var_token or var_token.type != "WORD":
        raise CompilerError("Expected loop variable after `as`", token=peek(tokens, i - 1))
    i += 1

    if not peek(tokens, i) or peek(tokens, i).type != "BRACE" or peek(tokens, i).value != "{":
        raise CompilerError("Expected `{` after `each ... as ...`", token=peek(tokens, i - 1))
    i += 1

    node = ForNode(var_token.value, list_expr)
    node.children, i = build_elements(tokens, i, file_path, source, require_closing_brace=True, start_token=start)
    return node, i


def _try_parse_script_tag_config(raw_body: str, *, token=None) -> Any:
    """
    Detect and parse:
      script { src "..." strategy afterInteractive|beforeInteractive|lazyOnload }

    Returns (src, strategy) when the body looks like a declarative config block.
    Otherwise returns None (treat as legacy raw-JS script body).
    """
    body = str(raw_body or "")
    # Quick sniff: config blocks must mention `src`.
    if "src" not in body:
        return None

    allowed_keys = {
        "src",
        "strategy",
        "id",
        "async",
        "defer",
        "type",
        "crossorigin",
        "integrity",
        "referrerpolicy",
    }
    cfg = {}
    try:
        inner_tokens = tokenize(body, allow_inline_scripts=False)
    except Exception:
        return None

    i = 0
    while i < len(inner_tokens):
        tok = inner_tokens[i]
        if tok.type == "NL":
            i += 1
            continue
        if tok.type != "WORD":
            return None
        key = tok.value
        if key not in allowed_keys:
            return None
        i += 1
        if i < len(inner_tokens) and inner_tokens[i].type == "WORD" and inner_tokens[i].value == "=":
            i += 1
        if i >= len(inner_tokens):
            raise CompilerError(f"Missing value for `{key}` inside `script {{ ... }}`", token=token)
        val_tok = inner_tokens[i]
        if val_tok.type not in {"WORD", "STRING"}:
            return None
        value = val_tok.value
        i += 1
        cfg[key] = value

    if "src" not in cfg:
        return None
    strategy = str(cfg.get("strategy") or "afterInteractive").strip()
    # Normalize (case-insensitive)
    strategy_l = strategy.lower()
    if strategy_l == "beforeinteractive":
        strategy = "beforeInteractive"
    elif strategy_l == "afterinteractive":
        strategy = "afterInteractive"
    elif strategy_l in {"lazyonload", "lazy_onload"}:
        strategy = "lazyOnload"
    else:
        raise CompilerError(
            f"Invalid `script` strategy: `{strategy}`",
            token=token,
            suggestion="Use `beforeInteractive`, `afterInteractive`, or `lazyOnload`.",
        )
    return str(cfg["src"]), strategy


def parse_script_placeholder(tokens, i, file_path=None) -> Any:
    token = peek(tokens, i)
    m = SCRIPT_PLACEHOLDER_RE.match(token.value)
    if not m:
        raise CompilerError("Invalid script placeholder", token=token)
    uid = int(m.group(1))
    raw_body = INLINE_SCRIPTS.get(uid, "")
    parsed = _try_parse_script_tag_config(raw_body, token=token)
    if parsed:
        src, strategy = parsed
        return ScriptTagNode(src, strategy=strategy, token=token, file_path=file_path), i + 1
    return ScriptNode(raw_body, token=token, file_path=file_path), i + 1


def parse_twm_script_placeholder(tokens, i) -> Any:
    token = peek(tokens, i)
    m = TWM_SCRIPT_PLACEHOLDER_RE.match(token.value)
    if not m:
        raise CompilerError("Invalid TWM script placeholder", token=token)
    uid = int(m.group(1))
    return INLINE_TWM_SCRIPTS.get(uid, ""), i + 1


def parse_property_value(tokens, i) -> Any:
    tok = peek(tokens, i)
    if not tok or tok.type in {"NL"}:
        return True, i + (1 if tok and tok.type == "NL" else 0)
    if tok.type == "BRACE" and tok.value == "}":
        return True, i

    # Fast path: single token value.
    # A quoted STRING value is always complete on its own — its boundaries
    # are the quote marks, so it never needs line-greedy collection. This
    # matters for single-line elements with multiple properties, e.g.
    # `a { href "/" target "_blank" text "Home" }` — without this, `href`
    # would swallow every token through the rest of the line.
    if tok.type == "STRING":
        return tok.value, i + 1

    nxt = peek(tokens, i + 1)
    if tok.type == "WORD" and (not nxt or nxt.type in {"NL"} or (nxt.type == "BRACE" and nxt.value == "}")):
        return tok.value, i + 1

    expr, j = collect_until_eol(tokens, i, stop_on_block_open=False)
    return expr, j


def parse_element_or_component(tokens, i, file_path, source) -> Any:
    token = peek(tokens, i)
    name = token.value
    i += 1
    text = None
    if peek(tokens, i) and peek(tokens, i).type == "STRING":
        text = peek(tokens, i).value
        i += 1

    # Component names are expected to start with an uppercase letter.
    # This also avoids false positives on case-insensitive filesystems
    # (for example Android/Termux shared storage), where the HTML tag
    # `header` could otherwise match `Header.tw` and cause recursion.
    is_explicit_component_name = (
        bool(name)
        and (name[0].isupper() or "/" in name or "\\" in name)
    )

    if is_explicit_component_name and component_exists(name):
        node = ComponentNode(name, token=token, file_path=file_path)
        if peek(tokens, i) and peek(tokens, i).type == "BRACE" and peek(tokens, i).value == "{":
            i += 1
            i = parse_component_block(tokens, i, node, file_path, source)
        elif text is not None:
            node.props.append(("text", text))
        return node, i

    # Treat unknown Capitalized tags as HTML tags (auto-lowercase).
    # Example: `Section { ... }` -> `<section>...</section>`
    node = ElementNode(name.lower(), text, token=token, file_path=file_path)
    if peek(tokens, i) and peek(tokens, i).type == "BRACE" and peek(tokens, i).value == "{":
        i += 1
        i = parse_element_block(tokens, i, node, file_path, source)
    return node, i


def parse_child_statement(tokens, i, file_path, source) -> Any:
    token = peek(tokens, i)
    if not token:
        return None, i
    if token.type == "BRACE" and token.value == "}":
        return None, i
    if token.type == "WORD" and token.value.startswith("<") and token.value.endswith(">"):
        raise CompilerError(
            f"HTML-like tag syntax not supported: `{token.value}`",
            token=token,
            suggestion="Do not use angle brackets. In TW write: `nav { ... }`, `section { ... }` (without `<` `>`).",
        )
    if token.type == "WORD" and token.value == "import":
        return parse_import(tokens, i)
    if token.type == "WORD" and token.value == "let":
        return parse_let(tokens, i)
    if token.type == "WORD" and token.value == "if":
        return parse_if(tokens, i, file_path, source)
    if token.type == "WORD" and token.value == "for":
        return parse_for(tokens, i, file_path, source)
    if token.type == "WORD" and token.value == "each":
        return parse_each(tokens, i, file_path, source)
    if token.type == "WORD" and token.value == "children":
        # App Router: children marker inside body or element block
        node = ElementNode("children", token=token, file_path=file_path)
        i += 1
        # Skip optional braces
        if peek(tokens, i) and peek(tokens, i).type == "BRACE" and peek(tokens, i).value == "{":
            i += 1
            depth = 1
            while i < len(tokens) and depth > 0:
                t = peek(tokens, i)
                if t.type == "BRACE" and t.value == "{":
                    depth += 1
                elif t.type == "BRACE" and t.value == "}":
                    depth -= 1
                i += 1
        return node, i
    if token.type == "WORD" and SCRIPT_PLACEHOLDER_RE.match(token.value):
        return parse_script_placeholder(tokens, i, file_path=file_path)
    if token.type == "WORD" and TAG_NAME_RE.match(token.value):
        return parse_element_or_component(tokens, i, file_path, source)
    raise CompilerError(f"Unexpected token: `{token.value}`", token=token)


def _is_comma(tok) -> bool:
    """Return True if *tok* is a comma separator (``WORD`` with value ``,``)."""
    return bool(tok) and tok.type == "WORD" and tok.value == ","


def _handle_comma_after_value(tokens, i, node) -> int:
    """After a property value, if the next token is a comma, skip it and
    optionally consume a following STRING as ``node.text``.

    This enables the ergonomic comma-separated syntax::

        span { class "badge", "Premium" }
        a { class "btn", href "/search", "Search Now" }

    Returns the updated index.
    """
    tok = peek(tokens, i)
    if not _is_comma(tok):
        return i
    i += 1  # skip comma
    nxt = peek(tokens, i)
    if nxt and nxt.type == "STRING":
        node.text = nxt.value
        i += 1
    return i


def parse_element_block(tokens, i, node, file_path, source) -> Any:
    while i < len(tokens):
        token = peek(tokens, i)
        if is_statement_separator(token):
            i += 1
            continue
        if token.type == "BRACE" and token.value == "}":
            return i + 1

        # Comma separator (e.g. trailing comma or between attribute + text)
        if _is_comma(token):
            i += 1
            nxt = peek(tokens, i)
            if nxt and nxt.type == "STRING":
                node.text = nxt.value
                i += 1
            continue

        if token.type == "WORD" and token.value == "text":
            i += 1
            raw_value, i = parse_property_value(tokens, i)
            node.text = raw_value if raw_value is not True else ""
            i = _handle_comma_after_value(tokens, i, node)
            continue

        if token.type == "WORD" and token.value in {"let", "if", "for", "each", "import", "children"}:
            child, i = parse_child_statement(tokens, i, file_path, source)
            if child:
                node.children.append(child)
            continue

        if token.type == "WORD" and SCRIPT_PLACEHOLDER_RE.match(token.value):
            child, i = parse_script_placeholder(tokens, i, file_path=file_path)
            node.children.append(child)
            continue

        if token.type == "WORD":
            # If the token looks like an element/component start (eg `input { ... }`),
            # prefer parsing it as a child node even when it collides with prop names
            # (events like `input`, router keys like `link`, etc).
            next_token = peek(tokens, i + 1)
            next_next_token = peek(tokens, i + 2)
            if next_token and next_token.type == "BRACE" and next_token.value == "{":
                child, i = parse_child_statement(tokens, i, file_path, source)
                if child:
                    node.children.append(child)
                continue
            if next_token and next_token.type == "STRING" and next_next_token and next_next_token.type == "BRACE" and next_next_token.value == "{":
                child, i = parse_child_statement(tokens, i, file_path, source)
                if child:
                    node.children.append(child)
                continue

            kind = classify_known_prop(token.value)
            if kind != "unknown":
                prop_name = token.value
                i += 1
                raw_value, i = parse_property_value(tokens, i)
                if kind == "css":
                    node.inline_style.append((normalize_css_prop(prop_name), raw_value))
                elif kind == "event":
                    ev = prop_name.lower()
                    if ev.startswith("on") and ev[2:] in EVENTS:
                        ev = ev[2:]
                    node.events.append((ev, raw_value))
                elif kind == "router":
                    node.router[prop_name.lower()] = raw_value
                else:
                    node.attrs.append((normalize_attr_name(prop_name), raw_value))
                i = _handle_comma_after_value(tokens, i, node)
                continue

            if looks_like_child_start(tokens, i):
                child, i = parse_child_statement(tokens, i, file_path, source)
                if child:
                    node.children.append(child)
                continue

            unknown_property_error(token)

        raise CompilerError(f"Unexpected token inside `{node.tag}` block: `{token.value}`", token=token)

    raise CompilerError(
        f"Missing closing `}}` for `{node.tag}` block",
        token=getattr(node, "token", None) or peek(tokens, max(len(tokens) - 1, 0)),
        file_path=getattr(node, "file_path", None) or file_path,
        suggestion="An opening `{` was found but the matching `}` is missing. Check your brace count.",
    )


def parse_component_block(tokens, i, node, file_path, source) -> Any:
    while i < len(tokens):
        token = peek(tokens, i)
        if is_statement_separator(token):
            i += 1
            continue
        if token.type == "BRACE" and token.value == "}":
            return i + 1

        # Comma separator (e.g. trailing comma or between prop + text)
        if _is_comma(token):
            i += 1
            nxt = peek(tokens, i)
            if nxt and nxt.type == "STRING":
                node.props.append(("text", nxt.value))
                i += 1
            continue

        if token.type == "WORD" and token.value in {"let", "if", "for", "each", "import", "children"}:
            child, i = parse_child_statement(tokens, i, file_path, source)
            if child:
                node.children.append(child)
            continue

        if token.type == "WORD" and SCRIPT_PLACEHOLDER_RE.match(token.value):
            child, i = parse_script_placeholder(tokens, i, file_path=file_path)
            node.children.append(child)
            continue

        if token.type == "WORD":
            next_token = peek(tokens, i + 1)
            next_next_token = peek(tokens, i + 2)
            if next_token and next_token.type == "BRACE" and next_token.value == "{":
                child, i = parse_child_statement(tokens, i, file_path, source)
                if child:
                    node.children.append(child)
                continue
            if token.value in {"let", "if", "for", "each", "import", "children"} or SCRIPT_PLACEHOLDER_RE.match(token.value):
                child, i = parse_child_statement(tokens, i, file_path, source)
                if child:
                    node.children.append(child)
                continue
            if next_token and next_token.type == "STRING" and next_next_token and next_next_token.type == "BRACE" and next_next_token.value == "{":
                child, i = parse_child_statement(tokens, i, file_path, source)
                if child:
                    node.children.append(child)
                continue

            key = token.value
            i += 1
            value, i = parse_property_value(tokens, i)
            node.props.append((key, value))
            # Handle comma after prop value — next string becomes "text" prop
            tok = peek(tokens, i)
            if _is_comma(tok):
                i += 1
                nxt = peek(tokens, i)
                if nxt and nxt.type == "STRING":
                    node.props.append(("text", nxt.value))
                    i += 1
            continue

        raise CompilerError(f"Unexpected token inside component `{node.name}`: `{token.value}`", token=token)

    raise CompilerError(
        f"Missing closing `}}` for component `{node.name}` block",
        token=getattr(node, "token", None) or peek(tokens, max(len(tokens) - 1, 0)),
        file_path=getattr(node, "file_path", None) or file_path,
        suggestion="An opening `{` was found but the matching `}` is missing. Check your brace count.",
    )


def build_elements(tokens, i, file_path, source, require_closing_brace=False, start_token=None) -> Any:
    nodes = []
    while i < len(tokens):
        token = peek(tokens, i)
        if is_statement_separator(token):
            i += 1
            continue
        if token.type == "BRACE" and token.value == "}":
            return nodes, i + 1
        node, i = parse_child_statement(tokens, i, file_path, source)
        if node:
            nodes.append(node)
    if require_closing_brace:
        raise CompilerError(
            "Missing closing `}` for block",
            token=start_token or peek(tokens, max(len(tokens) - 1, 0)),
            file_path=file_path,
            suggestion="An opening `{` was found but the matching `}` is missing. Check your brace count.",
        )
    return nodes, i


def parse_head_block(tokens, i, head) -> Any:
    while i < len(tokens):
        token = peek(tokens, i)
        if is_statement_separator(token):
            i += 1
            continue
        if token.type == "BRACE" and token.value == "}":
            return i + 1

        if token.type == "WORD" and token.value == "meta":
            i += 1
            attrs = {}
            if not peek(tokens, i) or peek(tokens, i).type != "BRACE" or peek(tokens, i).value != "{":
                raise CompilerError("Expected `{` after `meta`", token=peek(tokens, i - 1))
            i += 1
            while i < len(tokens):
                tok = peek(tokens, i)
                if tok.type == "BRACE" and tok.value == "}":
                    i += 1
                    break
                # v0.8.48 (bug #5): commas between attributes, as shown in the
                # docs (`name "viewport", content "..."`), were previously
                # swallowed as a literal `,` key, corrupting the output.
                # Treat a bare comma as an optional separator, same as `;`/newline.
                if is_statement_separator(tok) or (tok.type == "WORD" and tok.value == ","):
                    i += 1
                    continue
                if tok.type != "WORD":
                    raise CompilerError("Invalid meta key", token=tok)
                key = tok.value
                i += 1
                value, i = parse_property_value(tokens, i)
                attrs[key] = value
            head.metas.append(attrs)
            continue

        if token.type == "WORD" and token.value == "icon":
            i += 1
            value, i = parse_property_value(tokens, i)
            head.icon = value
            continue

        if token.type == "WORD" and token.value == "seo":
            i += 1
            if not peek(tokens, i) or peek(tokens, i).type != "BRACE" or peek(tokens, i).value != "{":
                raise CompilerError("Expected `{` after `seo`", token=peek(tokens, i - 1))
            i += 1
            while i < len(tokens):
                tok = peek(tokens, i)
                if tok.type == "BRACE" and tok.value == "}":
                    i += 1
                    break
                if is_statement_separator(tok) or (tok.type == "WORD" and tok.value == ","):
                    i += 1
                    continue
                if tok.type != "WORD":
                    raise CompilerError("Invalid SEO key", token=tok)
                key = tok.value
                i += 1
                value, i = parse_property_value(tokens, i)
                head.seo[key] = value
            continue

        raise CompilerError(f"Unexpected token inside `head`: `{token.value}`", token=token)

    raise CompilerError(
        "Missing closing `}` for `head` block",
        token=peek(tokens, max(len(tokens) - 1, 0)),
        suggestion="The closing `}` for `head { ... }` appears to be missing.",
    )


def parse_page_block(tokens, i, page) -> Any:
    while i < len(tokens):
        token = peek(tokens, i)
        if is_statement_separator(token):
            i += 1
            continue
        if token.type == "BRACE" and token.value == "}":
            return i + 1

        if token.type != "WORD":
            raise CompilerError("Invalid token inside `page` block", token=token)

        key = token.value
        i += 1
        value, i = parse_property_value(tokens, i)

        if key == "title":
            page.title = str(value)
            continue
        if key == "layout":
            # v0.8.48: The named-layout system (layout "x" + [home]/layouts/x.tw)
            # is DEPRECATED in favor of file-based layouts (layout.tw in route
            # dirs). It still works but emits a deprecation warning guiding
            # users to the file-based system. (Proposal: deprecate named layouts)
            import warnings as _warnings
            _warnings.warn(
                f"`layout \"{value}\"` (named layout) is deprecated. "
                f"Use file-based layouts instead: place a `layout.tw` in the "
                f"route directory ([home]/ or [home]/(group)/). "
                f"See the Layouts section in the README.",
                DeprecationWarning,
                stacklevel=2,
            )
            logger.warning(
                "TW: `layout \"%s\"` (named layout) is deprecated. "
                "Use file-based layouts (layout.tw in route dirs) instead.",
                value,
            )
            # Allow multiple layout layers:
            # 1) repeated `layout` keys inside the same `page {}` block
            # 2) `layout "base,docs"` or `layout "base > docs"` style chains
            for name in parse_layout_chain(value):
                page.layouts.append(name)
                page.layout = name
            continue
        if key == "render":
            render_mode = str(value).lower()
            if render_mode not in {"static", "server", "edge", "interactive", "dynamic", "csr"}:
                raise CompilerError(
                    f"Unsupported render mode: `{render_mode}`",
                    token=token,
                    suggestion="Use `static`, `interactive` (VDOM), `csr` (React), `server`, or `edge`.",
                )
            page.render_mode = render_mode
            continue
        if key == "revalidate":
            page.revalidate = parse_config_scalar(value)
            continue
        if key == "cache_by":
            page.cache_by = re.sub(r"\s*:\s*", ":", str(value).strip())
            continue
        if key == "cache_size":
            page.cache_size = parse_config_scalar(value)
            continue
        if key == "redirect":
            page.redirect_to = str(value)
            continue
        if key == "rewrite":
            page.rewrite_to = str(value)
            continue
        if key == "generateStaticParams":
            page.generate_static_params = str(value)
            continue

        raise CompilerError(
            f"Unknown key inside `page`: `{key}`",
            token=token,
            suggestion="Use `title`, `layout`, `render`, `revalidate`, `cache_by`, `cache_size`, `redirect`, `rewrite`, or `generateStaticParams`.",
        )
    raise CompilerError(
        "Missing closing `}` for `page` block",
        token=peek(tokens, max(len(tokens) - 1, 0)),
        suggestion="The closing `}` for `page { ... }` appears to be missing.",
    )


def build_tw_ast(tokens, base_dir, file_path, source) -> Any:
    page = PageNode()
    i = 0
    while i < len(tokens):
        token = peek(tokens, i)
        if is_statement_separator(token):
            i += 1
            continue

        if token.type == "WORD" and TWM_SCRIPT_PLACEHOLDER_RE.match(token.value):
            raw_module, i = parse_twm_script_placeholder(tokens, i)
            if raw_module and str(raw_module).strip():
                page.local_modules.append(str(raw_module))
            continue

        # Optional: enable responsive helpers at page-level too
        if token.type == "WORD" and token.value.lower() == "tw@responsive":
            i += 1
            if peek(tokens, i) and peek(tokens, i).type == "WORD" and peek(tokens, i).value == "=":
                i += 1
            value_tok = peek(tokens, i)
            if not value_tok or value_tok.type not in {"WORD", "STRING"}:
                raise CompilerError("Expected `true` or `false` after `tw@responsive`", token=token)
            page.responsive = to_bool(parse_config_scalar(value_tok.value))
            i += 1
            continue

        if token.type == "WORD" and token.value.upper() == "TITLE":
            i += 1
            if not peek(tokens, i) or peek(tokens, i).type != "STRING":
                raise CompilerError("Expected string after `TITLE`", token=peek(tokens, i - 1))
            page.title = peek(tokens, i).value
            i += 1
            continue

        if token.type == "WORD" and token.value == "page":
            i += 1
            if not peek(tokens, i) or peek(tokens, i).type != "BRACE" or peek(tokens, i).value != "{":
                raise CompilerError("Expected `{` after `page`", token=peek(tokens, i - 1))
            i += 1
            i = parse_page_block(tokens, i, page)
            continue

        if token.type == "WORD" and token.value == "layout":
            i += 1
            if not peek(tokens, i) or peek(tokens, i).type not in {"STRING", "WORD"}:
                raise CompilerError("Expected layout name after `layout`", token=peek(tokens, i - 1))
            # v0.8.48: named-layout deprecation warning (second parser path)
            _layout_val = peek(tokens, i).value
            logger.warning(
                "TW: `layout \"%s\"` (named layout) is deprecated. "
                "Use file-based layouts (layout.tw in route dirs) instead.",
                _layout_val,
            )
            for name in parse_layout_chain(_layout_val):
                page.layouts.append(name)
                page.layout = name
            i += 1
            continue

        # Explicit lifecycle hook (useEffect-equivalent, but explicit).
        # Syntax:
        #   on load init <handlerName>
        if token.type == "WORD" and token.value == "on":
            t1 = peek(tokens, i + 1)
            t2 = peek(tokens, i + 2)
            t3 = peek(tokens, i + 3)
            if t1 and t2 and t3 and t1.type == "WORD" and t2.type == "WORD" and t3.type == "WORD":
                if t1.value == "load" and t2.value == "init":
                    i += 3
                    handler_tok = peek(tokens, i)
                    if not handler_tok or handler_tok.type != "WORD":
                        raise CompilerError("Expected handler name after `on load init`", token=peek(tokens, i - 1))
                    page.on_load_inits.append(str(handler_tok.value))
                    i += 1
                    continue

        if token.type == "WORD" and token.value == "load":
            i += 1
            path_token = peek(tokens, i)
            is_valid = path_token and (
                path_token.type == "STRING"
                or (path_token.type == "WORD" and path_token.value.startswith("@"))
            )
            if not is_valid:
                raise CompilerError("Expected path after `load`", token=peek(tokens, i - 1))
            load_info = resolve_load_target(path_token.value, base_dir, token=path_token)
            if load_info["kind"] == "json":
                try:
                    key = infer_json_context_key(load_info["full_path"])
                except ValueError as e:
                    raise CompilerError(str(e), token=path_token)
                page.loaded_json.append({"key": key, "path": load_info["full_path"]})
            elif load_info["kind"] == "stylesheet":
                page.loaded_sheets.append(build_tss_ast_from_text(read_text_file(load_info["full_path"])))
            elif load_info["kind"] == "module":
                page.loaded_modules.append(load_info["full_path"])
                try:
                    mod_source = read_text_file(load_info["full_path"])
                    register_lib_module(mod_source, module_id=load_info["full_path"])
                except Exception:
                    pass
            i += 1
            continue

        if token.type == "WORD" and token.value == "let":
            let_node, i = parse_let(tokens, i)
            page.let_vars[let_node.name] = let_node.value
            continue

        if token.type == "WORD" and token.value == "head":
            i += 1
            if not peek(tokens, i) or peek(tokens, i).type != "BRACE" or peek(tokens, i).value != "{":
                raise CompilerError("Expected `{` after `head`", token=peek(tokens, i - 1))
            i += 1
            i = parse_head_block(tokens, i, page.head)
            continue

        if token.type == "WORD" and token.value.upper() == "BODY":
            i += 1
            if not peek(tokens, i) or peek(tokens, i).type != "BRACE" or peek(tokens, i).value != "{":
                raise CompilerError("Expected `{` after `BODY`", token=peek(tokens, i - 1))
            i += 1
            page.body, i = build_elements(tokens, i, file_path, source, require_closing_brace=True, start_token=token)
            continue

        # App Router: `children` keyword — marks where page content goes in layouts
        if token.type == "WORD" and token.value == "children":
            i += 1
            # children can be standalone (no braces) or have optional braces
            if peek(tokens, i) and peek(tokens, i).type == "BRACE" and peek(tokens, i).value == "{":
                i += 1
                # Skip until closing brace
                depth = 1
                while i < len(tokens) and depth > 0:
                    if peek(tokens, i).type == "BRACE" and peek(tokens, i).value == "{":
                        depth += 1
                    elif peek(tokens, i).type == "BRACE" and peek(tokens, i).value == "}":
                        depth -= 1
                    i += 1
            # Create a special marker element
            node = ElementNode("children", token=token, file_path=file_path)
            page.body.append(node)
            continue

        if token.type == "WORD" and token.value == "import":
            _, i = parse_import(tokens, i)
            continue

        if token.type == "WORD" and token.value == "state":
            i += 1
            if not peek(tokens, i) or peek(tokens, i).type != "BRACE" or peek(tokens, i).value != "{":
                raise CompilerError("Expected `{` after `state`", token=peek(tokens, i - 1))
            i += 1
            while i < len(tokens):
                tok = peek(tokens, i)
                if tok.type == "BRACE" and tok.value == "}":
                    i += 1
                    break
                if is_statement_separator(tok):
                    i += 1
                    continue
                if tok.type != "WORD":
                    raise CompilerError("Invalid state key", token=tok)
                key = tok.value
                key_tok = tok
                i += 1

                # Optional type annotation: `count: number = 0`
                state_type = None
                if peek(tokens, i) and peek(tokens, i).type == "WORD" and peek(tokens, i).value == ":":
                    i += 1  # consume ":"
                    type_token = peek(tokens, i)
                    if not type_token or type_token.type != "WORD":
                        raise CompilerError("Expected type name after `:`", token=peek(tokens, i - 1))
                    type_name = type_token.value.lower()
                    if type_name not in VALID_TYPES:
                        raise CompilerError(
                            f"Unknown type `{type_token.value}`. Valid types: {', '.join(sorted(VALID_TYPES))}",
                            token=type_token,
                        )
                    state_type = type_name
                    i += 1

                if peek(tokens, i) and peek(tokens, i).type == "WORD" and peek(tokens, i).value == "=":
                    i += 1
                value, i = parse_value_token(tokens, i)

                # Type-check at parse time
                if state_type:
                    check_type_annotation(state_type, value, key_tok, key)

                page.state_vars[key] = value
            continue

        raise CompilerError(f"Unexpected top-level token: `{token.value}`", token=token)

    _attach_component_stylesheets(page, source)
    return page


def _attach_component_stylesheets(page, source) -> None:
    """Components can `load` their own .tss file. If this page (directly or
    via nested component imports) ends up using such a component, pull that
    stylesheet in automatically -- same place page-level `load` results land."""
    seen_paths = set()
    used_names = set(IMPORT_RE.findall(source))
    used_names.update(_collect_used_component_names(getattr(page, "body", []) or []))
    for comp_name in sorted(used_names):
        try:
            dep_paths = collect_component_dependencies(comp_name)
        except CompilerError:
            continue
        # v0.8.48 (Issue B): Call load_component_ast to populate
        # _COMPONENT_STYLESHEET_PATHS for components used as child
        # elements (not just via `import`). Without this, `load` in
        # component files was silently ignored because the stylesheet
        # dict was empty when _attach ran (load_component_ast was only
        # called during rendering, which happens AFTER build_tw_ast).
        try:
            load_component_ast(comp_name)
        except Exception:
            pass
        for dep_path in dep_paths:
            if dep_path in _COMPONENT_STYLESHEET_PATHS and dep_path not in seen_paths:
                seen_paths.add(dep_path)
                # v0.8.48 (Issue 7): _COMPONENT_STYLESHEET_PATHS now stores
                # a LIST of sheets (one per `load` line) instead of a single
                # sheet.  Extend loaded_sheets with all of them.
                stored = _COMPONENT_STYLESHEET_PATHS[dep_path]
                if isinstance(stored, list):
                    page.loaded_sheets.extend(stored)
                else:
                    page.loaded_sheets.append(stored)



def _is_new_tss_declaration(item) -> bool:
    """Check if item starts a new CSS property or nested block."""
    if "{" in item:
        return True
    parts = item.split(None, 1)
    if parts and ":" in parts[0].rstrip(";"):
        return True
    # Check if it looks like Tailwind utility classes (each word is a known utility)
    # If so, it's a new declaration line, not a continuation
    if parts:
        words = parts[0].split()
        if len(words) > 0:
            from_tailwind = True
            for w in words:
                if not expand_tailwind_class(w):
                    from_tailwind = False
                    break
            if from_tailwind:
                return True
    # CSS custom properties (--accent, --bg-dark, etc.) are always new declarations
    if parts:
        first_word = parts[0].strip(":;,")
        if first_word.startswith("--"):
            return True
        if first_word.lower() in CSS_PROPERTIES or first_word.lower() in CSS_ALIASES:
            return True
        # v0.8.48 (Issue C): vendor-prefixed properties (-webkit-*, -moz-*, -ms-*, -o-*)
        # are always new declarations, even if not in CSS_PROPERTIES. Without this,
        # they'd be silently merged into the previous declaration's value and lost.
        if first_word.startswith(("-webkit-", "-moz-", "-ms-", "-o-", "-khtml-")):
            return True
    return False


def _split_tss_line(line) -> Any:
    """Split a TSS line on semicolons, respecting parentheses and quotes."""
    parts = []
    start = 0
    depth = 0
    in_quote = False
    quote_char = ""
    for i, ch in enumerate(line):
        if in_quote:
            if ch == quote_char:
                in_quote = False
            continue
        if ch in ('"', "'"):
            in_quote = True
            quote_char = ch
            continue
        if ch == "(":
            depth += 1
        elif ch == ")":
            depth -= 1
        elif ch == ";" and depth == 0:
            part = line[start:i].strip()
            if part:
                parts.append(part)
            start = i + 1
    tail = line[start:].strip()
    if tail:
        parts.append(tail)
    return parts


def _split_tss_body_items(body) -> Any:
    items = []
    start = 0
    depth = 0
    for i, ch in enumerate(body):
        if ch == "{":
            depth += 1
        elif ch == "}":
            depth -= 1
        elif ch == "\n" and depth == 0:
            line = body[start:i].strip()
            if line:
                # Split on semicolons at depth 0 to handle multiple declarations per line
                for part in _split_tss_line(line):
                    if part.strip():
                        items.append(part.strip())
            start = i + 1
    tail = body[start:].strip()
    if tail:
        for part in _split_tss_line(tail):
            if part.strip():
                items.append(part.strip())
    # Merge multi-line values: if an item doesn't end with ; or } and the
    # next item doesn't look like a new declaration, merge them into one.
    merged = []
    for item in items:
        if merged and not merged[-1].endswith(";") and not merged[-1].endswith("}") and not _is_new_tss_declaration(item):
            merged[-1] = merged[-1] + " " + item
        else:
            merged.append(item)
    return merged


def _tokenize_tss_value_line(line):
    """Tokenize a TSS declaration line on whitespace, keeping parenthesised
    groups (e.g. rgba(0, 0, 0, .5)) and quoted strings intact as one token."""
    tokens = []
    buf = []
    depth = 0
    in_quote = False
    quote_char = ""
    for ch in line:
        if in_quote:
            buf.append(ch)
            if ch == quote_char:
                in_quote = False
            continue
        if ch in ('"', "'"):
            in_quote = True
            quote_char = ch
            buf.append(ch)
            continue
        if ch == "(":
            depth += 1
            buf.append(ch)
            continue
        if ch == ")":
            depth -= 1
            buf.append(ch)
            continue
        if ch.isspace() and depth == 0:
            if buf:
                tokens.append("".join(buf))
                buf = []
            continue
        buf.append(ch)
    if buf:
        tokens.append("".join(buf))
    return tokens


def _looks_like_css_property_token(tok) -> bool:
    name = tok.strip(":;,").lower()
    if not name or not re.match(r"^-{0,2}[a-z][a-z-]*$", name):
        return False
    if name.startswith("--"):
        return True
    if name in CSS_PROPERTIES or name in CSS_ALIASES:
        return True
    if name.startswith(("-webkit-", "-moz-", "-ms-", "-o-", "-khtml-")):
        return True
    return False


def _split_multi_prop_declaration(item):
    """Split a single TSS line that packs multiple properties without
    semicolons, e.g. `border-radius 50% object-fit cover`, into individual
    (prop, value) pairs.

    Fix for bug #4 (v0.8.48): previously a line like
        border 3px solid rgba(0, 240, 255, 0.15) border-top-color #00f0ff
    was parsed as ONE declaration (`border: 3px solid rgba(...) border-top-color #00f0ff`),
    silently corrupting the generated CSS. Each token is scanned; whenever a
    token that is itself a recognized CSS property name shows up after at
    least one value token, that marks the start of a new declaration.

    Returns None (meaning "nothing to split, use normal single-declaration
    parsing") when the item only contains one property.
    """
    tokens = _tokenize_tss_value_line(item)
    if len(tokens) < 3:
        return None

    first_prop = tokens[0].strip(":;,").lower()
    if not (
        first_prop in CSS_PROPERTIES
        or first_prop in CSS_ALIASES
        or first_prop.startswith("--")
        or first_prop.startswith(("-webkit-", "-moz-", "-ms-", "-o-", "-khtml-"))
    ):
        return None

    boundaries = [0]
    for idx in range(2, len(tokens)):
        if _looks_like_css_property_token(tokens[idx]):
            boundaries.append(idx)
    if len(boundaries) < 2:
        return None  # only one property on this line — nothing to split

    decls = []
    for b_idx, start in enumerate(boundaries):
        end = boundaries[b_idx + 1] if b_idx + 1 < len(boundaries) else len(tokens)
        chunk = tokens[start:end]
        if not chunk:
            continue
        prop = chunk[0].strip(":;,")
        val = " ".join(chunk[1:]).strip().strip(";") or "true"
        decls.append((normalize_css_prop(prop), val))
    return decls


def _parse_tss_rule(selector, body) -> Any:
    rule = RuleNode(selector)
    for item in _split_tss_body_items(body):
        # Nested rule (media query, pseudo-class, etc.)
        if "{" in item and item.rstrip().endswith("}"):
            nested_sheet = build_tss_ast_from_text(item)
            rule.children.extend(nested_sheet.rules)
            continue

        # ── Tailwind CSS utility class support ──
        # Try to expand the entire item as Tailwind utility classes.
        # e.g. `flex items-center gap-2 p-4` → multiple CSS declarations.
        # Falls back to normal TSS parsing if not all words are Tailwind classes.
        tw_decls = expand_tailwind_line(item)
        if tw_decls is not None:
            for prop, val in tw_decls:
                rule.declarations.append((prop, val))
            continue

        # ── Multiple properties crammed onto one line without semicolons ──
        multi_decls = _split_multi_prop_declaration(item)
        if multi_decls is not None:
            rule.declarations.extend(multi_decls)
            continue

        # ── Normal TSS property: value parsing ──
        parts = item.split(None, 1)
        prop = parts[0].strip(":;,")
        val = parts[1].strip().strip(";") if len(parts) > 1 else "true"
        rule.declarations.append((normalize_css_prop(prop), val))
    return rule


def _dedupe_loaded_sheets(sheets):
    """Remove duplicate stylesheet entries (same rules object)."""
    seen = set()
    deduped = []
    for sheet in sheets:
        sheet_id = id(sheet)
        if sheet_id not in seen:
            seen.add(sheet_id)
            deduped.append(sheet)
    return deduped

def build_tss_ast_from_text(text) -> Any:
    sheet = StyleSheetNode()
    code = re.sub(r"/\\*.*?\\*/", "", text, flags=re.S)
    code = re.sub(r"//.*?$", "", code, flags=re.MULTILINE)
    i = 0
    n = len(code)

    while i < n:
        while i < n and code[i].isspace():
            i += 1
        if i >= n:
            break

        selector_start = i
        while i < n and code[i] != "{":
            i += 1
        selector = code[selector_start:i].strip()
        if not selector:
            break
        if i >= n or code[i] != "{":
            break
        i += 1

        depth = 1
        body_start = i
        while i < n and depth > 0:
            if code[i] == "{":
                depth += 1
            elif code[i] == "}":
                depth -= 1
            i += 1

        body = code[body_start:i - 1]
        sheet.rules.append(_parse_tss_rule(selector, body))

    return sheet


def render_value(value, context) -> Any:
    if isinstance(value, str):
        rendered = interpolate(value, context)
        parsed = parse_literal_value(rendered)
        return parsed
    return value


def html_escape(value) -> Any:
    if isinstance(value, bool):
        value = "true" if value else "false"
    s = "" if value is None else str(value)
    return (
        s.replace("&", "&amp;")
        .replace("<", "&lt;")
        .replace(">", "&gt;")
        .replace('"', "&quot;")
    )


def js_escape(value) -> Any:
    return str(value).replace("\\\\", "\\\\\\\\").replace("'", "\\\\'").replace("\\n", "\\\\n")


def safe_clone(value: Any):
    # Avoid accidental cross-scope mutation for composite values
    if isinstance(value, (dict, list)):
        return copy.deepcopy(value)
    return value


def render_attrs(attrs, context) -> Any:
    if not attrs:
        return ""
    # Transform reactive directives (bind:, on:, show:, tw-ref, etc.)
    try:
        attrs = _get_reactivity().transform_reactive_attrs(attrs)
    except Exception:
        if os.environ.get("TW_STRICT_EVAL", "").strip().lower() in {"1", "true", "yes", "on"}:
            raise
        logger.exception("transform_reactive_attrs failed; continuing without reactive directives")
    parts = []
    for name, raw_value in attrs:
        if name.startswith("data-tw-"):
            value = raw_value
        else:
            value = render_value(raw_value, context)
        if name in {"src", "href", "poster"}:
            value = resolve_static_asset_url(value)
        elif name == "srcset" and isinstance(value, str):
            srcset_parts = []
            for part in value.split(","):
                item = part.strip()
                if not item:
                    continue
                tokens = item.split()
                tokens[0] = str(resolve_static_asset_url(tokens[0]))
                srcset_parts.append(" ".join(tokens))
            value = ", ".join(srcset_parts)
        if name in BOOLEAN_ATTRS:
            if to_bool(value):
                parts.append(name)
            continue
        if value is None:
            continue
        parts.append(f'{name}="{html_escape(value)}"')
    return (" " + " ".join(parts)) if parts else ""


def render_events(events, context) -> Any:
    if not events:
        return ""
    parts = []
    for event_name, raw_handler in events:
        config = context.get("config", {}) if isinstance(context, dict) else {}
        allow_unsafe = to_bool(config.get("unsafe_inline_js", config.get("unsafeInlineJs", False)))

        # Security hardening: by default allow only function identifiers (or explicit `js:`).
        # This prevents XSS where user-controlled variables inject arbitrary JS into event attrs.
        handler = interpolate(str(raw_handler), context)
        handler = "" if handler is None else str(handler).strip()
        if handler.startswith("js:"):
            if allow_unsafe:
                js = handler[3:].lstrip()
            else:
                # Ignore unless explicitly enabled in config
                continue
        elif re.match(r"^[A-Za-z_$][A-Za-z0-9_$]*$", handler):
            # Route through the TW module registry to avoid relying on globals.
            # Fallback to window[handler] if not registered (compat).
            js = (
                "return (window.__twInvoke "
                f"? window.__twInvoke('{js_escape(handler)}', event) "
                f": (typeof {handler} === 'function' ? {handler}(event) : undefined))"
            )
        else:
            if allow_unsafe:
                js = handler
            else:
                continue

        parts.append(f'on{event_name}="{html_escape(js)}"')
    return (" " + " ".join(parts)) if parts else ""


def render_router(router, context) -> Any:
    prefix = ""
    suffix = ""
    extra = ""
    uses_router = False

    if "link" in router:
        href = interpolate(str(router["link"]), context)
        prefix = f'<a href="{html_escape(href)}" data-tw-link="{html_escape(href)}">'
        suffix = "</a>"
        uses_router = True

    if "goto" in router:
        path = interpolate(str(router["goto"]), context)
        extra += f' data-tw-goto="{html_escape(path)}" onclick="return window.__twRouterGoto(event, \'{js_escape(path)}\')"'
        uses_router = True

    return prefix, suffix, extra, uses_router


def render_inline_style(style_items, context) -> Any:
    if not style_items:
        return ""
    decls = []
    for prop, raw_value in style_items:
        decls.append(f"{prop}: {finalize_css_value(prop, raw_value, context)};")
    return f' style="{" ".join(decls)}"'


def _format_css_selector(selector, pad) -> Any:
    parts = [line.strip() for line in selector.splitlines() if line.strip()]
    if not parts:
        return selector.strip()
    return f"\n{pad}".join(parts)


def _render_css_rule(rule, context, indent=0) -> Any:
    pad = "    " * indent
    inner_pad = "    " * (indent + 1)
    selector = _format_css_selector(_normalize_at_rule_selector(rule.selector), pad)
    lines = [f"{pad}{selector} {{"]
    for prop, value in rule.declarations:
        lines.append(f"{inner_pad}{prop}: {finalize_css_value(prop, value, context)};")
    for child in rule.children:
        lines.append(_render_css_rule(child, context, indent + 1))
    lines.append(f"{pad}}}")
    return "\n".join(lines)


def render_css(sheet, context=None) -> Any:
    context = context or {}
    out = []
    for rule in sheet.rules:
        out.append(_render_css_rule(rule, context))
    return "\n".join(out)


def render_head_extras(head, context) -> Any:
    config = context.get("config", {}) if isinstance(context, dict) else {}
    site_url = str(config.get("site_url", "") or config.get("siteUrl", "") or "").rstrip("/")
    current_route = str(context.get("_tw_route", "") or "/")
    responsive = to_bool(context.get("_tw_responsive", False))

    def absolute_url(value) -> Any:
        value = render_value(value, context)
        value = resolve_static_asset_url(value)
        if not isinstance(value, str):
            return value
        if value.startswith(("http://", "https://", "//")):
            return value
        if site_url and value.startswith("/"):
            return site_url + value
        return value

    lines = []
    if head.icon:
        lines.append(f'  <link rel="icon" href="{html_escape(absolute_url(head.icon))}">')

    for meta in head.metas:
        attrs = []
        for key, raw_value in meta.items():
            value = render_value(raw_value, context)
            if value is not None:
                attrs.append(f'{key}="{html_escape(value)}"')
        lines.append(f"  <meta {' '.join(attrs)}>")

    seo = head.seo
    mappings = {
        "description": ("meta", 'name="description"'),
        "keywords": ("meta", 'name="keywords"'),
        "canonical": ("link", 'rel="canonical"'),
        "robots": ("meta", 'name="robots"'),
        "theme-color": ("meta", 'name="theme-color"'),
        "manifest": ("link", 'rel="manifest"'),
        "og_title": ("meta", 'property="og:title"'),
        "og_image": ("meta", 'property="og:image"'),
        "og_description": ("meta", 'property="og:description"'),
        "og_type": ("meta", 'property="og:type"'),
        "og_url": ("meta", 'property="og:url"'),
        "twitter_card": ("meta", 'name="twitter:card"'),
        "twitter_title": ("meta", 'name="twitter:title"'),
        "twitter_description": ("meta", 'name="twitter:description"'),
        "twitter_image": ("meta", 'name="twitter:image"'),
    }
    for key, (tag, attr) in mappings.items():
        if key not in seo:
            continue
        value = html_escape(absolute_url(seo[key]))
        if tag == "meta":
            lines.append(f'  <meta {attr} content="{value}">')
        else:
            lines.append(f'  <link {attr} href="{value}">')
    if "json_ld" in seo:
        payload = render_value(seo["json_ld"], context)
        if isinstance(payload, str):
            try:
                payload = json.loads(payload)
            except json.JSONDecodeError:
                payload = payload
        if isinstance(payload, (dict, list)):
            payload = json.dumps(payload, ensure_ascii=False)
        lines.append(f'  <script type="application/ld+json">{payload}</script>')
    return "\n".join(lines) + ("\n" if lines else "")


def get_router_runtime_url() -> Any:
    runtime_js = """/* TW Client-Side Router (v0.7.1) */
(function(){
  var pageCache = {};
  function swapBody(newHtml) {
    var parser = new DOMParser();
    var doc = parser.parseFromString(newHtml, 'text/html');
    var newBody = doc.querySelector('body');
    if (newBody) {
      document.body.innerHTML = newBody.innerHTML;
      var scripts = document.body.querySelectorAll('script');
      scripts.forEach(function(oldScript) {
        var newScript = document.createElement('script');
        if (oldScript.src) { newScript.src = oldScript.src; }
        else { newScript.textContent = oldScript.textContent; }
        oldScript.parentNode.replaceChild(newScript, oldScript);
      });
    }
    var newTitle = doc.querySelector('title');
    if (newTitle) document.title = newTitle.textContent;
  }
  function navigate(path, pushState) {
    if (path === window.location.pathname) return;
    if (pageCache[path]) {
      if (pushState) window.history.pushState({tw: path}, '', path);
      swapBody(pageCache[path]);
      window.scrollTo(0, 0);
      return;
    }
    if (typeof window.__twOnLoading === 'function') window.__twOnLoading();
    fetch(path, {headers: {'X-TW-Client-Nav': '1'}})
      .then(function(res) { if (!res.ok) throw new Error('HTTP ' + res.status); return res.text(); })
      .then(function(html) {
        pageCache[path] = html;
        if (pushState) window.history.pushState({tw: path}, '', path);
        swapBody(html);
        window.scrollTo(0, 0);
        if (typeof window.__twOnLoaded === 'function') window.__twOnLoaded();
      })
      .catch(function(err) { window.location.href = path; });
  }
  document.addEventListener('click', function(e) {
    var link = e.target.closest('[data-tw-link]');
    if (!link) return;
    var href = link.getAttribute('href');
    if (!href || href.startsWith('http') || href.startsWith('#') || link.target === '_blank') return;
    e.preventDefault();
    navigate(href, true);
  });
  window.addEventListener('popstate', function(e) {
    navigate(window.location.pathname, false);
  });
  window.__twNavigate = function(path) { navigate(path, true); };
  window.__twRouterGoto = function(event, path) {
    if (event && typeof event.preventDefault === 'function') event.preventDefault();
    navigate(path, true);
    return false;
  };
})();"""
    return write_chunk(runtime_js, "js")


def get_search_runtime_url() -> Any:
    runtime_js = """(function(){
  var INDEX_URL = '/_tw/search-index.json';
  var CACHE = null;
  function norm(s){ return String(s||'').toLowerCase().trim(); }
  async function load(){
    if (CACHE) return CACHE;
    var res = await fetch(INDEX_URL, {cache:'no-store'});
    if (!res.ok) throw new Error('Search index missing: ' + INDEX_URL);
    CACHE = await res.json();
    return CACHE;
  }
  window.__twSearch = async function(query, opts){
    opts = opts || {};
    var q = norm(query);
    if (!q) return [];
    // FIX #243: Add basic stemming (strip trailing 's', 'ing', 'ed')
    function stem(w){ w = w.replace(/(ing|ed|s)$/,''); return w; }
    // FIX #244: Guard limit — default 20, cap at 100 to prevent DoS
    var limit = Math.min(Math.max(Number(opts.limit || 20), 1), 100);
    var items = await load();
    var parts = q.split(/\\s+/).filter(Boolean).map(stem);
    var results = [];
    for (var i=0;i<items.length;i++){
      var it = items[i];
      var hay = norm((it.title||'') + ' ' + (it.content||''));
      var score = 0;
      for (var p=0;p<parts.length;p++){
        var idx = hay.indexOf(parts[p]);
        if (idx === -1) { score = 0; break; }
        score += Math.max(1, 200 - idx);
      }
      if (score > 0) results.push({route: it.route, title: it.title, excerpt: it.excerpt, score: score});
    }
    results.sort(function(a,b){ return b.score - a.score; });
    return results.slice(0, limit);
  };
})();"""
    return write_chunk(runtime_js, "js")


def build_theme_inline_script(context) -> Any:
    """
    Dark/Light mode support (static friendly).
    When context has _zero_js=True, returns empty string (no JS for static pages).
    """
    if isinstance(context, dict) and context.get("_zero_js"):
        return ""
    config = context.get("config", {}) if isinstance(context, dict) else {}
    raw_mode = config.get("theme", config.get("theme_mode", config.get("themeMode", "")))
    mode = str(raw_mode or "").strip().lower()
    if not mode or mode in {"false", "0", "off", "disabled", "none", "null"}:
        return ""
    if mode not in {"system", "dark", "light"}:
        mode = "system"
    storage_key = str(config.get("theme_storage_key", config.get("themeStorageKey", "tw_theme")) or "tw_theme")

    js = f"""(function() {{
  var STORAGE_KEY = {json.dumps(storage_key)};
  var DEFAULT_MODE = {json.dumps(mode)};
  function prefersDark() {{
    try {{
      return !!(window.matchMedia && window.matchMedia('(prefers-color-scheme: dark)').matches);
    }} catch (e) {{ return false; }}
  }}
  function resolve(mode) {{
    if (mode === 'dark' || mode === 'light') return mode;
    return prefersDark() ? 'dark' : 'light';
  }}
  function apply(resolved) {{
    var root = document.documentElement;
    root.setAttribute('data-theme', resolved);
    root.classList.toggle('dark', resolved === 'dark');
    root.classList.toggle('light', resolved === 'light');
  }}
  function getMode() {{
    var saved = null;
    try {{ saved = localStorage.getItem(STORAGE_KEY); }} catch (e) {{ saved = null; }}
    return (saved || DEFAULT_MODE || 'system');
  }}
  function setMode(mode) {{
    // FIX #246: Handle quota exceeded — try clearing old entries, then fallback silently
    try {{ localStorage.setItem(STORAGE_KEY, mode); }}
    catch (e) {{
      try {{ localStorage.removeItem(STORAGE_KEY); localStorage.setItem(STORAGE_KEY, mode); }}
      catch (e2) {{ /* quota exceeded — theme won't persist */ }}
    }}
    apply(resolve(mode));
  }}
  // FIX #245: Use namespaced object instead of polluting global scope
  window.__tw = window.__tw || {{}};
  window.__tw.setTheme = function(mode) {{ setMode(String(mode || 'system').toLowerCase()); }};
  window.__tw.toggleTheme = function() {{
    var current = document.documentElement.getAttribute('data-theme') || resolve(getMode());
    setMode(current === 'dark' ? 'light' : 'dark');
  }};
  // Initial paint
  apply(resolve(getMode()));
  // Keep in sync with system when mode=system
  try {{
    if (window.matchMedia) {{
      var mql = window.matchMedia('(prefers-color-scheme: dark)');
      var onChange = function() {{
        if (getMode() === 'system') apply(resolve('system'));
      }};
      if (mql.addEventListener) mql.addEventListener('change', onChange);
      else if (mql.addListener) mql.addListener(onChange);
    }}
  }} catch (e) {{}}
}})();"""
    return f"  <script>{js}</script>\n"


def maybe_optimize_image(node) -> None:
    # v0.8.48 (Issue 3): treat `image` tag as an alias for `img` so it gets
    # the same lazy-loading / decoding defaults and renders as <img>.
    if node.tag == "image":
        node.tag = "img"
    if node.tag != "img":
        return

    attr_map = {name: value for name, value in node.attrs}
    if "loading" not in attr_map:
        node.attrs.append(("loading", "lazy"))
    if "decoding" not in attr_map:
        node.attrs.append(("decoding", "async"))


def _build_declarative_script_loader_js(src: str, strategy: str) -> Any:
    src_json = json.dumps(str(src))
    strategy_json = json.dumps(str(strategy))
    return f"""(function(){{
  var src = {src_json};
  var strategy = {strategy_json};
  if (!src) return;
  // FIX #250: Use namespaced object instead of global pollution
  if (!window.__tw) window.__tw = {{}};
  if (!window.__tw._loadedScripts) window.__tw._loadedScripts = Object.create(null);
  if (window.__tw._loadedScripts[src]) return;
  function inject(){{
    if (window.__tw._loadedScripts[src]) return;
    window.__tw._loadedScripts[src] = true;
    var s = document.createElement('script');
    s.src = src;
    s.async = true;
    // FIX #249: Only append to document.head (documentElement is invalid)
    var _target = document.head || document.getElementsByTagName('head')[0];
    if (_target) _target.appendChild(s);
  }}
  if (strategy === 'lazyOnload') {{
    window.addEventListener('load', inject, {{ once: true }});
    return;
  }}
  // afterInteractive default
  if (document.readyState === 'loading') {{
    document.addEventListener('DOMContentLoaded', inject, {{ once: true }});
  }} else {{
    inject();
  }}
}})();"""


def render_elements_html(nodes, context, indent=1, slot_children=None, collect_head_scripts: bool = True) -> Any:
    pad = "  " * indent
    out = []
    current_context = dict(context)
    needs_router_runtime = False
    # FIX #258: Track full component stack for cycle detection (A→B→A)
    component_stack = list(current_context.get("_tw_component_stack") or [])
    head_scripts = []
    head_seen = set()

    for node in nodes:
        if isinstance(node, LetNode):
            # Default-props behavior inside components:
            # `let title "Fallback"` in component should NOT override a passed prop.
            if current_context.get("_tw_is_component") and node.name in current_context:
                continue
            current_context[node.name] = safe_clone(render_value(node.value, current_context))
            continue

        if isinstance(node, ForNode):
            items = evaluate_expression(node.list_expr, current_context)
            if not isinstance(items, list):
                continue
            for item in items:
                child_context = dict(current_context)
                child_context[node.var_name] = item
                html, router_used, child_head = render_elements_html(
                    node.children,
                    child_context,
                    indent,
                    slot_children,
                    collect_head_scripts=collect_head_scripts,
                )
                out.append(html)
                needs_router_runtime = needs_router_runtime or router_used
                for tag in child_head:
                    head_scripts.append(tag)
            continue

        if isinstance(node, IfNode):
            branch = node.children if eval_condition(node.condition, current_context) else node.else_children
            html, router_used, child_head = render_elements_html(
                branch,
                current_context,
                indent,
                slot_children,
                collect_head_scripts=collect_head_scripts,
            )
            out.append(html)
            needs_router_runtime = needs_router_runtime or router_used
            for tag in child_head:
                head_scripts.append(tag)
            continue

        if isinstance(node, ScriptTagNode):
            raw_src = render_value(node.src, current_context)
            src = interpolate(raw_src, current_context) if isinstance(raw_src, str) else str(raw_src or "")
            # Resolve @/ alias — copy file to dist/_tw/scripts/ and use served URL
            if src.startswith("@/"):
                try:
                    resolved = resolve_source_path(src, file_path or ".")
                    if os.path.exists(resolved):
                        script_name = os.path.basename(resolved)
                        # Find project root (where tw.config lives) to locate dist/
                        proj_root = file_path or "."
                        for _ in range(32):  # FIX #251: Increased depth limit
                            if os.path.exists(os.path.join(proj_root, "tw.config")):
                                break
                            parent = os.path.dirname(proj_root)
                            if parent == proj_root:
                                break
                            proj_root = parent
                        dist_scripts = os.path.join(proj_root, "dist", "_tw", "scripts")
                        os.makedirs(dist_scripts, exist_ok=True)
                        import shutil
                        shutil.copy(resolved, os.path.join(dist_scripts, script_name))
                        src = f"/_tw/scripts/{script_name}"
                except Exception:
                    pass  # Fall through with original src if resolution fails
            strategy = str(getattr(node, "strategy", "afterInteractive") or "afterInteractive")

            if strategy == "beforeInteractive":
                if collect_head_scripts and src and src not in head_seen:
                    head_seen.add(src)
                    head_scripts.append(f'{pad}<script src="{html_escape(src)}"></script>\n')
                elif not collect_head_scripts:
                    out.append(f'{pad}<script src="{html_escape(src)}"></script>\n')
                continue

            # afterInteractive / lazyOnload
            js = _build_declarative_script_loader_js(src, strategy)
            out.append(f"{pad}<script>{js}</script>\n")
            continue

        if isinstance(node, ScriptNode):
            config = current_context.get("config", {}) if isinstance(current_context, dict) else {}
            allow_raw = to_bool(
                config.get(
                    "allow_raw_script",
                    config.get(
                        "allowRawScript",
                        config.get("allow_inline_js", config.get("allowInlineJs", True)),
                    ),
                )
            )
            if not allow_raw:
                raise CompilerError(
                    "Raw `script { ... }` blocks are disabled by config (allow_raw_script: false).",
                    token=getattr(node, "token", None),
                    file_path=getattr(node, "file_path", None),
                    suggestion=(
                        "Use `.twm` + `load @...` + events, or use declarative "
                        "`script { src \"...\" strategy afterInteractive }`. "
                        "To disable raw scripts, set `allow_raw_script: false` in `tw.config`."
                    ),
                )
            # Interpolate {prop} placeholders in script content with context values
            js_content = node.raw_js
            if isinstance(current_context, dict) and "{" in js_content:
                for ctx_key, ctx_val in current_context.items():
                    if isinstance(ctx_val, (str, int, float)) and not str(ctx_key).startswith("_"):
                        js_content = js_content = js_content.replace("{" + str(ctx_key) + "}", json.dumps(str(ctx_val))[1:-1])  # FIX #255: escape ctx_val
            src = write_chunk(js_content, "js")
            out.append(f'{pad}<script src="{src}"></script>\n')
            continue

        # TW Image component — render to optimized <img>
        if isinstance(node, ComponentNode) and (node.name in _BUILTIN_TW_COMPONENTS or node.name.lower() in _BUILTIN_TW_COMPONENTS):
            if node.name in ("Icon", "icon"):
                icon_name = ""
                icon_size = 24
                icon_class = ""
                for attr_name, attr_val in node.props:
                    val = interpolate(str(attr_val), current_context) if attr_val else ""
                    if attr_name == "name":
                        icon_name = val
                    elif attr_name == "size":
                        try:
                            icon_size = int(val)
                        except (ValueError, TypeError):
                            icon_size = 24
                    elif attr_name == "class":
                        icon_class = val
                svg = get_icon_svg(icon_name, size=icon_size, class_name=icon_class)
                out.append(f"{pad}{svg}\n")
                continue
            img_html = _render_tw_image(
                node.props, context,
                project_root=getattr(node, "_tw_project_root", ""),
                output_dir=getattr(node, "_tw_output_dir", ""),
            )
            out.append(f"{pad}{img_html}\n")
            continue

        if isinstance(node, ComponentNode):
            # Guard against recursive component rendering:
            # This can happen even without `import` cycles (eg a component's template
            # directly uses itself: `Card {}` inside `Card.tw`, or A -> B -> A).
            if node.name in component_stack:
                chain = " -> ".join(component_stack + [node.name])
                raise CompilerError(
                    f"Recursive component render detected: {chain}",
                    token=getattr(node, "token", None),
                    file_path=getattr(node, "file_path", None),
                    suggestion="The component is rendering itself (directly or indirectly). Break the recursion or change the structure.",
                )
            try:
                component_nodes = load_component_ast(node.name)
            except CompilerError as err:
                notes = list(err.notes or [])
                callsite_path = getattr(node, "file_path", None) or ""
                callsite_token = getattr(node, "token", None)
                target_path = err.file_path or ""
                if not target_path:
                    with contextlib.suppress(Exception):
                        target_path = resolve_component_path(node.name)
                if callsite_path:
                    ref = f"Referenced from `{callsite_path}`"
                    if callsite_token is not None:
                        ref += f" at line {getattr(callsite_token, 'line', 0)}, column {getattr(callsite_token, 'col', 0)}"
                    notes.append(ref)
                raise CompilerError(
                    err.message,
                    token=err.token or callsite_token,
                    file_path=target_path or callsite_path,
                    suggestion=err.suggestion,
                    code=err.code,
                    notes=notes,
                )
            except Exception as err:
                # Show the error at the callsite (page/component file where it was used)
                target_path = ""
                with contextlib.suppress(Exception):
                    target_path = resolve_component_path(node.name)
                raise CompilerError(
                    f"Failed to load component `{node.name}`: {err}",
                    token=getattr(node, "token", None),
                    file_path=target_path or getattr(node, "file_path", None),
                    suggestion="Check whether the file exists in `[home]/components`. If you meant an HTML element, use a lowercase tag (e.g. `section`, `nav`).",
                    notes=[
                        (
                            f"Referenced from `{getattr(node, 'file_path', '')}` "
                            f"at line {getattr(getattr(node, 'token', None), 'line', 0)}, "
                            f"column {getattr(getattr(node, 'token', None), 'col', 0)}"
                        ).strip()
                    ],
                )
            component_context = dict(current_context)
            component_context["_tw_component_stack"] = component_stack + [node.name]
            component_context["_tw_is_component"] = True
            props_dict = {}
            for key, raw_value in node.props:
                props_dict[key] = safe_clone(render_value(raw_value, current_context))
            component_context.update(props_dict)
            component_context["props"] = props_dict
            component_context["children"] = node.children
            html, router_used, child_head = render_elements_html(
                component_nodes,
                component_context,
                indent,
                node.children,
                collect_head_scripts=collect_head_scripts,
            )
            out.append(html)
            needs_router_runtime = needs_router_runtime or router_used
            for tag in child_head:
                head_scripts.append(tag)
            continue

        if isinstance(node, ElementNode) and node.tag == "slot":
            html, router_used, child_head = render_elements_html(
                slot_children or [],
                current_context,
                indent,
                slot_children,
                collect_head_scripts=collect_head_scripts,
            )
            out.append(html)
            needs_router_runtime = needs_router_runtime or router_used
            for tag in child_head:
                head_scripts.append(tag)
            continue

        if isinstance(node, ElementNode) and node.tag == "children":
            # App Router: render {children} marker for layout composition
            out.append(pad + "{children}")
            continue

        if isinstance(node, ElementNode):
            maybe_optimize_image(node)
            attr_str = render_attrs(node.attrs, current_context)
            event_str = render_events(node.events, current_context)
            prefix, suffix, goto_str, router_used = render_router(node.router, current_context)
            style_str = render_inline_style(node.inline_style, current_context)
            full_attrs = attr_str + event_str + goto_str + style_str
            # FIX #263: Avoid double-escape for pre-escaped content
            if node.text is None:
                text = None
            else:
                _raw_text = interpolate(node.text, current_context) or ""
                text = _raw_text if ("&" in _raw_text or "<" in _raw_text) else html_escape(_raw_text)

            if node.tag in VOID_TAGS:
                out.append(f"{prefix}{pad}<{node.tag}{full_attrs}>{suffix}\n")
                needs_router_runtime = needs_router_runtime or router_used
                continue

            if node.children:
                out.append(f"{prefix}{pad}<{node.tag}{full_attrs}>\n")
                if text:
                    out.append(f"{pad}  {text}\n")
                html, child_router_used, child_head = render_elements_html(
                    node.children,
                    current_context,
                    indent + 1,
                    slot_children,
                    collect_head_scripts=collect_head_scripts,
                )
                out.append(html)
                out.append(f"{pad}</{node.tag}>{suffix}\n")
                needs_router_runtime = needs_router_runtime or router_used or child_router_used
                for tag in child_head:
                    head_scripts.append(tag)
            else:
                out.append(f"{prefix}{pad}<{node.tag}{full_attrs}>{text or ''}</{node.tag}>{suffix}\n")
                needs_router_runtime = needs_router_runtime or router_used

    return "".join(out), needs_router_runtime, head_scripts


def _build_tw_signature(page=None, context=None, zero_js: bool = False) -> Any:
    """
    Returns (meta_tags_html, tw_data_script_html, build_comments_html)
    These injected parts form TW Framework's signature in the HTML output.

    When *zero_js* is True, the ``__TW_DATA__`` script tag and the
    ``__TW__`` hidden div are omitted — the page ships with zero framework
    JavaScript.  Only the essential ``<meta>`` tags and HTML comments remain.
    """
    import datetime

    build_time = datetime.datetime.now(datetime.timezone.utc).strftime("%Y-%m-%dT%H:%M:%SZ")

    # Page name / route
    route = "/"
    page_name = "index"
    render_mode = "static"
    components_used = []

    if context and isinstance(context, dict):
        route = context.get("_tw_route", "/")
        render_mode = context.get("_tw_render_mode", "static")

    if page is not None:
        if hasattr(page, "name"):
            page_name = page.name or "index"
        elif route and route != "/":
            page_name = route.strip("/").split("/")[-1] or "index"

        # Collect component names from body nodes recursively
        def _collect_components(nodes, seen=None) -> Any:
            if seen is None:
                seen = set()
            if not nodes:
                return seen
            for node in nodes:
                if hasattr(node, "_tw_component") and node._tw_component:
                    seen.add(node._tw_component)
                if hasattr(node, "tag") and node.tag and node.tag[0].isupper():
                    seen.add(node.tag)
                if hasattr(node, "children"):
                    _collect_components(node.children, seen)
            return seen

        try:
            body = getattr(page, "body", None) or []
            components_used = sorted(_collect_components(body))
        except Exception:
            logger.exception("Failed to collect components used for build signature")
            components_used = []

    # meta + hidden markers — omit __TW__ div and __TW_DATA__ script for Zero-JS
    if zero_js:
        meta_html = (
            '  <meta charset="UTF-8">\n'
            '  <meta name="viewport" content="width=device-width, initial-scale=1.0">\n'
            '  <meta name="generator" content="TW Framework">\n'
        )
        data_script = ""
    else:
        meta_html = (
            '  <!-- ⚡ Built with TW Framework -->\n'
            '  <meta charset="UTF-8">\n'
            '  <meta name="viewport" content="width=device-width, initial-scale=1.0">\n'
            '  <meta name="generator" content="TW Framework">\n'
            '  <div id="__TW__" style="display:none"></div>\n'
        )
        tw_data = {
            "page": page_name,
            "route": route,
            "render": render_mode,
            "build": build_time,
        }
        if components_used:
            tw_data["components"] = components_used
        data_script = (
            f'  <script id="__TW_DATA__" type="application/json">'
            f'{json.dumps(tw_data, separators=(",", ":"))}'
            f'</script>\n'
        )

    # Structured HTML comments at top
    # FIX #201: In production, omit route/render/build details to prevent
    # information disclosure. Keep only page name + Zero-JS marker.
    comp_str = ", ".join(components_used) if components_used else "—"
    zero_marker = " | Zero-JS" if zero_js else ""
    _is_prod = not bool(os.environ.get("TW_DEV_MODE", ""))
    if _is_prod:
        build_comments = (
            f'<!-- [TW] Page: {page_name}{zero_marker} -->\n'
        )
    else:
        build_comments = (
            f'<!-- [TW] Page: {page_name} | Render: {render_mode} | Route: {route}{zero_marker} -->\n'
            f'<!-- [TW] Components: {comp_str} -->\n'
            f'<!-- [TW] Build: {build_time} -->\n'
        )

    return meta_html, data_script, build_comments


def build_default_document(title, head_extras, style_blocks, body_html, runtime_scripts_html, page=None, context=None, zero_js: bool = False) -> Any:
    runtime_scripts = (runtime_scripts_html + "\n") if runtime_scripts_html else ""
    meta_html, data_script, build_comments = _build_tw_signature(page, context, zero_js=zero_js)
    return f"""{build_comments}<!DOCTYPE html>
<html lang="en">
<head>
{meta_html}{data_script}{head_extras}{style_blocks}</head>
<body>
{body_html}{runtime_scripts}</body>
</html>"""


def build_redirect_document(title, target) -> Any:
    # FIX #204: URL-encode the target for meta refresh (special chars break it)
    from urllib.parse import quote as _url_quote
    safe_target = html_escape(target)
    safe_url_meta = html_escape(_url_quote(target, safe="/:?=&#%-_"))
    return f"""<!DOCTYPE html>
<html lang="en">
<head>
  <meta http-equiv="refresh" content="0;url={safe_url_meta}">
</head>
<body>
  <p>Redirecting to <a href="{safe_target}">{safe_target}</a>...</p>
  <script>window.location.replace({json.dumps(target)});</script>
</body>
</html>"""


# FIX #205: Support spaces, hyphens, and unicode in layout variable names
_LAYOUT_VAR_RE = re.compile(r"\{([A-Za-z_][A-Za-z0-9_ \-]*(?:\.[A-Za-z_][A-Za-z0-9_ \-]*)*(?:\[[0-9]+\])*)\}")


def interpolate_layout_template(text, context) -> Any:
    if text is None or "{" not in str(text):
        return text

    _unresolved = []
    def repl(match) -> Any:
        expr = match.group(1).strip()
        try:
            value = evaluate_expression(expr, context)
        except Exception:
            value = None
        if value is None:
            _unresolved.append(expr)
            return match.group(0)
        return str(value)

    result = _LAYOUT_VAR_RE.sub(repl, str(text))
    if _unresolved:
        logger.debug("Layout template has unresolved expressions: %s", ", ".join(_unresolved[:5]))
    return result


def apply_layout_template(layout_template, title, head_extras, style_blocks, body_html, runtime_scripts_html, context, page=None, zero_js: bool = False) -> Any:
    runtime_scripts = runtime_scripts_html or ""
    meta_html, data_script, build_comments = _build_tw_signature(page, context, zero_js=zero_js)
    # Inject signature into {head} placeholder
    # FIX #208: Deduplicate <meta> tags that appear in both the layout and enhanced_head
    _combined_head = meta_html + data_script + (head_extras or "")
    enhanced_head = _deduplicate_head_tags(_combined_head).rstrip()
    # FIX #207: Replace {slot} LAST to prevent body content from being
    # affected by other placeholder replacements.
    rendered = layout_template
    rendered = rendered.replace("{title}", html_escape(title or ""))
    rendered = rendered.replace("{head}", enhanced_head)
    rendered = rendered.replace("{styles}", (style_blocks or "").rstrip())
    rendered = rendered.replace("{scripts}", runtime_scripts)
    rendered = rendered.replace("{slot}", body_html)
    # Prepend build comments before <!DOCTYPE
    result = interpolate_layout_template(rendered, context)
    if result.lstrip().startswith("<!DOCTYPE") or result.lstrip().startswith("<html"):
        result = build_comments + result
    return result


def _inject_reactivity_runtime(html_text: str, page_source: str, state: dict) -> Any:
    """Inject TW VDOM runtime + state init + client lib functions into HTML before </body>."""
    try:
        from .reactivity import get_vdom_runtime_js, build_state_init_script
        runtime_js = get_vdom_runtime_js()
        state_init = build_state_init_script(state)
        
        # Extract client-side lib functions from imports
        client_lib_js = ""
        action_js = ""
        try:
            from .reactivity import extract_server_actions, build_action_bindings_js
            actions = extract_server_actions(page_source)
            action_js = build_action_bindings_js(actions)
        except Exception:
            pass
        
        script = f"<script>\n{runtime_js}\n{client_lib_js}\n{action_js}\n{state_init}\n</script>"
        if "</body>" in html_text:
            return html_text.replace("</body>", script + "\n</body>", 1)
        return html_text + script
    except Exception as _err:
        # FIX #264: Better error message for reactivity injection failure
        if os.environ.get("TW_STRICT_EVAL", "").strip().lower() in {"1", "true", "yes", "on"}:
            raise
        logger.warning("VDOM runtime injection failed: %s — page will render as static. Set TW_STRICT_EVAL=1 to raise.", _err)
        return html_text

def _inject_on_load_inits(html_text: str, handlers: Any) -> Any:
    handlers = [str(h).strip() for h in (handlers or []) if str(h).strip()]
    if not handlers:
        return html_text
    calls = "\n".join(
        (
            "    try {\n"
            f"      var name = {json.dumps(name)};\n"
            "      if (window.__twInvoke) window.__twInvoke(name);\n"
            "      else if (typeof window[name] === 'function') window[name]();\n"
            "    } catch (e) {}\n"
        )
        for name in handlers
    )
    js = f"""(function(){{
  function run(){{
{calls}
  }}
  if (document.readyState === 'loading') {{
    document.addEventListener('DOMContentLoaded', run, {{ once: true }});
  }} else {{
    run();
  }}
}})();"""
    script = f"<script>{js}</script>"
    if "</body>" in html_text:
        return html_text.replace("</body>", script + "\n</body>", 1)
    return html_text + script


def _inject_react_integration(html_doc: str, page, raw_source: str, context: dict) -> str:
    """
    Inject React bootstrap + loader scripts into the HTML if the page uses React.

    This connects ReactCompat to the actual build pipeline.
    (fixed v0.8.1 — previously ReactCompat was defined but never called during build.)

    Detection:
      - React import statements in page source or loaded .twm modules
      - render_mode == "interactive"
    """
    try:
        from .react_compat import ReactCompat

        react = ReactCompat(
            project_root=os.path.dirname(getattr(page, "_tw_source_path", "") or "")
        )
        uses_react = False

        if raw_source and react.detect_react_usage(raw_source):
            uses_react = True

        # Also check loaded .twm modules for React imports
        if not uses_react:
            for mod_path in getattr(page, "loaded_modules", []) or []:
                try:
                    mod_src = read_text_file(mod_path) if mod_path and os.path.exists(mod_path) else ""
                    if mod_src and react.detect_react_usage(mod_src):
                        uses_react = True
                        break
                except (OSError, UnicodeDecodeError):
                    continue

        # render interactive mode implies React usage
        if not uses_react and getattr(page, "render_mode", "") in ("interactive", "csr"):
            uses_react = True

        if not uses_react:
            return html_doc

        # Determine CDN vs bundle based on config
        config_react_cdn = True
        if isinstance(context, dict):
            cfg = context.get("config", {})
            if isinstance(cfg, dict):
                config_react_cdn = to_bool(
                    cfg.get("react_cdn", cfg.get("reactCdn", True))
                )

        # Inject bootstrap JS first (defines __tw.react)
        bootstrap = react.get_bootstrap_js()
        if "</body>" in html_doc:
            html_doc = html_doc.replace(
                "</body>", f'<script>\n{bootstrap}\n</script>\n</body>', 1
            )

        # Inject loader script (CDN or node_modules bundle)
        loader = react.get_react_loader_script(use_cdn=config_react_cdn)
        if loader and "</body>" in html_doc:
            html_doc = html_doc.replace("</body>", f'{loader}\n</body>', 1)

        if not config_react_cdn and not react.is_react_installed():
            logger.warning(
                "Page uses React but react is not installed in node_modules "
                "and react_cdn is disabled. Run: tw install react react-dom"
            )
    except Exception as _err:
        # FIX #265: Warn (not just debug) when React integration fails
        if os.environ.get("TW_STRICT_EVAL", "").strip().lower() in {"1", "true", "yes", "on"}:
            raise
        logger.warning("React integration failed: %s — page will render without React.", _err)

    return html_doc



def _render_image_tag(attrs: dict, text: str = "") -> str:
    """
    Render an optimized <image> tag (v0.8.37).
    `image` tag → optimized <img> with lazy loading, srcset, WebP.
    `img` tag → normal <img>, no optimization (developer choice).
    """
    src = attrs.get("src", "")
    if not src:
        return ""
    # v0.8.42: auto_image_alt
    if not attrs.get("alt"):
        try:
            _cfg = load_config()
            if to_bool(_cfg.get("auto_image_alt", False)):
                attrs["alt"] = auto_alt_from_filename(src)
        except Exception:
            pass
    return render_optimized_image(attrs, src)


def _get_component_scope_attr(component_path: str) -> str:
    """Get scoped CSS data attribute for a component if it has a .tss file (v0.8.37)."""
    try:
        tss_path = find_scoped_stylesheet(component_path)
        if tss_path:
            component_name = os.path.splitext(os.path.basename(component_path))[0]
            scope_id = generate_scope_id(component_name)
            return f"data-tw-{scope_id}"
    except Exception:
        pass
    return ""


def render_html(page, context, css_href) -> Any:
    if page.redirect_to:
        target = interpolate(page.redirect_to, context)
        return build_redirect_document(page.title or "Redirecting", target)

    body_html, needs_router_runtime, head_scripts = render_elements_html(page.body, context)
    title = interpolate(page.title, context) if page.title else ""
    context = dict(context)
    context["_tw_render_mode"] = page.render_mode
    context["_tw_revalidate"] = page.revalidate

    # FIX #268: Cache layout_responsive results to avoid repeated lookups
    layout_responsive = False
    try:
        _layouts_list = getattr(page, "layouts", None) or []
        if _layouts_list:
            _cache_key = tuple(_layouts_list)
            if not hasattr(render_html, "_responsive_cache"):
                render_html._responsive_cache = {}
            if _cache_key in render_html._responsive_cache:
                layout_responsive = render_html._responsive_cache[_cache_key]
            else:
                for lname in _layouts_list:
                    if to_bool(get_layout_meta(lname).get("responsive", False)):
                        layout_responsive = True
                        break
                render_html._responsive_cache[_cache_key] = layout_responsive
    except Exception:
        # v0.8.48 (Issue A): get_layout_meta now handles missing layouts
        # gracefully with a clean warning, so this should rarely fire.
        # Demoted from logger.exception (full traceback) to logger.debug.
        logger.debug("Failed to inspect layout meta for responsive mode", exc_info=True)
        layout_responsive = False

    context["_tw_responsive"] = (
        to_bool(context.get("_tw_responsive", False))
        or to_bool(getattr(page, "responsive", False))
        or layout_responsive
    )

    head_extras = "".join(head_scripts) + build_theme_inline_script(context) + render_head_extras(page.head, context)

    style_lines = []
    if to_bool(context.get("_tw_responsive", False)):
        # FIX #269: These are CSS resets (not viewport meta) — correct in <style>
        style_lines.append(
            "  <style>\n"
            "    *,*::before,*::after{box-sizing:border-box;}\n"
            "    body{margin:0;min-height:100vh;}\n"
            "    img,video,canvas,svg{max-width:100%;height:auto;}\n"
            "    .tw-container{width:100%;margin:0 auto;padding:0 16px;}\n"
            "    @media (min-width:768px){.tw-container{max-width:720px;padding:0 24px;}}\n"
            "    @media (min-width:1024px){.tw-container{max-width:960px;}}\n"
            "    @media (min-width:1280px){.tw-container{max-width:1140px;}}\n"
            "  </style>"
        )
    if css_href:
        style_lines.append(f'  <link rel="stylesheet" href="{css_href}">')
    if page.loaded_sheets:
        _sheets = _dedupe_loaded_sheets(page.loaded_sheets)
        combined = "\n\n".join(render_css(sheet, context) for sheet in _sheets)
        style_lines.append(f"  <style>\n{combined}\n  </style>")
    style_blocks = ("\n".join(style_lines) + "\n") if style_lines else ""

    config = context.get("config", {}) if isinstance(context, dict) else {}
    search_enabled = to_bool(config.get("search", config.get("search_index", config.get("searchIndex", False))))

    runtime_script_urls = []
    try:
        twm_sources = []
        for mod_path in getattr(page, "loaded_modules", []) or []:
            if mod_path and os.path.exists(mod_path):
                twm_sources.append({"kind": "file", "path": mod_path})
        for local_src in getattr(page, "local_modules", []) or []:
            if local_src and str(local_src).strip():
                twm_sources.append({"kind": "inline", "source": str(local_src)})
        if twm_sources:
            from .twm_parser import build_page_twm_bundle_js
            bundle_js = build_page_twm_bundle_js(twm_sources, page_source_path=getattr(page, "_tw_source_path", ""))
            runtime_script_urls.append(write_chunk(bundle_js, "js"))
    except Exception:
        if os.environ.get("TW_STRICT_EVAL", "").strip().lower() in {"1", "true", "yes", "on"}:
            raise
        logger.exception("Failed to compile `.twm` modules; continuing without TW module bundle")
    if needs_router_runtime:
        runtime_script_urls.append(get_router_runtime_url())
    if search_enabled:
        runtime_script_urls.append(get_search_runtime_url())
    # FIX #270: Bundle multiple runtime scripts into fewer requests when possible
    if len(runtime_script_urls) > 1:
        # Combine into a single chunk if all are local
        try:
            _combined = "\n".join(read_text_file(_url_to_path(u)) for u in runtime_script_urls if u and u.startswith("/_tw/"))
            if _combined:
                _bundled_url = write_chunk(_combined, "js")
                runtime_scripts_html = f'<script src="{_bundled_url}"></script>'
            else:
                runtime_scripts_html = "\n".join(f'<script src="{url}"></script>' for url in runtime_script_urls if url)
        except Exception:
            runtime_scripts_html = "\n".join(f'<script src="{url}"></script>' for url in runtime_script_urls if url)
    else:
        runtime_scripts_html = "\n".join(f'<script src="{url}"></script>' for url in runtime_script_urls if url)

    try:
        raw_source = read_text_file(getattr(page, "_tw_source_path", "")) if getattr(page, "_tw_source_path", "") else ""
    except (OSError, UnicodeDecodeError):
        # This can legitimately happen for in-memory renders (e.g. `tw run`) where
        # `_tw_source_path` points at a virtual filename. Treat as "no source".
        logger.debug("Failed to read page source for reactivity detection", exc_info=True)
        raw_source = ""

    from .reactivity import has_reactivity, parse_state_block

    reactive_enabled = bool(raw_source and has_reactivity(raw_source))
    page_state = getattr(page, "state_vars", {}) or {}
    if reactive_enabled:
        page_state.update(parse_state_block(raw_source))

    # ── Zero-JS detection ──────────────────────────────────────────────
    # If a page has no state, no events, no router, no client components,
    # no TWM modules, no on-load inits, and no reactivity, then it needs
    # zero framework JavaScript.  We skip __TW_DATA__, __TW__ div,
    # router/search/reactivity runtimes, and code-splitting chunks.
    # User-written `script { ... }` blocks are NOT framework JS and
    # are still rendered normally inside the body.
    zero_js = is_zero_js_page(
        page,
        body_html=body_html,
        needs_router_runtime=needs_router_runtime,
        raw_source=raw_source,
        reactive_enabled=reactive_enabled,
    )
    if isinstance(context, dict):
        context["_zero_js"] = zero_js
    if zero_js:
        runtime_scripts_html = ""
    # ────────────────────────────────────────────────────────────────────

    if page.layouts:
        wrapped_body = body_html
        # v0.8.48 (Issue 9): Guard against missing named layouts in the
        # render path — previously `load_layout()` raised a raw
        # `FileNotFoundError` traceback here.  Now we emit a clean TW1000
        # CompilerError with a helpful suggestion.
        for inner_name in reversed(page.layouts[1:]):
            try:
                layout_frag = load_layout(inner_name)
            except FileNotFoundError:
                expected = os.path.join(LAYOUTS_DIR, f"{inner_name}.tw")
                raise CompilerError(
                    f"Named layout `{inner_name}` not found (expected: {expected}).",
                    suggestion=f"Create `{expected}` or remove the `layout \"{inner_name}\"` key from the page.",
                )
            wrapped_body = apply_layout_fragment(layout_frag, wrapped_body, context)

        try:
            layout_template = load_layout(page.layouts[0])
        except FileNotFoundError:
            expected = os.path.join(LAYOUTS_DIR, f"{page.layouts[0]}.tw")
            raise CompilerError(
                f"Named layout `{page.layouts[0]}` not found (expected: {expected}).",
                suggestion=f"Create `{expected}` or remove the `layout \"{page.layouts[0]}\"` key from the page.",
            )
        layout_html = apply_layout_template(
            layout_template,
            title,
            head_extras,
            style_blocks,
            wrapped_body,
            runtime_scripts_html,
            context,
            page=page,
            zero_js=zero_js,
        )

        if page_state or reactive_enabled:
            layout_html = _inject_reactivity_runtime(layout_html, raw_source, page_state)
        if not zero_js:
            layout_html = _inject_on_load_inits(layout_html, getattr(page, "on_load_inits", []) or [])
        layout_html = _inject_react_integration(layout_html, page, raw_source, context)
        return layout_html

    final_doc = build_default_document(
        title,
        head_extras,
        style_blocks,
        body_html,
        runtime_scripts_html,
        page=page,
        context=context,
        zero_js=zero_js,
    )

    if page_state or reactive_enabled:
        final_doc = _inject_reactivity_runtime(final_doc, raw_source, page_state)

    if not zero_js:
        final_doc = _inject_on_load_inits(final_doc, getattr(page, "on_load_inits", []) or [])

    final_doc = _inject_react_integration(final_doc, page, raw_source, context)

    # v0.9.08 FIX: Inject prefetch script into built pages.
    # FIX #142: Skip prefetch for Zero-JS pages — they must ship 0 script tags.
    # Also skip when prefetch is explicitly disabled in config.
    if not zero_js:
        _skip_prefetch = False
        try:
            if isinstance(context, dict):
                _cfg = context.get("config", {})
                if isinstance(_cfg, dict):
                    _skip_prefetch = not bool(_cfg.get("prefetch", _cfg.get("prefetching", True)))
        except Exception:
            pass
        if not _skip_prefetch:
            try:
                from .prefetch import get_prefetch_script
                prefetch_js = get_prefetch_script()
                if prefetch_js and "</body>" in final_doc:
                    final_doc = final_doc.replace("</body>", prefetch_js + "\n</body>", 1)
            except Exception:
                pass

    # v0.9.08: CSR mode — inject full React CSR runtime
    if getattr(page, "render_mode", "") == "csr":
        try:
            from .csr_mode import inject_csr_runtime
            use_dev = bool(context.get("_tw_dev_mode", False))
            use_cdn = True
            if isinstance(context, dict):
                cfg = context.get("config", {})
                if isinstance(cfg, dict):
                    use_cdn = bool(cfg.get("react_cdn", cfg.get("reactCdn", True)))
            final_doc = inject_csr_runtime(final_doc, use_dev=use_dev, use_cdn=use_cdn)
        except Exception:
            logger.debug("CSR runtime injection skipped", exc_info=True)

    return final_doc


def parse_layout_chain(raw_value) -> Any:
    """
    Accept:
      - "main"
      - "base,docs"
      - "base > docs"
    Returns: list[str] (outer -> inner)
    """
    if raw_value is None:
        return []
    text = str(raw_value).strip()
    if not text:
        return []
    # FIX #272: Validate separators — reject ">>" or empty parts
    if ">>" in text:
        raise CompilerError(
            f"Invalid layout chain: {text!r} — multiple '>' not allowed",
            code="TW3301",
            suggestion="Use single '>' or ',' to separate layout names.",
        )
    normalized = text.replace(">", ",")
    parts = [part.strip() for part in normalized.split(",") if part.strip()]
    # Validate each part
    for part in parts:
        if not re.match(r"^[A-Za-z_][\w-]*$", part):
            raise CompilerError(
                f"Invalid layout name: {part!r}",
                code="TW3302",
                suggestion="Layout names must start with a letter or underscore.",
            )
    return parts


def apply_layout_fragment(layout_template, body_html, context) -> Any:
    """
    Apply an inner (fragment) layout around body_html.
    Inner layouts should ideally NOT include <html>/<head>/<body>; they are wrappers around `{slot}`.
    """
    # FIX #273: Call interpolate_layout_template BEFORE {slot} replacement
    # so context variables in the layout template are resolved first.
    rendered = interpolate_layout_template(layout_template, context)
    rendered = rendered.replace("{slot}", body_html)
    # Inner fragments should not re-inject global document placeholders
    # FIX #143/#146: Log warning when inner layout placeholders are stripped
    if "{head}" in rendered:
        import logging as _log
        _log.getLogger("tw_framework").warning("Inner layout has {head} placeholder \u2014 stripped instead of merged. Use {children} for content injection.")
    rendered = rendered.replace("{head}", "")
    rendered = rendered.replace("{styles}", "")
    rendered = rendered.replace("{scripts}", "")
    rendered = rendered.replace("{title}", "")
    return interpolate_layout_template(rendered, context)


# FIX #211: Allow hyphens and unicode in JSON context keys
_LOAD_JSON_KEY_RE = re.compile(r"^[A-Za-z_][\w\-]*$", re.UNICODE)


def load_external_json(rel_path, base_dir) -> Any:
    full_path = resolve_source_path(rel_path, base_dir)
    if not os.path.exists(full_path):
        raise FileNotFoundError(f"load: json not found -> {full_path}")
    with open(full_path, "r", encoding="utf-8") as f:
        data = json.load(f)
    # FIX #210: Basic schema validation — reject non-dict/non-list JSON
    if not isinstance(data, (dict, list)):
        raise CompilerError(
            f"JSON file must be an object or array: {full_path}",
            file_path=full_path,
            code="TW3201",
            suggestion="Ensure the JSON file contains a {{}} object or [] array at the top level.",
        )
    return data


def infer_json_context_key(rel_path) -> Any:
    base = os.path.basename(rel_path)
    stem = base[:-5] if base.lower().endswith(".json") else os.path.splitext(base)[0]
    if not _LOAD_JSON_KEY_RE.match(stem):
        raise ValueError(f"Invalid JSON context key inferred from filename: {stem}")
    return stem


def load_page_data(tw_path) -> Any:
    # FIX #212: Allow opt-out of auto JSON loading via config
    try:
        _cfg = load_config()
        if not to_bool(_cfg.get("auto_page_data", _cfg.get("autoPageData", True))):
            return {}
    except Exception:
        pass
    base, ext = os.path.splitext(tw_path)
    json_path = base + ".json" if ext.lower() == ".tw" else tw_path + ".json"
    if os.path.exists(json_path):
        try:
            with open(json_path, "r", encoding="utf-8") as f:
                data = json.load(f)
            if not isinstance(data, (dict, list)):
                log(f"⚠️ Page data JSON is not object/array: {json_path}", level="warning")
                return {}
            return data
        except Exception as err:
            log(f"⚠️ Failed to parse page data JSON: {json_path} ({err})", level="warning")
            return {}
    return {}


def load_page_ast_from_file(tw_path) -> Any:
    raw = read_text_file(tw_path)
    tokens = tokenize_tw(raw)
    ast = build_tw_ast(tokens, os.path.dirname(tw_path), tw_path, raw)
    ast._tw_source_path = tw_path
    return ast


def load_dynamic_items(tw_path) -> Any:
    base, ext = os.path.splitext(tw_path)
    json_path = base + ".json" if ext.lower() == ".tw" else tw_path + ".json"
    if not os.path.exists(json_path):
        # FIX #213: Warn instead of silently returning [] — user may think data is empty
        log(f"⚠️ Dynamic route JSON not found: {json_path} — page will have 0 items", level="warning")
        return []
    try:
        with open(json_path, "r", encoding="utf-8") as f:
            data = json.load(f)
    except Exception as err:
        log(f"⚠️ Failed to parse dynamic route JSON: {json_path} ({err})", level="warning")
        return []
    if isinstance(data, list):
        return data
    if isinstance(data, dict) and isinstance(data.get("items"), list):
        return data["items"]
    # Schema validation: wrong shape is an actionable project error (not just "no routes").
    raise CompilerError(
        f"Dynamic route JSON has unsupported shape: {json_path}",
        file_path=json_path,
        suggestion="Expected either a JSON list (e.g. `[{\"id\":\"a\"}]`) or an object with `{\"items\": [...]}`.",
        code="TW3101",
    )


def load_generate_static_params(page_ast, tw_path):
    """
    Load dynamic route params from generateStaticParams directive.

    The page directive `generateStaticParams` specifies a path to a JSON file
    (relative to the page's directory) that provides the params for
    pre-rendering a dynamic route at build time.

    Returns a list of item dicts (same shape as load_dynamic_items).
    Returns None if generateStaticParams is not set.
    """
    if not page_ast or not getattr(page_ast, "generate_static_params", None):
        return None

    params_path = page_ast.generate_static_params
    page_dir = os.path.dirname(tw_path)
    if not os.path.isabs(params_path):
        params_path = os.path.join(page_dir, params_path)

    if not os.path.exists(params_path):
        log(f"⚠️ generateStaticParams file not found: {params_path}", level="warning")
        return []

    try:
        with open(params_path, "r", encoding="utf-8") as f:
            data = json.load(f)
    except Exception as err:
        log(f"⚠️ Failed to parse generateStaticParams JSON: {params_path} ({err})", level="warning")
        return []

    if isinstance(data, list):
        return data
    if isinstance(data, dict) and isinstance(data.get("items"), list):
        return data["items"]

    raise CompilerError(
        f"generateStaticParams JSON has unsupported shape: {params_path}",
        file_path=params_path,
        suggestion="Expected either a JSON list (e.g. `[{\"slug\":\"a\"}]`) or an object with `{\"items\": [...]}`.",
        code="TW3102",
    )


def classify_dynamic_route_file(filename) -> Optional[Dict[str, Any]]:
    optional_match = OPTIONAL_CATCH_ALL_FILE_RE.match(filename)
    if optional_match:
        return {"type": "dynamic", "route_kind": "optional-catch-all", "param": optional_match.group(1)}

    catch_all_match = CATCH_ALL_FILE_RE.match(filename)
    if catch_all_match:
        return {"type": "dynamic", "route_kind": "catch-all", "param": catch_all_match.group(1)}

    dynamic_match = DYNAMIC_FILE_RE.match(filename)
    if dynamic_match:
        return {"type": "dynamic", "route_kind": "single", "param": dynamic_match.group(1)}

    return None


def resolve_dynamic_segments(page_info, item) -> Any:
    raw_value = item.get(page_info["param"], item.get("id", item.get("slug", "unknown")))
    route_kind = page_info.get("route_kind", "single")

    # FIX #215: Handle list values — join with slash instead of str() representation
    if isinstance(raw_value, (list, tuple)):
        segments = [str(part).strip("/") for part in raw_value if str(part).strip("/")]
        return segments or ["unknown"]

    if route_kind == "single":
        return [str(raw_value)]

    if raw_value is None or raw_value == "":
        # FIX #216: Use param name as fallback instead of hardcoded "unknown"
        _fallback = str(page_info.get("param", "unknown"))
        return [] if route_kind == "optional-catch-all" else [_fallback]

    if isinstance(raw_value, (list, tuple)):
        segments = [str(part).strip("/") for part in raw_value if str(part).strip("/")]
    else:
        segments = [part for part in str(raw_value).strip("/").split("/") if part]

    if not segments and route_kind != "optional-catch-all":
        return ["unknown"]
    return segments


def load_config() -> Any:
    config = {"name": "My Site"}
    if not os.path.exists(CONFIG_FILE):
        return config
    with open(CONFIG_FILE, "r", encoding="utf-8") as f:
        stack = [(-1, config)]
        for raw_line in f:
            if not raw_line.strip():
                continue
            if raw_line.lstrip().startswith("#"):
                continue
            indent = len(raw_line) - len(raw_line.lstrip(" "))
            line = raw_line.strip()
            if ":" not in line:
                # FIX #217: Warn instead of silently skipping config lines
                log(f"⚠️ Config line has no ':' separator, skipping: {line!r}", level="warning")
                continue
            key, value = line.split(":", 1)
            while len(stack) > 1 and indent <= stack[-1][0]:
                stack.pop()
            current = stack[-1][1]
            key = key.strip()
            value = value.strip()
            # FIX #218: Empty value = empty string, not nested dict.
            # Only create nested dict if the NEXT line is more indented.
            if value == "":
                # Peek ahead: if next non-blank line is more indented, this is a parent
                # (we'll handle it naturally via the stack). Otherwise, store empty string.
                current[key] = ""
                continue
            current[key] = parse_config_scalar(value)
    return config


def discover_pages() -> Any:
    pages = []

    # ── App Router mode (v0.7.0) ──────────────────────────────────────
    # If [home]/page.tw or [home]/layout.tw exists, use App Router discovery
    from .app_router import has_app_router_structure, discover_routes as _discover_app_routes
    if has_app_router_structure(HOME_DIR):
        app_routes = _discover_app_routes(HOME_DIR)
        for route in app_routes:
            if route.is_api:
                continue  # API routes handled separately
            # Build rel_dir and name from segments
            rel_parts = []
            for seg in route.segments:
                if seg.type == "route_group":
                    rel_parts.append(f"({seg.param_name})")
                elif seg.type == "dynamic":
                    rel_parts.append(f"[{seg.param_name}]")
                elif seg.type == "catch_all":
                    rel_parts.append(f"[...{seg.param_name}]")
                else:
                    rel_parts.append(seg.raw)
            rel_dir = "/".join(rel_parts) if rel_parts else ""
            rel_dir = normalize_route_directory(rel_dir)

            # Check if it's a dynamic route
            has_dynamic = any(seg.type in ("dynamic", "catch_all") for seg in route.segments)
            if has_dynamic:
                # FIX #220: Guard against StopIteration if has_dynamic=True but no dynamic segment found
                dyn_seg = next((s for s in route.segments if s.type in ("dynamic", "catch_all")), None)
                if dyn_seg is None:
                    log(f"⚠️ Dynamic route has no dynamic segment: {route.file_path}", level="warning")
                    continue
                pages.append({
                    "type": "dynamic",
                    "path": route.file_path,
                    "rel_dir": rel_dir,
                    "name": dyn_seg.param_name,
                    "param": dyn_seg.param_name,
                    "layout_files": route.layout_files,
                    "app_router": True,
                    "url_path": route.url_path,
                })
            else:
                name = "index" if route.url_path == "/" else route.url_path.strip("/").replace("/", "_")
                pages.append({
                    "type": "static",
                    "path": route.file_path,
                    "rel_dir": rel_dir,
                    "name": name,
                    "layout_files": route.layout_files,
                    "app_router": True,
                    "url_path": route.url_path,
                })
        return pages

    # ── Legacy mode (v0.6.x and earlier) ─────────────────────────────
    if os.path.exists(INDEX_FILE):
        pages.append({"type": "static", "path": INDEX_FILE, "rel_dir": "", "name": "index"})
    if os.path.exists(PAGES_DIR):
        for root, dirs, files in os.walk(PAGES_DIR):
            # FIX #221: Skip hidden dirs, .git, node_modules
            dirs[:] = [d for d in dirs if not d.startswith(".") and d not in {".git", "node_modules", "__pycache__"}]
            rel_dir = os.path.relpath(root, PAGES_DIR)
            rel_dir = normalize_route_directory(rel_dir)
            for fname in sorted(files):
                if not fname.endswith(".tw") or _is_backup_or_temp_file(fname):
                    continue
                full_path = os.path.join(root, fname)
                dynamic_meta = classify_dynamic_route_file(fname)
                if dynamic_meta:
                    pages.append({
                        "path": full_path,
                        "rel_dir": rel_dir,
                        **dynamic_meta,
                    })
                else:
                    pages.append({
                        "type": "static",
                        "path": full_path,
                        "rel_dir": rel_dir,
                        "name": fname[:-3],
                    })
    return pages


def copy_assets() -> None:
    # FIX #222: Use a local dict and merge at end for thread safety
    _local_asset_map = {}
    if not os.path.exists(ASSETS_DIR):
        return
    for sub in ("images", "js", "css", "fonts"):
        src = os.path.join(ASSETS_DIR, sub)
        dst = os.path.join(PUBLIC_ASSETS_DIR, sub)
        if not os.path.exists(src):
            continue
        os.makedirs(dst, exist_ok=True)
        for dirpath, _, filenames in os.walk(src):
            rel_dir = os.path.relpath(dirpath, src)
            rel_dir = "" if rel_dir == "." else rel_dir
            target_dir = os.path.join(dst, rel_dir) if rel_dir else dst
            os.makedirs(target_dir, exist_ok=True)
            for filename in filenames:
                full_src = os.path.join(dirpath, filename)
                if not os.path.isfile(full_src):
                    continue
                # FIX #223: Use SHA-256 with 12 chars for fewer collisions, read in chunks
                _h = hashlib.sha256()
                with open(full_src, "rb") as f:
                    for _chunk in iter(lambda: f.read(8192), b""):
                        _h.update(_chunk)
                digest = _h.hexdigest()[:12]
                name, ext = os.path.splitext(filename)
                hashed_name = f"{name}.{digest}{ext}"
                full_dst = os.path.join(target_dir, hashed_name)
                shutil.copy2(full_src, full_dst)

                rel_asset_dir = f"/assets/{sub}"
                if rel_dir:
                    rel_asset_dir += "/" + rel_dir.replace(os.sep, "/")
                original_url = f"{rel_asset_dir}/{filename}"
                hashed_url = f"{rel_asset_dir}/{hashed_name}"
                _local_asset_map[original_url] = hashed_url


    ASSET_URL_MAP.update(_local_asset_map)


def copy_public_folder() -> None:
    """Copy the project's public/ folder (static passthrough assets) into the
    build output root, mirroring Next.js-style `public/` behaviour.

    Looked up in [home]/public first, then <project_root>/public. Files are
    copied verbatim (no hashing, no URL rewriting) so a file at
    public/photo.jpg is served at /photo.jpg.
    """
    for public_dir in (os.path.join(HOME_DIR, "public"), os.path.join(PROJECT_ROOT, "public")):
        if not os.path.isdir(public_dir):
            continue
        for dirpath, _, filenames in os.walk(public_dir):
            rel_dir = os.path.relpath(dirpath, public_dir)
            rel_dir = "" if rel_dir == "." else rel_dir
            target_dir = os.path.join(PUBLIC_DIR, rel_dir) if rel_dir else PUBLIC_DIR
            for filename in filenames:
                full_src = os.path.join(dirpath, filename)
                if not os.path.isfile(full_src):
                    continue
                os.makedirs(target_dir, exist_ok=True)
                full_dst = os.path.join(target_dir, filename)
                # FIX #224: Use copy (not copy2) — metadata preservation unnecessary
                shutil.copy(full_src, full_dst)
        # Only the first existing public/ directory wins (mirrors _user_provided
        # priority used elsewhere: [home]/public before <project_root>/public).
        break


def verify_api_isolated() -> None:
    # FIX #225: Actually verify that API routes are not included in build output
    if os.path.exists(API_DIR):
        log("  🔒 api/ folder detected — kept server-only, not included in build output.")
        # Verify no .tw API files leaked into pages/
        _api_leak = []
        if os.path.exists(PAGES_DIR):
            for _r, _, _fs in os.walk(PAGES_DIR):
                for _fn in _fs:
                    if _fn.endswith(".twm"):
                        _api_leak.append(os.path.join(_r, _fn))
        if _api_leak:
            log(f"  ⚠️  API route files found in pages/ directory: {_api_leak}", level="warning")


def read_global_stylesheet() -> Any:
    if not os.path.exists(STYLE_FILE):
        return "", None
    raw = read_text_file(STYLE_FILE)
    sheet = build_tss_ast_from_text(raw)
    css_content = render_css(sheet)
    if MINIFY_OUTPUT:
        css_content = minify_css_content(css_content)
    css_url = write_chunk(css_content, "css")
    return css_url, sheet


def create_base_context(page_ast, tw_path) -> Any:
    context = {}
    for key, value in page_ast.let_vars.items():
        context[key] = value
    # FIX #227: Cache loaded JSON files to avoid repeated file I/O
    if not hasattr(create_base_context, "_json_cache"):
        create_base_context._json_cache = {}
    for entry in getattr(page_ast, "loaded_json", []) or []:
        if not isinstance(entry, dict):
            continue
        key = entry.get("key")
        rel_path = entry.get("path")
        if not key or not rel_path:
            continue
        _cache_key = os.path.join(os.path.dirname(tw_path), rel_path)
        try:
            if _cache_key in create_base_context._json_cache:
                payload = create_base_context._json_cache[_cache_key]
            else:
                payload = load_external_json(rel_path, os.path.dirname(tw_path))
                create_base_context._json_cache[_cache_key] = payload
        except FileNotFoundError as e:
            raise CompilerError(str(e), file_path=tw_path)
        context[key] = payload
    config = load_config()
    # FIX #226: Use copies (not references) to prevent shared mutation across pages
    if "config" not in context:
        context["config"] = dict(config) if isinstance(config, dict) else config
    if "site" not in context:
        context["site"] = dict(config) if isinstance(config, dict) else config
    if "env" not in context:
        context["env"] = dict(get_public_env(config))
    return context


def build_one_page(page_info, css_url) -> Any:
    tw_path = page_info["path"]
    page_ast = load_page_ast_from_file(tw_path)

    # ── App Router mode: use compose_nested_layouts ───────────────────
    if page_info.get("app_router") and page_info.get("layout_files"):
        # v0.8.48 (bug #8): a page can carry a leftover/mistaken `layout "name"`
        # key (the older named-layout system) while ALSO living inside an App
        # Router group with its own layout.tw chain. Only the folder-based
        # layout_files chain is ever applied here — the named `layout` key is
        # silently ignored, which is confusing on its own even though it does
        # NOT double-wrap the page. Warn once so this doesn't go unnoticed.
        if getattr(page_ast, "layouts", None):
            log(
                f"  ⚠️  {compiler.safe_relpath(tw_path, compiler.PROJECT_ROOT)}: "
                f"`layout {page_ast.layouts!r}` is ignored here — this page is inside an "
                f"App Router group and already uses its layout.tw chain. Remove the "
                f"named `layout` key or move the page out of the group folder.",
                level="warning",
            )
        if page_info["type"] == "static":
            route_path = page_info.get("url_path", route_path_from_page_info(page_info))
            context = build_page_context(page_info, page_ast, tw_path, route_path=route_path)
            body_html, needs_router, head_scripts = render_elements_html(page_ast.body, context)
            title = interpolate(page_ast.title, context) if page_ast.title else ""
            head_extras = "".join(head_scripts) + build_theme_inline_script(context) + render_head_extras(page_ast.head, context)

            style_lines = []
            if page_ast.loaded_sheets:
                combined = "\n\n".join(render_css(sheet, context) for sheet in page_ast.loaded_sheets)
                style_lines.append(f"  <style>\n{combined}\n  </style>")
            style_blocks = ("\n".join(style_lines) + "\n") if style_lines else ""

            raw_source = ""
            try:
                raw_source = read_text_file(page_ast._tw_source_path) if page_ast._tw_source_path else ""
            except (OSError, UnicodeDecodeError):
                raw_source = ""

            from .reactivity import has_reactivity
            reactive_enabled = bool(raw_source and has_reactivity(raw_source))
            zero_js = is_zero_js_page(
                page_ast, body_html=body_html,
                needs_router_runtime=needs_router,
                raw_source=raw_source, reactive_enabled=reactive_enabled,
            )
            if isinstance(context, dict):
                context["_zero_js"] = zero_js

            # FIX #228: Collect TWM module JS for App Router static pages
            _app_router_scripts = ""
            if not zero_js:
                try:
                    _twm_sources = []
                    for _mod_path in getattr(page_ast, "loaded_modules", []) or []:
                        if _mod_path and os.path.exists(_mod_path):
                            _twm_sources.append({"kind": "file", "path": _mod_path})
                    for _local_src in getattr(page_ast, "local_modules", []) or []:
                        if _local_src and str(_local_src).strip():
                            _twm_sources.append({"kind": "inline", "source": str(_local_src)})
                    if _twm_sources:
                        from .twm_parser import build_page_twm_bundle_js
                        _bundle = build_page_twm_bundle_js(_twm_sources, page_source_path=getattr(page_ast, "_tw_source_path", ""))
                        _app_router_scripts = f'<script>{_bundle}</script>'
                except Exception:
                    pass
            html = compose_nested_layouts(
                layout_files=page_info["layout_files"],
                page_body_html=body_html,
                page_title=title,
                page_head_extras=head_extras,
                page_style_blocks=style_blocks,
                page_runtime_scripts=_app_router_scripts,
                context=context,
                page=page_ast,
                zero_js=zero_js,
            )
            if MINIFY_OUTPUT:
                html = minify_html_content(html)

            # Output path based on URL path
            from .app_router import route_to_output_path
            out_rel = route_to_output_path(page_info.get("url_path", "/"))
            out_path = os.path.join(BUILD_DIR, out_rel)
            os.makedirs(os.path.dirname(out_path), exist_ok=True)
            with open(out_path, "w", encoding="utf-8") as f:
                f.write(html)
            return [out_path]

        # Dynamic App Router page
        built_paths = []
        items = load_dynamic_items(tw_path)
        for item in items:
            if not isinstance(item, dict):
                continue
            segments = resolve_dynamic_segments(page_info, item)
            route_path = route_path_from_page_info(page_info, item=item)
            context = build_page_context(page_info, page_ast, tw_path, item=item, route_path=route_path)
            # FIX #229: Use shallow copy instead of deepcopy — AST nodes are not mutated
            # during rendering, so a shallow copy is sufficient and much faster for 1000+ items.
            page_copy = copy.copy(page_ast)

            body_html, needs_router, head_scripts = render_elements_html(page_copy.body, context)
            title = interpolate(page_copy.title, context) if page_copy.title else ""
            head_extras = "".join(head_scripts) + build_theme_inline_script(context) + render_head_extras(page_copy.head, context)

            style_lines = []
            if page_copy.loaded_sheets:
                combined = "\n\n".join(render_css(sheet, context) for sheet in page_copy.loaded_sheets)
                style_lines.append(f"  <style>\n{combined}\n  </style>")
            style_blocks = ("\n".join(style_lines) + "\n") if style_lines else ""

            raw_source = ""
            try:
                raw_source = read_text_file(page_copy._tw_source_path) if page_copy._tw_source_path else ""
            except (OSError, UnicodeDecodeError):
                raw_source = ""

            from .reactivity import has_reactivity
            reactive_enabled = bool(raw_source and has_reactivity(raw_source))
            zero_js = is_zero_js_page(
                page_copy, body_html=body_html,
                needs_router_runtime=needs_router,
                raw_source=raw_source, reactive_enabled=reactive_enabled,
            )
            if isinstance(context, dict):
                context["_zero_js"] = zero_js

            html = compose_nested_layouts(
                layout_files=page_info["layout_files"],
                page_body_html=body_html,
                page_title=title,
                page_head_extras=head_extras,
                page_style_blocks=style_blocks,
                page_runtime_scripts="",
                context=context,
                page=page_copy,
                zero_js=zero_js,
            )
            if MINIFY_OUTPUT:
                html = minify_html_content(html)

            out_parts = [BUILD_DIR]
            out_parts.extend(segments)
            out_dir = os.path.join(*out_parts)
            os.makedirs(out_dir, exist_ok=True)
            out_path = os.path.join(out_dir, "index.html")
            with open(out_path, "w", encoding="utf-8") as f:
                f.write(html)
            built_paths.append(out_path)
        return built_paths

    # ── Legacy mode ───────────────────────────────────────────────────
    if page_info["type"] == "static":
        config = load_config()
        pretty_urls = to_bool(config.get("pretty_urls", config.get("prettyUrls", False)))
        route_path = route_path_from_page_info(page_info)
        context = build_page_context(page_info, page_ast, tw_path, route_path=route_path)
        html = render_html(page_ast, context, css_url)
        if MINIFY_OUTPUT:
            html = minify_html_content(html)
        out_dir = os.path.join(BUILD_DIR, page_info["rel_dir"]) if page_info["rel_dir"] else BUILD_DIR
        is_app_router = page_info.get("app_router", False)
        if pretty_urls and page_info["name"] != "index":
            if is_app_router:
                # App Router: rel_dir already contains the route name (e.g. "about"),
                # so we must NOT append page_info["name"] again — that causes
                # double-nesting: dist/about/about/index.html (bug fixed v0.8.1).
                out_path = os.path.join(out_dir, "index.html")
            else:
                # Legacy mode: /about -> dist/about/index.html (clean URLs)
                out_dir = os.path.join(out_dir, page_info["name"])
                out_path = os.path.join(out_dir, "index.html")
        else:
            # legacy: /about -> dist/about.html
            out_path = os.path.join(out_dir, f"{page_info['name']}.html")
        os.makedirs(out_dir, exist_ok=True)
        with open(out_path, "w", encoding="utf-8") as f:
            f.write(html)
        return [out_path]

    built_paths = []
    items = load_dynamic_items(tw_path)
    for item in items:
        if not isinstance(item, dict):
            continue
        segments = resolve_dynamic_segments(page_info, item)
        route_path = route_path_from_page_info(page_info, item=item)
        context = build_page_context(page_info, page_ast, tw_path, item=item, route_path=route_path)
        page_copy = copy.deepcopy(page_ast)
        html = render_html(page_copy, context, css_url)
        if MINIFY_OUTPUT:
            html = minify_html_content(html)

        seg = page_info["rel_dir"] if page_info["rel_dir"] else ""
        route_parts = [BUILD_DIR]
        if seg:
            route_parts.append(seg)
        route_parts.extend(segments)
        out_dir = os.path.join(*route_parts)
        os.makedirs(out_dir, exist_ok=True)
        out_path = os.path.join(out_dir, "index.html")
        with open(out_path, "w", encoding="utf-8") as f:
            f.write(html)
        built_paths.append(out_path)
    return built_paths


def parse_cli_args() -> Any:
    parser = argparse.ArgumentParser(description="TW compiler build tool")
    parser.add_argument("--force", action="store_true", help="Rebuild all pages")
    parser.add_argument(
        "--workers",
        type=int,
        default=DEFAULT_WORKERS,
        help="Parallel page compilation workers",
    )
    args = parser.parse_args()
    return BuildOptions(
        force=args.force,
        workers=max(1, args.workers),
    )


def get_page_manifest_entry(manifest, page_info) -> Any:
    return manifest.get("pages", {}).get(page_cache_key(page_info))


def should_rebuild_page(page_info, dependencies, manifest, options) -> Any:
    if options.force:
        return True, "forced rebuild"

    entry = get_page_manifest_entry(manifest, page_info)
    if not entry:
        return True, "first build"

    signature = compute_dependency_signature(dependencies)
    if entry.get("signature") != signature:
        current_fingerprints = collect_dependency_fingerprints(dependencies)
        reason = describe_dependency_delta(entry.get("fingerprints"), current_fingerprints)
        return True, reason

    outputs = entry.get("outputs", [])
    if not outputs or any(not os.path.exists(path) for path in outputs):
        return True, "output missing"

    return False, "cache valid"


def update_page_manifest_entry(manifest, page_info, dependencies, outputs, metadata=None) -> None:
    key = page_cache_key(page_info)
    manifest.setdefault("pages", {})
    previous = manifest["pages"].get(key, {})
    previous_outputs = set(previous.get("outputs", []))
    current_outputs = set(outputs)
    stale_outputs = sorted(previous_outputs - current_outputs)
    cleanup_outputs(stale_outputs)
    if metadata is None:
        # FIX #232: Avoid re-parsing if metadata can be collected from cached context
        try:
            page_ast = load_page_ast_from_file(page_info["path"])
            metadata = collect_page_metadata(page_info, page_ast=page_ast, pipeline="legacy")
        except Exception as err:
            logger.debug("Failed to collect metadata for %s: %s", page_info.get("path"), err)
            metadata = {"path": page_info.get("path", ""), "type": page_info.get("type", "static")}
    manifest["pages"][key] = {
        "type": page_info["type"],
        "path": normalize_path(page_info["path"]),
        "dependencies": sorted(normalize_path(dep) for dep in dependencies),
        "signature": compute_dependency_signature(dependencies),
        "fingerprints": collect_dependency_fingerprints(dependencies),
        "outputs": sorted(normalize_path(out) for out in outputs),
        "metadata": metadata,
    }


def build_page_job(page_info, css_url) -> Dict[str, Any]:
    outputs = build_one_page(page_info, css_url)
    return {
        "page_info": page_info,
        "outputs": outputs,
    }


def print_compiler_error(page_info, err, debug: bool = False) -> None:
    if isinstance(err, CompilerError) and page_info.get("path") and os.path.exists(page_info["path"]):
        raw = read_text_file(page_info["path"])
        emitter = DiagnosticEmitter(page_info["path"], raw)
        log(emitter.format(err, debug=debug), level="error")
    else:
        log(f"  ❌ Error in {page_info['path']}: {err}", level="error")


def main() -> None:
    options = parse_cli_args()
    config = load_config()
    log(f"🔧 Building: {config.get('name', 'My Site')}\n")

    os.makedirs(BUILD_DIR, exist_ok=True)
    os.makedirs(PUBLIC_ASSETS_DIR, exist_ok=True)
    os.makedirs(CACHE_DIR, exist_ok=True)
    os.makedirs(MANIFEST_DIR, exist_ok=True)
    os.makedirs(COMPILER_DIR, exist_ok=True)

    css_url, _ = read_global_stylesheet()
    manifest = load_build_manifest()

    copy_assets()
    verify_api_isolated()

    pages = discover_pages()
    built = 0
    skipped = 0
    current_page_keys = {page_cache_key(page) for page in pages}
    removed = remove_deleted_page_outputs(manifest, current_page_keys)

    dependency_map = {}
    pages_to_build = []
    for page_info in pages:
        try:
            dependencies = collect_page_dependencies(page_info["path"])
            dependency_map[page_cache_key(page_info)] = dependencies
            needs_build, reason = should_rebuild_page(page_info, dependencies, manifest, options)
            if needs_build:
                pages_to_build.append(page_info)
            else:
                log(f"  ⏭️  {safe_relpath(page_info['path'], PROJECT_ROOT)} ({reason})")
                skipped += 1
        except Exception as err:
            print_compiler_error(page_info, err)

    if pages_to_build:
        with concurrent.futures.ThreadPoolExecutor(max_workers=options.workers) as executor:
            future_map = {
                executor.submit(build_page_job, page_info, css_url): page_info
                for page_info in pages_to_build
            }
            for future in concurrent.futures.as_completed(future_map):
                page_info = future_map[future]
                try:
                    result = future.result()
                    outputs = result["outputs"]
                    update_page_manifest_entry(
                        manifest,
                        page_info,
                        dependency_map[page_cache_key(page_info)],
                        outputs,
                    )
                    for out_path in outputs:
                        rel_out = os.path.relpath(out_path, BUILD_DIR)
                        log(f"  ✅ {rel_out}")
                        built += 1
                except Exception as err:
                    # FIX #234: Log and continue — partial output possible
                    print_compiler_error(page_info, err)

    save_build_manifest(manifest)

    log(
        f"\n🚀 Build complete — {built} page(s) generated, "
        f"{skipped} skipped, {removed} removed → {BUILD_DIR}"
    )


def _token_to_dict(token) -> Any:
    if hasattr(token, "to_dict"):
        return token.to_dict()
    return {
        "type": getattr(token, "type", ""),
        "value": getattr(token, "value", ""),
        "line": getattr(token, "line", 0),
        "col": getattr(token, "col", 0),
    }


def _diagnostic_to_payload(err, fallback_file_path="", *, phase=None) -> Dict[str, Any]:
    if isinstance(err, Diagnostic):
        diagnostic = err
    elif isinstance(err, CompilerError):
        diagnostic = err.to_diagnostic(fallback_file_path)
    elif isinstance(err, FileNotFoundError):
        message = str(err)
        # FIX #235: Use path-based detection instead of fragile string matching
        _msg_lower = message.lower()
        if "layout" in _msg_lower or "layouts/" in _msg_lower:
            code = "TW2404"
            suggestion = "Add the layout file to `[home]/layouts/<name>.tw`, or update the page's `layout` value."
        elif "component" in _msg_lower or "components/" in _msg_lower:
            code = "TW2405"
            suggestion = "Add the component file to `[home]/components`, or fix the import name."
        else:
            code = "TW2400"
            suggestion = None
        diagnostic = Diagnostic(
            severity="error",
            code=code,
            message=message,
            file_path=fallback_file_path or "",
            suggestion=suggestion,
        )
    else:
        diagnostic = Diagnostic(
            severity="error",
            code="TW0000",
            message=str(err),
            file_path=fallback_file_path or "",
        )
    return {
        "severity": diagnostic.severity,
        "code": diagnostic.code,
        "message": diagnostic.message,
        "file_path": diagnostic.file_path,
        "line": diagnostic.line,
        "col": diagnostic.col,
        # FIX #236: Handle None diagnostic.line/col gracefully
        "end_line": getattr(diagnostic, "end_line", None) or diagnostic.line or 0,
        "end_col": getattr(diagnostic, "end_col", None) or diagnostic.col or 0,
        "suggestion": diagnostic.suggestion,
        "notes": list(diagnostic.notes or []),
        "phase": phase or getattr(diagnostic, "phase", None),
        "exception_type": getattr(diagnostic, "exception_type", None) or err.__class__.__name__,
    }


def _summarize_diagnostics_payload(items) -> Any:
    summary = {
        "total": 0,
        "errors": 0,
        "warnings": 0,
        "info": 0,
        "by_code": {},
        "by_phase": {},
    }
    for item in items or []:
        summary["total"] += 1
        # FIX #237: Handle empty string severity properly
        _sev = item.get("severity", "")
        severity = (str(_sev) if _sev else "info").lower()
        if severity == "error":
            summary["errors"] += 1
        elif severity == "warning":
            summary["warnings"] += 1
        else:
            summary["info"] += 1

        code = item.get("code") or "unknown"
        summary["by_code"][code] = summary["by_code"].get(code, 0) + 1

        phase = item.get("phase") or "unspecified"
        summary["by_phase"][phase] = summary["by_phase"].get(phase, 0) + 1
    return summary


def _pipeline_metadata_from_program(program, *, file_path, route_path, dependencies) -> Dict[str, Any]:
    # FIX #238: Guard against layouts being a string instead of list
    _raw_layouts = program.meta.layouts
    if isinstance(_raw_layouts, str):
        layouts = [_raw_layouts]
    elif isinstance(_raw_layouts, (list, tuple)):
        layouts = list(_raw_layouts)
    else:
        layouts = []
    if not layouts and program.meta.layout:
        layouts = [program.meta.layout]
    raw = ""
    try:
        if file_path and file_path != "<memory>" and os.path.exists(file_path):
            raw = read_text_file(file_path)
    except (OSError, UnicodeDecodeError):
        logger.debug("Failed to read source for metadata extraction: %s", file_path, exc_info=True)
        raw = ""
    directives = extract_directives_from_source(raw, os.path.dirname(file_path)) if raw else {"imports": []}
    return {
        "pipeline": "modular",
        "route_path": route_path or "/",
        "render_mode": program.meta.render_mode,
        "revalidate": program.meta.revalidate,
        "cache_by": getattr(program.meta, "cache_by", None),
        "cache_size": getattr(program.meta, "cache_size", None),
        "layouts": layouts,
        "components": sorted(set(directives.get("imports", []))),
        "dependency_count": len(dependencies),
    }


def compile_text_pipeline(text, *, base_dir=".", file_path="<memory>", context=None, css_href=None, route_path=None, capture_errors=False, dependency_paths=None) -> Any:
    from . import parser as modular_parser
    from .lowering import lower_program
    from .render_html import build_runtime_context, render_program_document
    from .runtime_model import CompilerArtifacts
    from .semantic import analyze_program

    resolved_route = route_path or "/"
    dependencies = sorted(set(normalize_path(p) for p in (dependency_paths or ([file_path] if file_path and file_path != "<memory>" else []))))
    tokens = []
    try:
        tokens = [_token_to_dict(token) for token in tokenize_tw(text)]
    except Exception as err:
        if not capture_errors:
            raise
        payload = _diagnostic_to_payload(err, file_path, phase="tokenize")
        return CompilerArtifacts(
            source_path=file_path,
            tokens=[],
            diagnostics=[payload],
            route_path=resolved_route,
            dependencies=dependencies,
            metadata={
                "pipeline": "modular",
                "route_path": resolved_route,
                "dependency_count": len(dependencies),
                "completed_phases": [],
                "diagnostic_summary": _summarize_diagnostics_payload([payload]),
                "has_output": False,
            },
        )

    diagnostics_payload = []
    completed_phases = ["tokenize"]
    program = None
    runtime_context = {}
    ir_program = None
    html_text = None

    try:
        program = modular_parser.parse_text(text, base_dir=base_dir, file_path=file_path)
        completed_phases.append("parse")
    except Exception as err:
        if not capture_errors:
            raise
        diagnostics_payload.append(_diagnostic_to_payload(err, file_path, phase="parse"))

    # FIX #240: Ensure context is not None
    _safe_context = context if context is not None else {}
    if program is not None:
        try:
            diagnostics = analyze_program(program, context=_safe_context)
            diagnostics_payload = diagnostics.to_list()
            for item in diagnostics_payload:
                item.setdefault("phase", "analyze")
                item.setdefault("exception_type", "Diagnostic")
            completed_phases.append("analyze")
        except Exception as err:
            if not capture_errors:
                raise
            diagnostics_payload.append(_diagnostic_to_payload(err, file_path, phase="analyze"))

    if program is not None:
        try:
            ir_program = lower_program(program)
            completed_phases.append("lower")
        except Exception as err:
            if not capture_errors:
                raise
            diagnostics_payload.append(_diagnostic_to_payload(err, file_path, phase="lower"))

    if program is not None and ir_program is not None:
        try:
            runtime_context = build_runtime_context(program, context=context)
            runtime_context["_tw_route"] = resolved_route
            runtime_context.setdefault("request", create_request_context(resolved_route))
            html_text = render_program_document(ir_program, page_program=program, context=runtime_context, css_href=css_href)
            completed_phases.append("render")
        except Exception as err:
            if not capture_errors:
                raise
            diagnostics_payload.append(_diagnostic_to_payload(err, file_path, phase="render"))

    metadata = (
        _pipeline_metadata_from_program(program, file_path=file_path, route_path=resolved_route, dependencies=dependencies)
        if program is not None
        else {"pipeline": "modular", "route_path": resolved_route, "dependency_count": len(dependencies)}
    )
    metadata["completed_phases"] = list(completed_phases)
    metadata["diagnostic_summary"] = _summarize_diagnostics_payload(diagnostics_payload)
    metadata["has_output"] = html_text is not None
    return CompilerArtifacts(
        source_path=file_path,
        tokens=tokens,
        ast=program.to_dict() if program is not None else None,
        diagnostics=diagnostics_payload,
        ir=ir_program.to_dict() if ir_program is not None else None,
        html=html_text,
        program=program,
        runtime_context=runtime_context,
        dependencies=dependencies,
        route_path=resolved_route,
        pipeline="modular",
        metadata=metadata,
    )


def compile_file_pipeline(path, context=None, css_href=None, route_path=None, capture_errors=False) -> Any:
    path = normalize_path(os.path.abspath(path))
    try:
        source = read_text_file(path)
    except Exception as err:
        if not capture_errors:
            raise
        from .runtime_model import CompilerArtifacts
        payload = _diagnostic_to_payload(err, path, phase="read")
        return CompilerArtifacts(
            source_path=path,
            diagnostics=[payload],
            dependencies=[path],
            route_path=route_path or "/",
            metadata={
                "pipeline": "modular",
                "route_path": route_path or "/",
                "dependency_count": 1,
                "completed_phases": [],
                "diagnostic_summary": _summarize_diagnostics_payload([payload]),
                "has_output": False,
            },
        )
    try:
        dependency_paths = collect_page_dependencies(path)
    except CompilerError as err:
        # FIX #241: Log the actual error and use a more informative fallback
        logger.warning("Dependency collection failed for %s: %s", path, err)
        dependency_paths = [path]  # Fallback: treat file as its own dependency
    except Exception:
        logger.exception("Unexpected error while collecting dependencies for %s", path)
        dependency_paths = [path]
    return compile_text_pipeline(
        source,
        base_dir=normalize_path(os.path.dirname(path)),
        file_path=path,
        context=context,
        css_href=css_href,
        route_path=route_path,
        capture_errors=capture_errors,
        dependency_paths=dependency_paths,
    )


if __name__ == "__main__":
    main()
