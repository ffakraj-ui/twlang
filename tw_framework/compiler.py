import os
import re
import json
import ast
import copy
import shutil
import hashlib
import difflib
import argparse
import sys
import logging
import contextlib
import tempfile
import threading
import concurrent.futures
import unicodedata
import errno
from collections import OrderedDict
from dataclasses import dataclass

from .common import content_hash, log

logger = logging.getLogger(__name__)

# Cross-process file locks (best-effort). This prevents concurrent `tw build`
# processes from corrupting shared JSON artifacts (manifest/graphs) mid-write.
try:
    import fcntl  # type: ignore
except ImportError:  # pragma: no cover
    fcntl = None


@contextlib.contextmanager
def _file_lock(target_path: str, *, shared: bool):
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
def _get_reactivity():
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

# Layout-level directives (layouts are treated as raw HTML templates, so we scan & strip these lines)
LAYOUT_RESPONSIVE_RE = re.compile(
    r"(?m)^\s*tw@responsive\s*(?:=\s*)?(true|false|\"true\"|\"false\"|'true'|'false')\s*$"
)

IMPORT_RE = re.compile(r'\bimport\s+"([^"]+)"')
LAYOUT_RE = re.compile(r'\blayout\s+(?:"([^"]+)"|([^\s{}]+))')
LOAD_RE = re.compile(r'\bload\s+(?:"([^"]+)"|(@[^\s{}"\']+))')
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
    severity: str
    code: str
    message: str
    file_path: str
    line: int = 0
    col: int = 0
    end_line: int = 0
    end_col: int = 0
    suggestion: str = None
    notes: list = None
    phase: str = None
    exception_type: str = None


class CompilerError(Exception):
    def __init__(self, message, token=None, file_path=None, suggestion=None, code="TW1000", notes=None):
        super().__init__(message)
        self.message = message
        self.token = token
        self.file_path = file_path
        self.suggestion = suggestion
        self.code = code
        self.notes = list(notes or [])

    def to_diagnostic(self, fallback_file_path=None):
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
        )


class DiagnosticEmitter:
    def __init__(self, file_path, source):
        self.file_path = file_path
        self.source = source
        self.lines = source.splitlines()

    def format(self, err):
        if isinstance(err, Diagnostic):
            diagnostic = err
        elif isinstance(err, CompilerError):
            diagnostic = err.to_diagnostic(self.file_path)
        else:
            diagnostic = Diagnostic(
                severity="error",
                code="TW0000",
                message=str(err),
                file_path=self.file_path,
            )
        path = diagnostic.file_path or self.file_path
        used_fallback_source = False
        if path == self.file_path:
            lines = self.lines
        else:
            try:
                lines = read_text_file(path).splitlines()
            except (OSError, UnicodeDecodeError):
                lines = self.lines
                used_fallback_source = True

        if not diagnostic.line:
            out = [f"❌ {diagnostic.severity.upper()} [{diagnostic.code}] {path}", diagnostic.message]
            if diagnostic.suggestion:
                out.append(f"Hint: {diagnostic.suggestion}")
            for note in diagnostic.notes or []:
                out.append(f"Note: {note}")
            if used_fallback_source:
                out.append("Note: Unable to re-read the real source file; showing fallback context.")
            return "\n".join(out)

        line_no = diagnostic.line
        col_no = diagnostic.col
        line_text = ""
        if 1 <= line_no <= len(lines):
            line_text = lines[line_no - 1]
        gutter = f"{line_no:>4} | "
        pointer = " " * (len(gutter) + max(col_no - 1, 0)) + "^"

        out = [
            f"❌ {diagnostic.severity.upper()} [{diagnostic.code}] {path}",
            f"Line {line_no}, Column {col_no}",
            diagnostic.message,
        ]
        if line_text:
            out.append(f"{gutter}{line_text}")
            out.append(pointer)
        if diagnostic.suggestion:
            out.append(f"Hint: {diagnostic.suggestion}")
        for note in diagnostic.notes or []:
            out.append(f"Note: {note}")
        if used_fallback_source:
            out.append("Note: Unable to re-read the real source file; showing fallback context.")
        return "\n".join(out)


def print_diagnostic(diagnostic):
    path = diagnostic.file_path or ""
    source = ""
    if path and os.path.exists(path):
        try:
            source = read_text_file(path)
        except (OSError, UnicodeDecodeError):
            source = ""
    emitter = DiagnosticEmitter(path, source)
    log(emitter.format(diagnostic), level=diagnostic.severity)


def _mojibake_score(text):
    return sum(text.count(ch) for ch in ("Ã", "Â", "â", "ð"))


def _repair_common_mojibake(text):
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


def normalize_source_text(text):
    if not text:
        return text
    text = text.lstrip("\ufeff")
    text = unicodedata.normalize("NFC", text)
    return _repair_common_mojibake(text)


def read_text_file(path):
    with open(path, "r", encoding="utf-8") as f:
        return normalize_source_text(f.read())


def normalize_path(path):
    return os.path.normpath(path)


def resolve_source_path(path, base_dir):
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


def minify_html_content(text):
    # Collapse whitespace between tags: `>   <` -> `><`
    text = re.sub(r">\s+<", "><", text)
    text = re.sub(r"\n\s*\n+", "\n", text)
    return text.strip()


def minify_css_content(text):
    # Strip block comments: /* ... */
    text = re.sub(r"/\*.*?\*/", "", text, flags=re.S)
    # Collapse runs of whitespace
    text = re.sub(r"\s+", " ", text)
    # Remove whitespace around common separators
    text = re.sub(r"\s*([{}:;,])\s*", r"\1", text)
    return text.strip()


def minify_js_content(text):
    # Conservative minifier: strip block comments and drop empty/`//...` lines.
    # (We intentionally do not try to remove inline `//` safely inside strings.)
    text = re.sub(r"/\*.*?\*/", "", text, flags=re.S)
    lines = []
    for line in text.splitlines():
        stripped = line.strip()
        if not stripped or stripped.startswith("//"):
            continue
        lines.append(stripped)
    return "".join(lines).strip()


def parse_config_scalar(raw):
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


def get_config_value(config, *path, default=None):
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


def normalize_route_directory(rel_dir):
    if not rel_dir or rel_dir == ".":
        return ""
    parts = []
    for part in rel_dir.split(os.sep):
        if not part or ROUTE_GROUP_DIR_RE.match(part):
            continue
        parts.append(part)
    return os.path.join(*parts) if parts else ""


def resolve_static_asset_url(value):
    if not isinstance(value, str):
        return value
    if value in ASSET_URL_MAP:
        return ASSET_URL_MAP[value]
    return value


def safe_relpath(path, start):
    try:
        return os.path.relpath(path, start)
    except (ValueError, OSError):
        return path


def load_build_manifest():
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


def save_build_manifest(manifest):
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


def save_dependency_graph(dependency_map):
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


def file_fingerprint(path):
    if not os.path.exists(path):
        return None
    stat = os.stat(path)
    return {
        "size": stat.st_size,
        "mtime_ns": stat.st_mtime_ns,
    }


def compute_dependency_signature(paths):
    digest = hashlib.sha1()
    for path in sorted(normalize_path(p) for p in paths):
        digest.update(path.encode("utf-8"))
        fp = file_fingerprint(path)
        if fp is None:
            digest.update(b"|missing")
        else:
            digest.update(f"|{fp['size']}|{fp['mtime_ns']}".encode("utf-8"))
    return digest.hexdigest()


def collect_dependency_fingerprints(paths):
    fingerprints = {}
    for path in sorted(normalize_path(p) for p in paths):
        fingerprints[path] = file_fingerprint(path)
    return fingerprints


def describe_dependency_delta(previous_fingerprints, current_fingerprints):
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


def page_cache_key(page_info):
    return normalize_path(page_info["path"])


def cleanup_outputs(paths):
    for path in paths or []:
        if os.path.exists(path):
            os.remove(path)


def remove_deleted_page_outputs(old_manifest, current_page_keys):
    removed = 0
    old_keys = set(old_manifest.get("pages", {}).keys())
    for stale_key in sorted(old_keys - current_page_keys):
        entry = old_manifest["pages"].pop(stale_key, None)
        if entry:
            cleanup_outputs(entry.get("outputs", []))
            removed += 1
    return removed


class PageNode:
    def __init__(self):
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
        # Source file path for reactivity detection
        self._tw_source_path = ""


class HeadNode:
    def __init__(self):
        self.metas = []
        self.icon = None
        self.seo = {}


class ElementNode:
    def __init__(self, tag, text=None, token=None, file_path=None):
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
    def __init__(self, name, token=None, file_path=None):
        self.tag = "__component__"
        self.name = name
        self.props = []
        self.children = []
        self.token = token
        self.file_path = file_path


class ForNode:
    def __init__(self, var_name, list_expr):
        self.tag = "__for__"
        self.var_name = var_name
        self.list_expr = list_expr
        self.children = []


class IfNode:
    def __init__(self, condition):
        self.tag = "__if__"
        self.condition = condition
        self.children = []
        self.else_children = []


class LetNode:
    def __init__(self, name, value):
        self.tag = "__let__"
        self.name = name
        self.value = value


class ScriptNode:
    def __init__(self, raw_js, token=None, file_path=None):
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

    def __init__(self, src: str, strategy: str = "afterInteractive", token=None, file_path=None):
        self.tag = "__script_tag__"
        self.src = src
        self.strategy = strategy
        self.children = []
        self.token = token
        self.file_path = file_path


class StyleSheetNode:
    def __init__(self):
        self.rules = []


class RuleNode:
    def __init__(self, selector):
        self.selector = selector
        self.declarations = []
        self.children = []


def is_identifier_boundary_char(ch):
    return not (ch.isalnum() or ch == "_")


def tokenize(code, allow_inline_scripts=False):
    global _SCRIPT_COUNTER
    global _TWM_SCRIPT_COUNTER

    tokens = []
    i = 0
    line = 1
    col = 1
    n = len(code)

    def advance_one():
        nonlocal i, line, col
        ch = code[i]
        i += 1
        if ch == "\n":
            line += 1
            col = 1
        else:
            col += 1
        return ch

    def advance_count(count):
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

    def read_string(quote_char):
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

    def read_inline_script_block(open_token):
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

    def read_inline_twm_block(open_token):
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
        while i < n and (code[i] not in ' \t\r\n{}"\'' and code[i] not in ONE_CHAR_OPS):
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


def tokenize_tw(code):
    return tokenize(code, allow_inline_scripts=True)


def classify_known_prop(name):
    nl = name.lower()
    if nl in ROUTER_KEYS:
        return "router"
    if nl in EVENTS or (nl.startswith("on") and nl[2:] in EVENTS):
        return "event"
    if nl in HTML_ATTRIBUTES or nl.startswith("data-") or nl.startswith("aria-"):
        return "attr"
    if nl in CSS_PROPERTIES or nl in CSS_ALIASES:
        return "css"
    return "unknown"


def normalize_css_prop(name):
    return CSS_ALIASES.get(name.lower(), name.lower())


def normalize_attr_name(name):
    return name if any(c.isupper() for c in name) else name.lower()


def component_exists(name):
    with _CACHE_LOCK:
        if name in _COMPONENT_EXISTS_CACHE:
            return _COMPONENT_EXISTS_CACHE[name]
    path = resolve_component_path(name)
    found = bool(path and os.path.exists(path))
    with _CACHE_LOCK:
        _COMPONENT_EXISTS_CACHE[name] = found
    return found


def is_component_name(name):
    # Only treat it as a component if it actually exists.
    # This avoids errors like `Section {}` being treated as a missing component.
    return component_exists(name)


def resolve_component_path(name):
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
            if target in files:
                found = os.path.join(root, target)
                break
    with _CACHE_LOCK:
        _COMPONENT_PATH_CACHE[name] = found or direct
        return _COMPONENT_PATH_CACHE[name]


def component_name_from_path(path):
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


def resolve_load_target(raw_path, base_dir, *, token=None, location="load"):
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


def extract_directives_from_source(raw, base_dir):
    imports = IMPORT_RE.findall(raw)
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
        "layouts": layouts,
        "stylesheets": stylesheets,
        "json_files": json_files,
        "component_files": component_files,
        "module_files": module_files,
    }


def collect_component_dependencies(name, stack=None, seen=None):
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


def collect_page_dependencies(tw_path):
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


def route_path_from_page_info(page_info, item=None):
    route_parts = []
    rel_dir = page_info.get("rel_dir", "")
    if rel_dir:
        route_parts.append(rel_dir)
    if page_info.get("type") == "dynamic":
        route_parts.extend(resolve_dynamic_segments(page_info, item or {}))
    else:
        name = page_info.get("name", "index")
        if name != "index":
            route_parts.append(name)
    route = "/" + "/".join(filter(None, route_parts))
    return route or "/"


def collect_page_metadata(page_info, page_ast=None, route_path=None, *, pipeline="legacy", item=None):
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


def create_request_context(route_path, params=None):
    return {"path": route_path or "/", "params": dict(params or {}), "env": dict(os.environ)}


def build_page_context(page_info, page_ast=None, tw_path=None, *, item=None, route_path=None, request_params=None):
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


def parse_literal_value(raw):
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
    return raw


def to_bool(value):
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


def resolve_path(path, context):
    current = context
    for part in path.split("."):
        if isinstance(current, dict) and part in current:
            current = current[part]
        else:
            return None
    return current


def _transform_logic_operators(expr):
    expr = expr.replace("&&", " and ")
    expr = expr.replace("||", " or ")
    expr = re.sub(r"(?<![=!<>])!(?!=)", " not ", expr)
    return expr


def _safe_eval(node, context):
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


def evaluate_expression(expr, context):
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


def extract_placeholder_expressions(text):
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
    def __init__(self):
        self.names = []

    def visit_Name(self, node):
        self.names.append(node.id)


def collect_expression_names(expr):
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


def build_diagnostic(severity, code, message, file_path, token=None, suggestion=None, notes=None):
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


def collect_known_scope_names(context):
    names = set(context.keys() if isinstance(context, dict) else [])
    names.update({"config", "site", "env", "request", "props", "children"})
    return names


def analyze_expression_symbols(expr, scope_names, diagnostics, token=None, file_path=None, label="expression"):
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


def analyze_interpolated_text(text, scope_names, diagnostics, token=None, file_path=None, label="template"):
    for expr in extract_placeholder_expressions(text):
        analyze_expression_symbols(expr, scope_names, diagnostics, token=token, file_path=file_path, label=label)


def _append_unique_diagnostic(diagnostics, diagnostic, seen_keys):
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


def analyze_nodes_semantics(nodes, scope_names, diagnostics, file_path, component_stack=None, seen_keys=None):
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
                except Exception as err:
                    logger.exception("Unexpected error while analyzing component `%s` semantics", node.name)
            continue

        if isinstance(node, ElementNode):
            analyze_interpolated_text(node.text, current_scope, diagnostics, token=token, file_path=node_file_path, label=f"`{node.tag}` text")
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


def analyze_page_semantics(page_ast, context, tw_path, page_info=None):
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


def eval_condition(expr, context):
    return to_bool(evaluate_expression(expr, context))


def interpolate(text, context):
    if text is None or "{" not in str(text):
        return text

    def repl(match):
        value = evaluate_expression(match.group(1), context)
        return match.group(0) if value is None else str(value)

    # Support moustache-style placeholders: `{{brandName}}`
    # (common habit from other template engines)
    rendered = re.sub(r"\{\{([^{}]+)\}\}", repl, str(text))

    return INTERPOLATION_RE.sub(repl, rendered)


def _append_px_if_numeric(token):
    stripped = str(token).strip()
    if NUM_RE.match(stripped):
        return "0" if float(stripped) == 0 else f"{stripped}px"
    return stripped


def _split_css_tokens_outside_parens(value):
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


def _normalize_css_function_args(value):
    def repl(match):
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


def _normalize_border_like_value(value):
    tokens = _split_css_tokens_outside_parens(value)
    if tokens and NUM_RE.match(tokens[0]):
        tokens[0] = _append_px_if_numeric(tokens[0])
    return " ".join(tokens)


def _normalize_shadow_value(value):
    tokens = _split_css_tokens_outside_parens(value)
    normalized = []
    for token in tokens:
        normalized.append(_append_px_if_numeric(token) if NUM_RE.match(token) else token)
    return " ".join(normalized)


def _normalize_at_rule_selector(selector):
    if not selector.lstrip().startswith("@media"):
        return selector
    return re.sub(
        r"((?:min|max)-(?:width|height)\s*:\s*)(-?\d+(?:\.\d+)?)\b",
        lambda m: f"{m.group(1)}{_append_px_if_numeric(m.group(2))}",
        selector,
    )


def finalize_css_value(css_prop, raw_value, context):
    value = interpolate(raw_value, context)
    if value is None:
        value = ""
    if css_prop in NUMERIC_CSS and isinstance(value, (int, float)):
        if css_prop == "line-height":
            return str(value)
        return _append_px_if_numeric(value)
    if isinstance(value, str):
        stripped = value.strip()
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


def classify_known_keywords():
    return {
        "let", "if", "else", "for", "each", "in", "as", "import",
        "layout", "head", "body", "title", "load", "page",
        *EVENTS, *ROUTER_KEYS,
    }


def peek(tokens, i):
    return tokens[i] if i < len(tokens) else None


def collect_until_block(tokens, i):
    parts = []
    while i < len(tokens) and not (tokens[i].type == "BRACE" and tokens[i].value == "{"):
        if tokens[i].type != "NL":
            parts.append(tokens[i].value)
        i += 1
    return " ".join(parts).strip(), i


def collect_until_eol(tokens, i, stop_on_block_open=False):
    """
    Collect tokens into an expression string until newline / block end.
    - STRING tokens are re-quoted to preserve valid JSON/Python literal parsing.
    - Supports multi-token literals like: ["a", "b",]
    """
    parts = []
    depth = 0  # bracket/paren nesting
    while i < len(tokens):
        tok = tokens[i]
        if tok.type == "WORD" and tok.value == ";" and depth == 0:
            break
        if tok.type == "NL" and depth == 0:
            break
        if tok.type == "BRACE":
            if tok.value == "}" and depth == 0:
                break
            if stop_on_block_open and tok.value == "{" and depth == 0:
                break
            # NOTE: `{`/`}` are reserved for TW blocks; we don't treat them as value tokens here.
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


def is_statement_separator(token):
    return bool(token) and (
        token.type == "NL" or (token.type == "WORD" and token.value == ";")
    )


def parse_value_token(tokens, i):
    token = peek(tokens, i)
    if not token:
        return True, i
    if is_statement_separator(token):
        return True, i + 1
    expr, j = collect_until_eol(tokens, i, stop_on_block_open=True)
    if not expr:
        return True, j
    return parse_literal_value(expr), j


def unknown_property_error(token, is_component=False):
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


def looks_like_child_start(tokens, i):
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


def extract_component_load_directive(raw, base_dir):
    """Scans a component/.tw source for a top-level `load "x.tss"` / `load @x.tss`
    line, strips it out (so the main element parser never sees it), and returns
    the parsed stylesheet (or None if nothing was loaded)."""
    m = COMPONENT_LOAD_RE.search(raw)
    if not m:
        return raw, None
    quoted, atpath = m.group(1), m.group(2)
    load_info = resolve_load_target(quoted or atpath, base_dir, location="component load")
    if load_info["kind"] != "stylesheet":
        raise CompilerError(
            f"component load: expected a stylesheet but found `{load_info['full_path']}`",
            suggestion="Inside a component file, `load` currently supports `.tss` stylesheets.",
        )
    full_path = load_info["full_path"]
    sheet = build_tss_ast_from_text(read_text_file(full_path))
    raw = COMPONENT_LOAD_RE.sub("", raw, count=1)
    return raw, sheet


def load_component_ast(name):
    with _CACHE_LOCK:
        if name in _COMPONENT_AST_CACHE:
            return copy.deepcopy(_COMPONENT_AST_CACHE[name])
    collect_component_dependencies(name)
    path = resolve_component_path(name)
    if not os.path.exists(path):
        raise FileNotFoundError(f"Component not found: {path}")
    raw = read_text_file(path)
    raw, comp_sheet = extract_component_load_directive(raw, os.path.dirname(path))
    if comp_sheet is not None:
        with _CACHE_LOCK:
            _COMPONENT_STYLESHEET_PATHS[normalize_path(path)] = comp_sheet
    tokens = tokenize_tw(raw)
    nodes, _ = build_elements(tokens, 0, path, raw)
    with _CACHE_LOCK:
        _COMPONENT_AST_CACHE[name] = nodes
    return copy.deepcopy(nodes)


def load_layout(name):
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


def resolve_layout_loads(raw, base_dir):
    """Lets a layout file pull in a component (header/footer etc.) or a
    stylesheet via `load "path"` / `load @path`, so it shows on every page
    that uses this layout — without the layout needing real TW parsing.
    Paths are resolved relative to `[home]/`, same as `./components/...`
    inside a component's own `load`."""

    def repl(m):
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


def get_layout_meta(name):
    # Ensures layout is loaded at least once (populates meta cache)
    with _CACHE_LOCK:
        loaded = name in _LAYOUT_CACHE
    if not loaded:
        load_layout(name)
    with _CACHE_LOCK:
        return dict(_LAYOUT_META_CACHE.get(name, {}) or {})


def load_external_stylesheet(rel_path, base_dir):
    full_path = resolve_source_path(rel_path, base_dir)
    if not os.path.exists(full_path):
        raise FileNotFoundError(f"load: stylesheet not found -> {full_path}")
    return build_tss_ast_from_text(read_text_file(full_path))


def write_chunk(content, ext):
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


def parse_import(tokens, i):
    i += 1
    token = peek(tokens, i)
    if not token or token.type != "STRING":
        raise CompilerError("Expected component name after `import`", token=peek(tokens, i - 1))
    name = token.value
    if not component_exists(name):
        raise CompilerError(
            f"Imported component not found: `{name}`",
            token=token,
            suggestion=f"Expected file: `{os.path.join(COMPONENTS_DIR, name + '.tw')}`",
        )
    load_component_ast(name)
    return None, i + 1


def _collect_used_component_names(nodes, found=None):
    found = found or set()
    for node in nodes or []:
        if getattr(node, "tag", "") == "__component__" and getattr(node, "name", ""):
            found.add(node.name)
        _collect_used_component_names(getattr(node, "children", []) or [], found)
        _collect_used_component_names(getattr(node, "else_children", []) or [], found)
    return found


def parse_let(tokens, i):
    start = peek(tokens, i)
    i += 1
    name_token = peek(tokens, i)
    if not name_token or name_token.type != "WORD":
        raise CompilerError("Expected variable name after `let`", token=start)
    i += 1
    if peek(tokens, i) and peek(tokens, i).type == "WORD" and peek(tokens, i).value == "=":
        i += 1
    value, i = parse_value_token(tokens, i)
    return LetNode(name_token.value, value), i


def parse_if(tokens, i, file_path, source):
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


def parse_for(tokens, i, file_path, source):
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


def parse_each(tokens, i, file_path, source):
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


def _try_parse_script_tag_config(raw_body: str, *, token=None):
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


def parse_script_placeholder(tokens, i, file_path=None):
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


def parse_twm_script_placeholder(tokens, i):
    token = peek(tokens, i)
    m = TWM_SCRIPT_PLACEHOLDER_RE.match(token.value)
    if not m:
        raise CompilerError("Invalid TWM script placeholder", token=token)
    uid = int(m.group(1))
    return INLINE_TWM_SCRIPTS.get(uid, ""), i + 1


def parse_property_value(tokens, i):
    tok = peek(tokens, i)
    if not tok or tok.type in {"NL"}:
        return True, i + (1 if tok and tok.type == "NL" else 0)
    if tok.type == "BRACE" and tok.value == "}":
        return True, i

    # Fast path: single token value
    nxt = peek(tokens, i + 1)
    if tok.type == "STRING" and (not nxt or nxt.type in {"NL"} or (nxt.type == "BRACE" and nxt.value == "}")):
        return tok.value, i + 1
    if tok.type == "WORD" and (not nxt or nxt.type in {"NL"} or (nxt.type == "BRACE" and nxt.value == "}")):
        return tok.value, i + 1

    expr, j = collect_until_eol(tokens, i, stop_on_block_open=False)
    return expr, j


def parse_element_or_component(tokens, i, file_path, source):
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


def parse_child_statement(tokens, i, file_path, source):
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
    if token.type == "WORD" and SCRIPT_PLACEHOLDER_RE.match(token.value):
        return parse_script_placeholder(tokens, i, file_path=file_path)
    if token.type == "WORD" and TAG_NAME_RE.match(token.value):
        return parse_element_or_component(tokens, i, file_path, source)
    raise CompilerError(f"Unexpected token: `{token.value}`", token=token)


def parse_element_block(tokens, i, node, file_path, source):
    while i < len(tokens):
        token = peek(tokens, i)
        if is_statement_separator(token):
            i += 1
            continue
        if token.type == "BRACE" and token.value == "}":
            return i + 1

        if token.type == "WORD" and token.value == "text":
            i += 1
            raw_value, i = parse_property_value(tokens, i)
            node.text = raw_value if raw_value is not True else ""
            continue

        if token.type == "WORD" and token.value in {"let", "if", "for", "each", "import"}:
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


def parse_component_block(tokens, i, node, file_path, source):
    while i < len(tokens):
        token = peek(tokens, i)
        if is_statement_separator(token):
            i += 1
            continue
        if token.type == "BRACE" and token.value == "}":
            return i + 1

        if token.type == "WORD" and token.value in {"let", "if", "for", "each", "import"}:
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
            if token.value in {"let", "if", "for", "each", "import"} or SCRIPT_PLACEHOLDER_RE.match(token.value):
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
            continue

        raise CompilerError(f"Unexpected token inside component `{node.name}`: `{token.value}`", token=token)

    raise CompilerError(
        f"Missing closing `}}` for component `{node.name}` block",
        token=getattr(node, "token", None) or peek(tokens, max(len(tokens) - 1, 0)),
        file_path=getattr(node, "file_path", None) or file_path,
        suggestion="An opening `{` was found but the matching `}` is missing. Check your brace count.",
    )


def build_elements(tokens, i, file_path, source, require_closing_brace=False, start_token=None):
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


def parse_head_block(tokens, i, head):
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
                if is_statement_separator(tok):
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
                if is_statement_separator(tok):
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


def parse_page_block(tokens, i, page):
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
            # Allow multiple layout layers:
            # 1) repeated `layout` keys inside the same `page {}` block
            # 2) `layout "base,docs"` or `layout "base > docs"` style chains
            for name in parse_layout_chain(value):
                page.layouts.append(name)
                page.layout = name
            continue
        if key == "render":
            render_mode = str(value).lower()
            if render_mode not in {"static", "server", "edge"}:
                raise CompilerError(
                    f"Unsupported render mode: `{render_mode}`",
                    token=token,
                    suggestion="Use `static`, `server`, or `edge`.",
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

        raise CompilerError(
            f"Unknown key inside `page`: `{key}`",
            token=token,
            suggestion="Use `title`, `layout`, `render`, `revalidate`, `cache_by`, `cache_size`, `redirect`, or `rewrite`.",
        )
    raise CompilerError(
        "Missing closing `}` for `page` block",
        token=peek(tokens, max(len(tokens) - 1, 0)),
        suggestion="The closing `}` for `page { ... }` appears to be missing.",
    )


def build_tw_ast(tokens, base_dir, file_path, source):
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
            for name in parse_layout_chain(peek(tokens, i).value):
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
                i += 1
                value, i = parse_value_token(tokens, i)
                page.state_vars[key] = value
            continue

        raise CompilerError(f"Unexpected top-level token: `{token.value}`", token=token)

    _attach_component_stylesheets(page, source)
    return page


def _attach_component_stylesheets(page, source):
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
        for dep_path in dep_paths:
            if dep_path in _COMPONENT_STYLESHEET_PATHS and dep_path not in seen_paths:
                seen_paths.add(dep_path)
                page.loaded_sheets.append(_COMPONENT_STYLESHEET_PATHS[dep_path])



def _split_tss_body_items(body):
    items = []
    start = 0
    depth = 0
    for i, ch in enumerate(body):
        if ch == "{":
            depth += 1
        elif ch == "}":
            depth -= 1
        elif ch == "\n" and depth == 0:
            item = body[start:i].strip()
            if item:
                if item.endswith(","):
                    continue
                items.append(item)
            start = i + 1
    tail = body[start:].strip()
    if tail:
        items.append(tail)
    return items


def _parse_tss_rule(selector, body):
    rule = RuleNode(selector)
    for item in _split_tss_body_items(body):
        if "{" in item and item.rstrip().endswith("}"):
            nested_sheet = build_tss_ast_from_text(item)
            rule.children.extend(nested_sheet.rules)
            continue
        parts = item.split(None, 1)
        prop = parts[0].strip(":;,")
        val = parts[1].strip().strip(";") if len(parts) > 1 else "true"
        rule.declarations.append((normalize_css_prop(prop), val))
    return rule


def build_tss_ast_from_text(text):
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


def render_value(value, context):
    if isinstance(value, str):
        rendered = interpolate(value, context)
        parsed = parse_literal_value(rendered)
        return parsed
    return value


def html_escape(value):
    s = "" if value is None else str(value)
    return (
        s.replace("&", "&amp;")
        .replace("<", "&lt;")
        .replace(">", "&gt;")
        .replace('"', "&quot;")
    )


def js_escape(value):
    return str(value).replace("\\\\", "\\\\\\\\").replace("'", "\\\\'").replace("\\n", "\\\\n")


def safe_clone(value):
    # Avoid accidental cross-scope mutation for composite values
    if isinstance(value, (dict, list)):
        return copy.deepcopy(value)
    return value


def render_attrs(attrs, context):
    if not attrs:
        return ""
    # Transform reactive directives (bind:, on:, show:, tw-ref, etc.)
    try:
        attrs = _get_reactivity().transform_reactive_attrs(attrs)
    except Exception as err:
        if os.environ.get("TW_STRICT_EVAL", "").strip().lower() in {"1", "true", "yes", "on"}:
            raise
        logger.exception("transform_reactive_attrs failed; continuing without reactive directives")
    parts = []
    for name, raw_value in attrs:
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


def render_events(events, context):
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


def render_router(router, context):
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


def render_inline_style(style_items, context):
    if not style_items:
        return ""
    decls = []
    for prop, raw_value in style_items:
        decls.append(f"{prop}: {finalize_css_value(prop, raw_value, context)};")
    return f' style="{" ".join(decls)}"'


def _format_css_selector(selector, pad):
    parts = [line.strip() for line in selector.splitlines() if line.strip()]
    if not parts:
        return selector.strip()
    return f"\n{pad}".join(parts)


def _render_css_rule(rule, context, indent=0):
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


def render_css(sheet, context=None):
    context = context or {}
    out = []
    for rule in sheet.rules:
        out.append(_render_css_rule(rule, context))
    return "\n".join(out)


def render_head_extras(head, context):
    config = context.get("config", {}) if isinstance(context, dict) else {}
    site_url = str(config.get("site_url", "") or config.get("siteUrl", "") or "").rstrip("/")
    current_route = str(context.get("_tw_route", "") or "/")
    responsive = to_bool(context.get("_tw_responsive", False))

    def absolute_url(value):
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


def get_router_runtime_url():
    runtime_js = """window.__twRouterGoto = window.__twRouterGoto || function(event, path) {
  if (event && typeof event.preventDefault === 'function') event.preventDefault();
  window.location.href = path;
  return false;
};"""
    return write_chunk(runtime_js, "js")


def get_search_runtime_url():
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
    var limit = Number(opts.limit || 20);
    var items = await load();
    var parts = q.split(/\\s+/).filter(Boolean);
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


def build_theme_inline_script(context):
    """
    Dark/Light mode support (static friendly).
    Config keys supported:
      - theme: "system" | "dark" | "light" | "off"
      - theme_storage_key: override localStorage key (default: "tw_theme")
    Adds:
      - <html data-theme="dark|light"> + class "dark"/"light"
      - window.__twSetTheme(mode), window.__twToggleTheme()
    """
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
    try {{ localStorage.setItem(STORAGE_KEY, mode); }} catch (e) {{}}
    apply(resolve(mode));
  }}
  window.__twSetTheme = function(mode) {{ setMode(String(mode || 'system').toLowerCase()); }};
  window.__twToggleTheme = function() {{
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


def maybe_optimize_image(node):
    if node.tag != "img":
        return

    attr_map = {name: value for name, value in node.attrs}
    if "loading" not in attr_map:
        node.attrs.append(("loading", "lazy"))
    if "decoding" not in attr_map:
        node.attrs.append(("decoding", "async"))


def _build_declarative_script_loader_js(src: str, strategy: str) -> str:
    src_json = json.dumps(str(src))
    strategy_json = json.dumps(str(strategy))
    return f"""(function(){{
  var src = {src_json};
  var strategy = {strategy_json};
  if (!src) return;
  window.__twExternalScripts = window.__twExternalScripts || Object.create(null);
  if (window.__twExternalScripts[src]) return;
  function inject(){{
    if (window.__twExternalScripts[src]) return;
    window.__twExternalScripts[src] = true;
    var s = document.createElement('script');
    s.src = src;
    s.async = true;
    (document.head || document.documentElement).appendChild(s);
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


def render_elements_html(nodes, context, indent=1, slot_children=None, collect_head_scripts: bool = True):
    pad = "  " * indent
    out = []
    current_context = dict(context)
    needs_router_runtime = False
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
                        config.get("allow_inline_js", config.get("allowInlineJs", False)),
                    ),
                )
            )
            if not allow_raw:
                raise CompilerError(
                    "Raw `script { ... }` blocks are disabled by default (safety).",
                    token=getattr(node, "token", None),
                    file_path=getattr(node, "file_path", None),
                    suggestion=(
                        "Use `.twm` + `load @...` + events, or use declarative "
                        "`script { src \"...\" strategy afterInteractive }`. "
                        "If you must allow raw scripts, set `allow_raw_script: true` in `tw.config`."
                    ),
                )
            src = write_chunk(node.raw_js, "js")
            out.append(f'{pad}<script src="{src}"></script>\n')
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

        if isinstance(node, ElementNode):
            maybe_optimize_image(node)
            attr_str = render_attrs(node.attrs, current_context)
            event_str = render_events(node.events, current_context)
            prefix, suffix, goto_str, router_used = render_router(node.router, current_context)
            style_str = render_inline_style(node.inline_style, current_context)
            full_attrs = attr_str + event_str + goto_str + style_str
            text = html_escape(interpolate(node.text, current_context)) if node.text is not None else None

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


def _build_tw_signature(page=None, context=None):
    """
    Returns (meta_tags_html, tw_data_script_html, build_comments_html)
    These injected parts form TW Framework's signature in the HTML output.
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
        def _collect_components(nodes, seen=None):
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
        except Exception as err:
            logger.exception("Failed to collect components used for build signature")
            components_used = []

    # meta + hidden markers
    meta_html = (
        '  <!-- ⚡ Built with TW Framework -->\n'
        '  <meta charset="UTF-8">\n'
        '  <meta name="viewport" content="width=device-width, initial-scale=1.0">\n'
        '  <meta name="generator" content="TW Framework">\n'
        '  <div id="__TW__" style="display:none"></div>\n'
    )

    # __TW_DATA__ JSON blob
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
    comp_str = ", ".join(components_used) if components_used else "—"
    build_comments = (
        f'<!-- [TW] Page: {page_name} | Render: {render_mode} | Route: {route} -->\n'
        f'<!-- [TW] Components: {comp_str} -->\n'
        f'<!-- [TW] Build: {build_time} -->\n'
    )

    return meta_html, data_script, build_comments


def build_default_document(title, head_extras, style_blocks, body_html, runtime_scripts_html, page=None, context=None):
    runtime_scripts = (runtime_scripts_html + "\n") if runtime_scripts_html else ""
    meta_html, data_script, build_comments = _build_tw_signature(page, context)
    return f"""{build_comments}<!DOCTYPE html>
<html>
<head>
{meta_html}{data_script}{head_extras}{style_blocks}</head>
<body>
{body_html}{runtime_scripts}</body>
</html>"""


def build_redirect_document(title, target):
    safe_target = html_escape(target)
    return f"""<!DOCTYPE html>
<html>
<head>
  <meta http-equiv="refresh" content="0;url={safe_target}">
</head>
<body>
  <p>Redirecting to <a href="{safe_target}">{safe_target}</a>...</p>
  <script>window.location.replace({json.dumps(target)});</script>
</body>
</html>"""


_LAYOUT_VAR_RE = re.compile(r"\{([A-Za-z_][A-Za-z0-9_]*(?:\.[A-Za-z_][A-Za-z0-9_]*)*(?:\[[0-9]+\])*)\}")


def interpolate_layout_template(text, context):
    if text is None or "{" not in str(text):
        return text

    def repl(match):
        expr = match.group(1)
        value = evaluate_expression(expr, context)
        return match.group(0) if value is None else str(value)

    return _LAYOUT_VAR_RE.sub(repl, str(text))


def apply_layout_template(layout_template, title, head_extras, style_blocks, body_html, runtime_scripts_html, context, page=None):
    runtime_scripts = runtime_scripts_html or ""
    meta_html, data_script, build_comments = _build_tw_signature(page, context)
    # Inject signature into {head} placeholder
    enhanced_head = (meta_html + data_script + (head_extras or "")).rstrip()
    rendered = layout_template
    rendered = rendered.replace("{slot}", body_html)
    rendered = rendered.replace("{title}", html_escape(title))
    rendered = rendered.replace("{head}", enhanced_head)
    rendered = rendered.replace("{styles}", style_blocks.rstrip())
    rendered = rendered.replace("{scripts}", runtime_scripts)
    # Prepend build comments before <!DOCTYPE
    result = interpolate_layout_template(rendered, context)
    if result.lstrip().startswith("<!DOCTYPE") or result.lstrip().startswith("<html"):
        result = build_comments + result
    return result


def _inject_reactivity_runtime(html_text: str, page_source: str, state: dict) -> str:
    """Inject TW reactivity runtime + state init into HTML before </body>."""
    try:
        from .reactivity import get_reactivity_runtime_js, build_state_init_script
        runtime_js = get_reactivity_runtime_js()
        state_init = build_state_init_script(state)
        script = f"<script>\n{runtime_js}\n{state_init}\n</script>"
        if "</body>" in html_text:
            return html_text.replace("</body>", script + "\n</body>", 1)
        return html_text + script
    except Exception as err:
        if os.environ.get("TW_STRICT_EVAL", "").strip().lower() in {"1", "true", "yes", "on"}:
            raise
        logger.exception("Failed to inject reactivity runtime; continuing without reactivity script")
        return html_text


def _inject_on_load_inits(html_text: str, handlers) -> str:
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


def render_html(page, context, css_href):
    if page.redirect_to:
        target = interpolate(page.redirect_to, context)
        return build_redirect_document(page.title or "Redirecting", target)

    body_html, needs_router_runtime, head_scripts = render_elements_html(page.body, context)
    title = interpolate(page.title, context) if page.title else ""
    context = dict(context)
    context["_tw_render_mode"] = page.render_mode
    context["_tw_revalidate"] = page.revalidate

    layout_responsive = False
    try:
        for lname in (getattr(page, "layouts", None) or []):
            if to_bool(get_layout_meta(lname).get("responsive", False)):
                layout_responsive = True
                break
    except Exception as err:
        logger.exception("Failed to inspect layout meta for responsive mode")
        layout_responsive = False

    context["_tw_responsive"] = (
        to_bool(context.get("_tw_responsive", False))
        or to_bool(getattr(page, "responsive", False))
        or layout_responsive
    )

    head_extras = "".join(head_scripts) + build_theme_inline_script(context) + render_head_extras(page.head, context)

    style_lines = []
    if to_bool(context.get("_tw_responsive", False)):
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
        combined = "\n\n".join(render_css(sheet, context) for sheet in page.loaded_sheets)
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
    except Exception as err:
        if os.environ.get("TW_STRICT_EVAL", "").strip().lower() in {"1", "true", "yes", "on"}:
            raise
        logger.exception("Failed to compile `.twm` modules; continuing without TW module bundle")
    if needs_router_runtime:
        runtime_script_urls.append(get_router_runtime_url())
    if search_enabled:
        runtime_script_urls.append(get_search_runtime_url())
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

    if page.layouts:
        wrapped_body = body_html
        for inner_name in reversed(page.layouts[1:]):
            wrapped_body = apply_layout_fragment(load_layout(inner_name), wrapped_body, context)

        layout_template = load_layout(page.layouts[0])
        layout_html = apply_layout_template(
            layout_template,
            title,
            head_extras,
            style_blocks,
            wrapped_body,
            runtime_scripts_html,
            context,
            page=page,
        )

        if page_state or reactive_enabled:
            layout_html = _inject_reactivity_runtime(layout_html, raw_source, page_state)
        layout_html = _inject_on_load_inits(layout_html, getattr(page, "on_load_inits", []) or [])
        return layout_html

    final_doc = build_default_document(
        title,
        head_extras,
        style_blocks,
        body_html,
        runtime_scripts_html,
        page=page,
        context=context,
    )

    if page_state or reactive_enabled:
        final_doc = _inject_reactivity_runtime(final_doc, raw_source, page_state)

    final_doc = _inject_on_load_inits(final_doc, getattr(page, "on_load_inits", []) or [])
    return final_doc


def parse_layout_chain(raw_value):
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
    # Normalize separators to comma
    normalized = text.replace(">", ",")
    parts = [part.strip() for part in normalized.split(",") if part.strip()]
    return parts


def apply_layout_fragment(layout_template, body_html, context):
    """
    Apply an inner (fragment) layout around body_html.
    Inner layouts should ideally NOT include <html>/<head>/<body>; they are wrappers around `{slot}`.
    """
    rendered = layout_template.replace("{slot}", body_html)
    # Inner fragments should not re-inject global document placeholders
    rendered = rendered.replace("{head}", "")
    rendered = rendered.replace("{styles}", "")
    rendered = rendered.replace("{scripts}", "")
    rendered = rendered.replace("{title}", "")
    return interpolate_layout_template(rendered, context)


_LOAD_JSON_KEY_RE = re.compile(r"^[A-Za-z_][A-Za-z0-9_]*$")


def load_external_json(rel_path, base_dir):
    full_path = resolve_source_path(rel_path, base_dir)
    if not os.path.exists(full_path):
        raise FileNotFoundError(f"load: json not found -> {full_path}")
    with open(full_path, "r", encoding="utf-8") as f:
        return json.load(f)


def infer_json_context_key(rel_path):
    base = os.path.basename(rel_path)
    stem = base[:-5] if base.lower().endswith(".json") else os.path.splitext(base)[0]
    if not _LOAD_JSON_KEY_RE.match(stem):
        raise ValueError(f"Invalid JSON context key inferred from filename: {stem}")
    return stem


def load_page_data(tw_path):
    base, ext = os.path.splitext(tw_path)
    json_path = base + ".json" if ext.lower() == ".tw" else tw_path + ".json"
    if os.path.exists(json_path):
        try:
            with open(json_path, "r", encoding="utf-8") as f:
                return json.load(f)
        except Exception as err:
            log(f"⚠️ Failed to parse page data JSON: {json_path} ({err})", level="warning")
            return {}
    return {}


def load_page_ast_from_file(tw_path):
    raw = read_text_file(tw_path)
    tokens = tokenize_tw(raw)
    ast = build_tw_ast(tokens, os.path.dirname(tw_path), tw_path, raw)
    ast._tw_source_path = tw_path
    return ast


def load_dynamic_items(tw_path):
    base, ext = os.path.splitext(tw_path)
    json_path = base + ".json" if ext.lower() == ".tw" else tw_path + ".json"
    if not os.path.exists(json_path):
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


def classify_dynamic_route_file(filename):
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


def resolve_dynamic_segments(page_info, item):
    raw_value = item.get(page_info["param"], item.get("id", item.get("slug", "unknown")))
    route_kind = page_info.get("route_kind", "single")

    if route_kind == "single":
        return [str(raw_value)]

    if raw_value is None or raw_value == "":
        return [] if route_kind == "optional-catch-all" else ["unknown"]

    if isinstance(raw_value, (list, tuple)):
        segments = [str(part).strip("/") for part in raw_value if str(part).strip("/")]
    else:
        segments = [part for part in str(raw_value).strip("/").split("/") if part]

    if not segments and route_kind != "optional-catch-all":
        return ["unknown"]
    return segments


def load_config():
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
                continue
            key, value = line.split(":", 1)
            while len(stack) > 1 and indent <= stack[-1][0]:
                stack.pop()
            current = stack[-1][1]
            key = key.strip()
            value = value.strip()
            if value == "":
                nested = {}
                current[key] = nested
                stack.append((indent, nested))
                continue
            current[key] = parse_config_scalar(value)
    return config


def discover_pages():
    pages = []
    if os.path.exists(INDEX_FILE):
        pages.append({"type": "static", "path": INDEX_FILE, "rel_dir": "", "name": "index"})
    if os.path.exists(PAGES_DIR):
        for root, _, files in os.walk(PAGES_DIR):
            rel_dir = os.path.relpath(root, PAGES_DIR)
            rel_dir = normalize_route_directory(rel_dir)
            for fname in sorted(files):
                if not fname.endswith(".tw"):
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


def copy_assets():
    ASSET_URL_MAP.clear()
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
                with open(full_src, "rb") as f:
                    digest = content_hash(f.read(), length=8)
                name, ext = os.path.splitext(filename)
                hashed_name = f"{name}.{digest}{ext}"
                full_dst = os.path.join(target_dir, hashed_name)
                shutil.copy2(full_src, full_dst)

                rel_asset_dir = f"/assets/{sub}"
                if rel_dir:
                    rel_asset_dir += "/" + rel_dir.replace(os.sep, "/")
                original_url = f"{rel_asset_dir}/{filename}"
                hashed_url = f"{rel_asset_dir}/{hashed_name}"
                ASSET_URL_MAP[original_url] = hashed_url


def verify_api_isolated():
    if os.path.exists(API_DIR):
        log("  🔒 api/ folder detected — kept server-only, not included in build output.")


def read_global_stylesheet():
    if not os.path.exists(STYLE_FILE):
        return "", None
    raw = read_text_file(STYLE_FILE)
    sheet = build_tss_ast_from_text(raw)
    css_content = render_css(sheet)
    if MINIFY_OUTPUT:
        css_content = minify_css_content(css_content)
    css_url = write_chunk(css_content, "css")
    return css_url, sheet


def create_base_context(page_ast, tw_path):
    context = {}
    for key, value in page_ast.let_vars.items():
        context[key] = value
    for entry in getattr(page_ast, "loaded_json", []) or []:
        if not isinstance(entry, dict):
            continue
        key = entry.get("key")
        rel_path = entry.get("path")
        if not key or not rel_path:
            continue
        try:
            payload = load_external_json(rel_path, os.path.dirname(tw_path))
        except FileNotFoundError as e:
            raise CompilerError(str(e), file_path=tw_path)
        context[key] = payload
    config = load_config()
    context["config"] = config
    context["site"] = config
    context["env"] = dict(os.environ)
    return context


def build_one_page(page_info, css_url):
    tw_path = page_info["path"]
    page_ast = load_page_ast_from_file(tw_path)

    if page_info["type"] == "static":
        config = load_config()
        pretty_urls = to_bool(config.get("pretty_urls", config.get("prettyUrls", False)))
        route_path = route_path_from_page_info(page_info)
        context = build_page_context(page_info, page_ast, tw_path, route_path=route_path)
        html = render_html(page_ast, context, css_url)
        if MINIFY_OUTPUT:
            html = minify_html_content(html)
        out_dir = os.path.join(BUILD_DIR, page_info["rel_dir"]) if page_info["rel_dir"] else BUILD_DIR
        if pretty_urls and page_info["name"] != "index":
            # /about -> dist/about/index.html (clean URLs on static hosts)
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


def parse_cli_args():
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


def get_page_manifest_entry(manifest, page_info):
    return manifest.get("pages", {}).get(page_cache_key(page_info))


def should_rebuild_page(page_info, dependencies, manifest, options):
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


def update_page_manifest_entry(manifest, page_info, dependencies, outputs, metadata=None):
    key = page_cache_key(page_info)
    manifest.setdefault("pages", {})
    previous = manifest["pages"].get(key, {})
    previous_outputs = set(previous.get("outputs", []))
    current_outputs = set(outputs)
    stale_outputs = sorted(previous_outputs - current_outputs)
    cleanup_outputs(stale_outputs)
    if metadata is None:
        page_ast = load_page_ast_from_file(page_info["path"])
        metadata = collect_page_metadata(page_info, page_ast=page_ast, pipeline="legacy")
    manifest["pages"][key] = {
        "type": page_info["type"],
        "path": normalize_path(page_info["path"]),
        "dependencies": sorted(normalize_path(dep) for dep in dependencies),
        "signature": compute_dependency_signature(dependencies),
        "fingerprints": collect_dependency_fingerprints(dependencies),
        "outputs": sorted(normalize_path(out) for out in outputs),
        "metadata": metadata,
    }


def build_page_job(page_info, css_url):
    outputs = build_one_page(page_info, css_url)
    return {
        "page_info": page_info,
        "outputs": outputs,
    }


def print_compiler_error(page_info, err):
    if isinstance(err, CompilerError) and page_info.get("path") and os.path.exists(page_info["path"]):
        raw = read_text_file(page_info["path"])
        emitter = DiagnosticEmitter(page_info["path"], raw)
        log(emitter.format(err), level="error")
    else:
        log(f"  ❌ Error in {page_info['path']}: {err}", level="error")


def main():
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
                    print_compiler_error(page_info, err)

    save_build_manifest(manifest)

    log(
        f"\n🚀 Build complete — {built} page(s) generated, "
        f"{skipped} skipped, {removed} removed → {BUILD_DIR}"
    )


def _token_to_dict(token):
    if hasattr(token, "to_dict"):
        return token.to_dict()
    return {
        "type": getattr(token, "type", ""),
        "value": getattr(token, "value", ""),
        "line": getattr(token, "line", 0),
        "col": getattr(token, "col", 0),
    }


def _diagnostic_to_payload(err, fallback_file_path="", *, phase=None):
    if isinstance(err, Diagnostic):
        diagnostic = err
    elif isinstance(err, CompilerError):
        diagnostic = err.to_diagnostic(fallback_file_path)
    elif isinstance(err, FileNotFoundError):
        message = str(err)
        code = "TW2404" if "Layout not found" in message else "TW2405" if "Component not found" in message else "TW2400"
        suggestion = None
        if code == "TW2404":
            suggestion = "Add the layout file to `[home]/layouts/<name>.tw`, or update the page's `layout` value."
        elif code == "TW2405":
            suggestion = "Add the component file to `[home]/components`, or fix the import name."
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
        "end_line": getattr(diagnostic, "end_line", diagnostic.line),
        "end_col": getattr(diagnostic, "end_col", diagnostic.col),
        "suggestion": diagnostic.suggestion,
        "notes": list(diagnostic.notes or []),
        "phase": phase or getattr(diagnostic, "phase", None),
        "exception_type": getattr(diagnostic, "exception_type", None) or err.__class__.__name__,
    }


def _summarize_diagnostics_payload(items):
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
        severity = str(item.get("severity", "info") or "info").lower()
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


def _pipeline_metadata_from_program(program, *, file_path, route_path, dependencies):
    layouts = list(program.meta.layouts or [])
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


def compile_text_pipeline(text, *, base_dir=".", file_path="<memory>", context=None, css_href=None, route_path=None, capture_errors=False, dependency_paths=None):
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

    if program is not None:
        try:
            diagnostics = analyze_program(program, context=context)
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


def compile_file_pipeline(path, context=None, css_href=None, route_path=None, capture_errors=False):
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
        logger.warning("Dependency collection failed for %s: %s", path, err)
        dependency_paths = [path]
    except Exception as err:
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
