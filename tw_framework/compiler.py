import os
import re
import json
import ast
import copy
import shutil
import hashlib
import difflib
import argparse
import threading
import concurrent.futures
from dataclasses import dataclass


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
TAG_NAME_RE = re.compile(r"^[A-Za-z][A-Za-z0-9_-]*$")
DYNAMIC_FILE_RE = re.compile(r"^\[(\w+)\]\.tw$")
CATCH_ALL_FILE_RE = re.compile(r"^\[\.\.\.(\w+)\]\.tw$")
OPTIONAL_CATCH_ALL_FILE_RE = re.compile(r"^\[\[\.\.\.(\w+)\]\]\.tw$")

INLINE_SCRIPTS = {}
_SCRIPT_COUNTER = 0
_CHUNK_CACHE = {}
_COMPONENT_AST_CACHE = {}
_COMPONENT_EXISTS_CACHE = {}
_COMPONENT_PATH_CACHE = {}
_LAYOUT_CACHE = {}
_LAYOUT_META_CACHE = {}
_COMPONENT_DEP_GRAPH_CACHE = {}
_COMPONENT_STYLESHEET_PATHS = {}
_CHUNK_LOCK = threading.Lock()
_SCRIPT_LOCK = threading.Lock()

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
        if path == self.file_path:
            lines = self.lines
        else:
            try:
                lines = read_text_file(path).splitlines()
            except Exception:
                lines = self.lines

        if not diagnostic.line:
            out = [f"❌ {diagnostic.severity.upper()} [{diagnostic.code}] {path}", diagnostic.message]
            if diagnostic.suggestion:
                out.append(f"Hint: {diagnostic.suggestion}")
            for note in diagnostic.notes or []:
                out.append(f"Note: {note}")
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
        return "\n".join(out)


def print_diagnostic(diagnostic):
    path = diagnostic.file_path or ""
    source = ""
    if path and os.path.exists(path):
        try:
            source = read_text_file(path)
        except Exception:
            source = ""
    emitter = DiagnosticEmitter(path, source)
    print(emitter.format(diagnostic))


def read_text_file(path):
    with open(path, "r", encoding="utf-8") as f:
        return f.read()


def normalize_path(path):
    return os.path.normpath(path)


def minify_html_content(text):
    text = re.sub(r">\\s+<", "><", text)
    text = re.sub(r"\n\s*\n+", "\n", text)
    return text.strip()


def minify_css_content(text):
    text = re.sub(r"/\\*.*?\\*/", "", text, flags=re.S)
    text = re.sub(r"\\s+", " ", text)
    text = re.sub(r"\\s*([{}:;,])\\s*", r"\\1", text)
    return text.strip()


def minify_js_content(text):
    text = re.sub(r"/\\*.*?\\*/", "", text, flags=re.S)
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
    except Exception:
        return path


def load_build_manifest():
    if not os.path.exists(BUILD_MANIFEST_FILE):
        return {"version": 1, "pages": {}}
    try:
        with open(BUILD_MANIFEST_FILE, "r", encoding="utf-8") as f:
            data = json.load(f)
        if not isinstance(data, dict):
            return {"version": 1, "pages": {}}
        data.setdefault("version", 1)
        data.setdefault("pages", {})
        return data
    except Exception:
        return {"version": 1, "pages": {}}


def save_build_manifest(manifest):
    os.makedirs(os.path.dirname(BUILD_MANIFEST_FILE), exist_ok=True)
    with open(BUILD_MANIFEST_FILE, "w", encoding="utf-8") as f:
        json.dump(manifest, f, indent=2, sort_keys=True)


def save_dependency_graph(dependency_map):
    os.makedirs(os.path.dirname(DEPENDENCY_GRAPH_FILE), exist_ok=True)
    reverse = {}
    for page_key, dependencies in sorted(dependency_map.items()):
        for dependency in dependencies:
            dep_key = normalize_path(dependency)
            reverse.setdefault(dep_key, []).append(page_key)
    payload = {
        "version": 1,
        "forward": {page: sorted(normalize_path(dep) for dep in deps) for page, deps in sorted(dependency_map.items())},
        "reverse": {dep: sorted(set(pages)) for dep, pages in sorted(reverse.items())},
    }
    with open(DEPENDENCY_GRAPH_FILE, "w", encoding="utf-8") as f:
        json.dump(payload, f, indent=2, sort_keys=True)


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
        self.redirect_to = None
        self.rewrite_to = None
        self.head = HeadNode()
        self.body = []
        self.loaded_sheets = []
        self.loaded_json = []
        self.let_vars = {}
        # Optional responsive helpers (enabled via `tw@responsive true|false`)
        self.responsive = False


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
    def __init__(self, raw_js):
        self.tag = "__script__"
        self.raw_js = raw_js
        self.children = []


class StyleSheetNode:
    def __init__(self):
        self.rules = []


class RuleNode:
    def __init__(self, selector):
        self.selector = selector
        self.declarations = []


def is_identifier_boundary_char(ch):
    return not (ch.isalnum() or ch == "_")


def tokenize(code, allow_inline_scripts=False):
    global _SCRIPT_COUNTER

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

        tokens.append(Token("WORD", word, start_line, start_col))

    return tokens


def tokenize_tw(code):
    return tokenize(code, allow_inline_scripts=True)


def classify_known_prop(name):
    nl = name.lower()
    if nl in ROUTER_KEYS:
        return "router"
    if nl in EVENTS:
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
    if name in _COMPONENT_EXISTS_CACHE:
        return _COMPONENT_EXISTS_CACHE[name]
    path = resolve_component_path(name)
    found = bool(path and os.path.exists(path))
    _COMPONENT_EXISTS_CACHE[name] = found
    return found


def is_component_name(name):
    # Only treat it as a component if it actually exists.
    # This avoids errors like `Section {}` being treated as a missing component.
    return component_exists(name)


def resolve_component_path(name):
    # 1) Support nested component folders via `import "ui/Button"` (path-like names)
    if "/" in str(name) or "\\" in str(name):
        rel = str(name).replace("\\", "/").lstrip("/")
        return os.path.join(COMPONENTS_DIR, rel + ".tw")

    # 2) Fast path: direct component file
    direct = os.path.join(COMPONENTS_DIR, f"{name}.tw")
    if os.path.exists(direct):
        return direct

    # 3) Fallback: search in subfolders (allows organizing components in nested dirs)
    if name in _COMPONENT_PATH_CACHE:
        return _COMPONENT_PATH_CACHE[name]
    found = ""
    if os.path.isdir(COMPONENTS_DIR):
        target = f"{name}.tw"
        for root, _, files in os.walk(COMPONENTS_DIR):
            if target in files:
                found = os.path.join(root, target)
                break
    _COMPONENT_PATH_CACHE[name] = found or direct
    return _COMPONENT_PATH_CACHE[name]


def extract_directives_from_source(raw, base_dir):
    imports = IMPORT_RE.findall(raw)
    layouts = []
    for quoted, bare in LAYOUT_RE.findall(raw):
        name = quoted or bare
        if name:
            layouts.append(name)
    stylesheets = []
    json_files = []
    for quoted, atpath in LOAD_RE.findall(raw):
        rel_path = quoted or atpath.lstrip("@")
        full_path = normalize_path(os.path.join(base_dir, rel_path))
        if rel_path.lower().endswith(".json"):
            json_files.append(full_path)
        else:
            stylesheets.append(full_path)
    return {
        "imports": imports,
        "layouts": layouts,
        "stylesheets": stylesheets,
        "json_files": json_files,
    }


def collect_component_dependencies(name, stack=None, seen=None):
    if name in _COMPONENT_DEP_GRAPH_CACHE:
        return set(_COMPONENT_DEP_GRAPH_CACHE[name])

    stack = list(stack or [])
    seen = seen or set()

    if name in stack:
        chain = " -> ".join(stack + [name])
        raise CompilerError(
            f"Circular component import detected: {chain}",
            file_path=resolve_component_path(name),
            suggestion="Import graph ko acyclic rakho ya shared code ko alag component me nikalo.",
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

    for child_name in directives["imports"]:
        deps.update(collect_component_dependencies(child_name, stack + [name], seen))

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

    for layout_name in directives["layouts"]:
        layout_path = normalize_path(os.path.join(LAYOUTS_DIR, f"{layout_name}.tw"))
        deps.add(layout_path)
        if os.path.exists(layout_path):
            layout_raw = read_text_file(layout_path)
            for quoted, atpath in LAYOUT_LOAD_RE.findall(layout_raw):
                rel = quoted or atpath.lstrip("@")
                loaded_path = normalize_path(os.path.join(HOME_DIR, rel))
                deps.add(loaded_path)
                if loaded_path.endswith(".tw") and os.path.exists(loaded_path):
                    # one level deep: if that component itself loads a stylesheet, track it too
                    inner_raw = read_text_file(loaded_path)
                    for q2, a2 in COMPONENT_LOAD_RE.findall(inner_raw):
                        rel2 = q2 or a2.lstrip("@")
                        deps.add(normalize_path(os.path.join(HOME_DIR, rel2)))

    for component_name in directives["imports"]:
        deps.update(collect_component_dependencies(component_name))

    return sorted(deps)


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
        except Exception:
            # Allow trailing commas and a slightly more forgiving literal syntax
            # via Python's safe literal parser.
            try:
                return ast.literal_eval(stripped)
            except Exception:
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
        except Exception:
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
    except Exception:
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
    except Exception:
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
            suggestion="Symbol define karo, JSON load/let/import use karo, ya placeholder ko literal text rakhna ho to braces hata do.",
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
                except Exception:
                    pass
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
                            suggestion="Duplicate attribute remove karo taaki final HTML predictable rahe.",
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


def finalize_css_value(css_prop, raw_value, context):
    value = interpolate(raw_value, context)
    if value is None:
        value = ""
    if css_prop in NUMERIC_CSS and isinstance(value, (int, float)):
        return f"{value}px"
    if css_prop in NUMERIC_CSS and isinstance(value, str):
        stripped = value.strip()
        if NUM_RE.match(stripped):
            return f"{stripped}px"
        # Multi-value numeric shorthand (eg `padding 12 18` or `margin 8 12 8 12`)
        parts = [p for p in stripped.split() if p]
        if parts and all(NUM_RE.match(p) for p in parts):
            return " ".join(f"{p}px" for p in parts)
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


def parse_value_token(tokens, i):
    token = peek(tokens, i)
    if not token:
        return True, i
    if token.type == "NL":
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
    suggestion = f"Did you mean `{guess[0]}`?" if guess else "Known keys use CSS props, HTML attrs, events, ya child elements."
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
    rel_path = quoted or atpath.lstrip("@")
    full_path = os.path.normpath(os.path.join(base_dir, rel_path))
    if not os.path.exists(full_path):
        raise CompilerError(f"load: file not found -> {full_path}", suggestion=f"Expected: `{full_path}`")
    sheet = build_tss_ast_from_text(read_text_file(full_path))
    raw = COMPONENT_LOAD_RE.sub("", raw, count=1)
    return raw, sheet


def load_component_ast(name):
    if name in _COMPONENT_AST_CACHE:
        return copy.deepcopy(_COMPONENT_AST_CACHE[name])
    collect_component_dependencies(name)
    path = resolve_component_path(name)
    if not os.path.exists(path):
        raise FileNotFoundError(f"Component not found: {path}")
    raw = read_text_file(path)
    raw, comp_sheet = extract_component_load_directive(raw, HOME_DIR)
    if comp_sheet is not None:
        _COMPONENT_STYLESHEET_PATHS[normalize_path(path)] = comp_sheet
    tokens = tokenize_tw(raw)
    nodes, _ = build_elements(tokens, 0, path, raw)
    _COMPONENT_AST_CACHE[name] = nodes
    return copy.deepcopy(nodes)


def load_layout(name):
    if name in _LAYOUT_CACHE:
        return _LAYOUT_CACHE[name]
    path = os.path.join(LAYOUTS_DIR, f"{name}.tw")
    if not os.path.exists(path):
        raise FileNotFoundError(f"Layout not found: {path}")
    raw = read_text_file(path)

    meta = _LAYOUT_META_CACHE.get(name) or {}
    # Scan directive: `tw@responsive true|false` (line-based)
    m = LAYOUT_RESPONSIVE_RE.search(raw or "")
    if m:
        meta["responsive"] = to_bool(parse_config_scalar(m.group(1)))
        raw = LAYOUT_RESPONSIVE_RE.sub("", raw, count=1).lstrip("\n")
    _LAYOUT_META_CACHE[name] = meta

    raw = resolve_layout_loads(raw, HOME_DIR)

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
        rel_path = quoted or atpath.lstrip("@")
        full_path = os.path.normpath(os.path.join(base_dir, rel_path))
        if not os.path.exists(full_path):
            raise CompilerError(
                f"load: file not found in layout -> {full_path}",
                suggestion=f"Expected: `{full_path}`",
            )

        if full_path.endswith(".tw"):
            comp_raw = read_text_file(full_path)
            comp_raw, comp_sheet = extract_component_load_directive(comp_raw, HOME_DIR)
            comp_tokens = tokenize_tw(comp_raw)
            comp_nodes, _ = build_elements(comp_tokens, 0, full_path, comp_raw)
            html, _needs_router = render_elements_html(comp_nodes, {})
            if comp_sheet is not None:
                html = f"<style>\n{render_css(comp_sheet, {})}</style>\n{html}"
            return html

        sheet = build_tss_ast_from_text(read_text_file(full_path))
        return f"<style>\n{render_css(sheet, {})}</style>"

    return LAYOUT_LOAD_RE.sub(repl, raw)


def get_layout_meta(name):
    # Ensures layout is loaded at least once (populates meta cache)
    if name not in _LAYOUT_CACHE:
        load_layout(name)
    return _LAYOUT_META_CACHE.get(name, {})


def load_external_stylesheet(rel_path, base_dir):
    full_path = os.path.normpath(os.path.join(base_dir, rel_path))
    if not os.path.exists(full_path):
        raise FileNotFoundError(f"load: stylesheet not found -> {full_path}")
    return build_tss_ast_from_text(read_text_file(full_path))


def write_chunk(content, ext):
    if MINIFY_OUTPUT and ext == "js":
        content = minify_js_content(content)
    digest = hashlib.md5(content.encode("utf-8")).hexdigest()[:8]
    with _CHUNK_LOCK:
        if digest in _CHUNK_CACHE:
            return _CHUNK_CACHE[digest]
        fname = f"{digest}.{ext}"
        os.makedirs(CHUNKS_DIR, exist_ok=True)
        out_path = os.path.join(CHUNKS_DIR, fname)
        if not os.path.exists(out_path):
            with open(out_path, "w", encoding="utf-8") as f:
                f.write(content)
        url = CHUNKS_URL_PREFIX + fname
        _CHUNK_CACHE[digest] = url
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


def parse_script_placeholder(tokens, i):
    token = peek(tokens, i)
    m = SCRIPT_PLACEHOLDER_RE.match(token.value)
    if not m:
        raise CompilerError("Invalid script placeholder", token=token)
    uid = int(m.group(1))
    return ScriptNode(INLINE_SCRIPTS.get(uid, "")), i + 1


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

    if component_exists(name):
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
            suggestion="Angle brackets mat use karo. TW me aise likho: `nav { ... }`, `section { ... }` (without `<` `>`).",
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
        return parse_script_placeholder(tokens, i)
    if token.type == "WORD" and TAG_NAME_RE.match(token.value):
        return parse_element_or_component(tokens, i, file_path, source)
    raise CompilerError(f"Unexpected token: `{token.value}`", token=token)


def parse_element_block(tokens, i, node, file_path, source):
    while i < len(tokens):
        token = peek(tokens, i)
        if token.type == "NL":
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
            child, i = parse_script_placeholder(tokens, i)
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
                    node.events.append((prop_name.lower(), raw_value))
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
        suggestion="Ek `{` open hua hai lekin matching `}` nahi mila. Braces count check karo.",
    )


def parse_component_block(tokens, i, node, file_path, source):
    while i < len(tokens):
        token = peek(tokens, i)
        if token.type == "NL":
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
            child, i = parse_script_placeholder(tokens, i)
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
        suggestion="Ek `{` open hua hai lekin matching `}` nahi mila. Braces count check karo.",
    )


def build_elements(tokens, i, file_path, source, require_closing_brace=False, start_token=None):
    nodes = []
    while i < len(tokens):
        token = peek(tokens, i)
        if token.type == "NL":
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
            suggestion="Ek `{` open hua hai lekin matching `}` nahi mila. Braces count check karo.",
        )
    return nodes, i


def parse_head_block(tokens, i, head):
    while i < len(tokens):
        token = peek(tokens, i)
        if token.type == "NL":
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
        suggestion="`head { ... }` ka closing `}` missing lag raha hai.",
    )


def parse_page_block(tokens, i, page):
    while i < len(tokens):
        token = peek(tokens, i)
        if token.type == "NL":
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
                    suggestion="Use `static`, `server`, ya `edge`.",
                )
            page.render_mode = render_mode
            continue
        if key == "revalidate":
            page.revalidate = parse_config_scalar(value)
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
            suggestion="Use `title`, `layout`, `render`, `revalidate`, `redirect`, ya `rewrite`.",
        )
    raise CompilerError(
        "Missing closing `}` for `page` block",
        token=peek(tokens, max(len(tokens) - 1, 0)),
        suggestion="`page { ... }` ka closing `}` missing lag raha hai.",
    )


def build_tw_ast(tokens, base_dir, file_path, source):
    page = PageNode()
    i = 0
    while i < len(tokens):
        token = peek(tokens, i)
        if token.type == "NL":
            i += 1
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

        if token.type == "WORD" and token.value == "load":
            i += 1
            path_token = peek(tokens, i)
            is_valid = path_token and (
                path_token.type == "STRING"
                or (path_token.type == "WORD" and path_token.value.startswith("@"))
            )
            if not is_valid:
                raise CompilerError("Expected path after `load`", token=peek(tokens, i - 1))
            raw_path = path_token.value.lstrip("@") if path_token.type == "WORD" else path_token.value
            if str(raw_path).lower().endswith(".json"):
                try:
                    key = infer_json_context_key(raw_path)
                except ValueError as e:
                    raise CompilerError(str(e), token=path_token)
                page.loaded_json.append({"key": key, "path": raw_path})
            else:
                page.loaded_sheets.append(load_external_stylesheet(raw_path, base_dir))
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

        raise CompilerError(f"Unexpected top-level token: `{token.value}`", token=token)

    _attach_component_stylesheets(page, source)
    return page


def _attach_component_stylesheets(page, source):
    """Components can `load` their own .tss file. If this page (directly or
    via nested component imports) ends up using such a component, pull that
    stylesheet in automatically -- same place page-level `load` results land."""
    seen_paths = set()
    for comp_name in IMPORT_RE.findall(source):
        try:
            dep_paths = collect_component_dependencies(comp_name)
        except CompilerError:
            continue
        for dep_path in dep_paths:
            if dep_path in _COMPONENT_STYLESHEET_PATHS and dep_path not in seen_paths:
                seen_paths.add(dep_path)
                page.loaded_sheets.append(_COMPONENT_STYLESHEET_PATHS[dep_path])



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
        rule = RuleNode(selector)
        for raw_line in body.splitlines():
            line = raw_line.strip()
            if not line:
                continue
            parts = line.split(None, 1)
            prop = parts[0].strip(":;,")
            val = parts[1].strip().strip(";") if len(parts) > 1 else "true"
            rule.declarations.append((normalize_css_prop(prop), val))
        sheet.rules.append(rule)

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
            js = f"{handler}(event)"
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


def render_css(sheet, context=None):
    context = context or {}
    out = []
    for rule in sheet.rules:
        out.append(f"{rule.selector} {{")
        for prop, value in rule.declarations:
            out.append(f"    {prop}: {finalize_css_value(prop, value, context)};")
        out.append("}")
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
            except Exception:
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


def render_elements_html(nodes, context, indent=1, slot_children=None):
    pad = "  " * indent
    out = []
    current_context = dict(context)
    needs_router_runtime = False
    component_stack = list(current_context.get("_tw_component_stack") or [])

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
                html, router_used = render_elements_html(node.children, child_context, indent, slot_children)
                out.append(html)
                needs_router_runtime = needs_router_runtime or router_used
            continue

        if isinstance(node, IfNode):
            branch = node.children if eval_condition(node.condition, current_context) else node.else_children
            html, router_used = render_elements_html(branch, current_context, indent, slot_children)
            out.append(html)
            needs_router_runtime = needs_router_runtime or router_used
            continue

        if isinstance(node, ScriptNode):
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
                    suggestion="Component ke andar wahi component (direct/indirect) call ho raha hai. Recursion break karo ya structure change karo.",
                )
            try:
                component_nodes = load_component_ast(node.name)
            except Exception as err:
                # Show the error at the callsite (page/component file where it was used)
                raise CompilerError(
                    f"Failed to load component: `{node.name}` ({err})",
                    token=getattr(node, "token", None),
                    file_path=getattr(node, "file_path", None),
                    suggestion="Check `[home]/components` me file exist karti hai ya nahi. HTML element chahiye to lowercase tag use karo (eg `section`, `nav`).",
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
            html, router_used = render_elements_html(component_nodes, component_context, indent, node.children)
            out.append(html)
            needs_router_runtime = needs_router_runtime or router_used
            continue

        if isinstance(node, ElementNode) and node.tag == "slot":
            html, router_used = render_elements_html(slot_children or [], current_context, indent, slot_children)
            out.append(html)
            needs_router_runtime = needs_router_runtime or router_used
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
                html, child_router_used = render_elements_html(node.children, current_context, indent + 1, slot_children)
                out.append(html)
                out.append(f"{pad}</{node.tag}>{suffix}\n")
                needs_router_runtime = needs_router_runtime or router_used or child_router_used
            else:
                out.append(f"{prefix}{pad}<{node.tag}{full_attrs}>{text or ''}</{node.tag}>{suffix}\n")
                needs_router_runtime = needs_router_runtime or router_used

    return "".join(out), needs_router_runtime


def build_default_document(title, head_extras, style_blocks, body_html, runtime_scripts_html):
    runtime_scripts = (runtime_scripts_html + "\n") if runtime_scripts_html else ""
    return f"""<!DOCTYPE html>
<html>
<head>
{head_extras}{style_blocks}</head>
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


def apply_layout_template(layout_template, title, head_extras, style_blocks, body_html, runtime_scripts_html, context):
    runtime_scripts = runtime_scripts_html or ""
    rendered = layout_template
    rendered = rendered.replace("{slot}", body_html)
    rendered = rendered.replace("{title}", html_escape(title))
    rendered = rendered.replace("{head}", (head_extras or "").rstrip())
    rendered = rendered.replace("{styles}", style_blocks.rstrip())
    rendered = rendered.replace("{scripts}", runtime_scripts)
    return interpolate_layout_template(rendered, context)


def render_html(page, context, css_href):
    if page.redirect_to:
        target = interpolate(page.redirect_to, context)
        return build_redirect_document(page.title or "Redirecting", target)

    body_html, needs_router_runtime = render_elements_html(page.body, context)
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
    except Exception:
        layout_responsive = False
    context["_tw_responsive"] = (
        to_bool(context.get("_tw_responsive", False))
        or to_bool(getattr(page, "responsive", False))
        or layout_responsive
    )
    head_extras = build_theme_inline_script(context) + render_head_extras(page.head, context)

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
    if needs_router_runtime:
        runtime_script_urls.append(get_router_runtime_url())
    if search_enabled:
        runtime_script_urls.append(get_search_runtime_url())
    runtime_scripts_html = "\n".join(f'<script src="{url}"></script>' for url in runtime_script_urls if url)

    if page.layouts:
        # Nested layout support:
        # - `page.layouts[0]` is treated as the outer (document) layout
        # - any additional layouts are treated as inner wrappers (fragments) around `{slot}`
        wrapped_body = body_html
        for inner_name in reversed(page.layouts[1:]):
            wrapped_body = apply_layout_fragment(load_layout(inner_name), wrapped_body, context)
        layout_template = load_layout(page.layouts[0])
        return apply_layout_template(layout_template, title, head_extras, style_blocks, wrapped_body, runtime_scripts_html, context)

    return build_default_document(title, head_extras, style_blocks, body_html, runtime_scripts_html)


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
    full_path = os.path.normpath(os.path.join(base_dir, rel_path))
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
    json_path = tw_path[:-3] + ".json"
    if os.path.exists(json_path):
        with open(json_path, "r", encoding="utf-8") as f:
            return json.load(f)
    return {}


def load_page_ast_from_file(tw_path):
    raw = read_text_file(tw_path)
    tokens = tokenize_tw(raw)
    return build_tw_ast(tokens, os.path.dirname(tw_path), tw_path, raw)


def load_dynamic_items(tw_path):
    json_path = tw_path[:-3] + ".json"
    if not os.path.exists(json_path):
        return []
    with open(json_path, "r", encoding="utf-8") as f:
        data = json.load(f)
    if isinstance(data, list):
        return data
    if isinstance(data, dict) and isinstance(data.get("items"), list):
        return data["items"]
    return []


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
        for line in f:
            line = line.strip()
            if not line or line.startswith("#") or ":" not in line:
                continue
            key, value = line.split(":", 1)
            config[key.strip()] = parse_config_scalar(value.strip())
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
                    digest = hashlib.md5(f.read()).hexdigest()[:8]
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
        print("  🔒 api/ folder detected — kept server-only, not included in build output.")


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
        context = create_base_context(page_ast, tw_path)
        route_path = "/" + "/".join(filter(None, [page_info["rel_dir"], "" if page_info["name"] == "index" else page_info["name"]]))
        context["_tw_route"] = route_path or "/"
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
        slug = "/".join(segments)
        context = create_base_context(page_ast, tw_path)
        context.update(item)
        context[page_info["param"]] = slug
        if page_info.get("route_kind") != "single":
            context[page_info["param"] + "Segments"] = segments
        route_parts = []
        if page_info["rel_dir"]:
            route_parts.append(page_info["rel_dir"])
        route_parts.extend(segments)
        context["_tw_route"] = "/" + "/".join(filter(None, route_parts))
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
    parser.add_argument("--force", action="store_true", help="Sab pages ko rebuild karo")
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


def update_page_manifest_entry(manifest, page_info, dependencies, outputs):
    key = page_cache_key(page_info)
    manifest.setdefault("pages", {})
    previous = manifest["pages"].get(key, {})
    previous_outputs = set(previous.get("outputs", []))
    current_outputs = set(outputs)
    stale_outputs = sorted(previous_outputs - current_outputs)
    cleanup_outputs(stale_outputs)
    manifest["pages"][key] = {
        "type": page_info["type"],
        "path": normalize_path(page_info["path"]),
        "dependencies": sorted(normalize_path(dep) for dep in dependencies),
        "signature": compute_dependency_signature(dependencies),
        "fingerprints": collect_dependency_fingerprints(dependencies),
        "outputs": sorted(normalize_path(out) for out in outputs),
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
        print(emitter.format(err))
    else:
        print(f"  ❌ Error in {page_info['path']}: {err}")


def main():
    options = parse_cli_args()
    config = load_config()
    print(f"🔧 Building: {config.get('name', 'My Site')}\n")

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
                print(f"  ⏭️  {safe_relpath(page_info['path'], PROJECT_ROOT)} ({reason})")
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
                        print(f"  ✅ {rel_out}")
                        built += 1
                except Exception as err:
                    print_compiler_error(page_info, err)

    save_build_manifest(manifest)

    print(
        f"\n🚀 Build complete — {built} page(s) generated, "
        f"{skipped} skipped, {removed} removed → {BUILD_DIR}"
    )


if __name__ == "__main__":
    main()
