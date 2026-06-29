import argparse
import contextlib
import fnmatch
import gzip
import hashlib
import html
import http.server
import json
import mimetypes
import os
import posixpath
import re
import shutil
import socketserver
import subprocess
import sys
import threading
import time
import urllib.parse
from email.utils import formatdate
from dataclasses import dataclass
from typing import Dict, List, Optional, Tuple

from . import compiler


SCRIPT_DIR = os.path.abspath(os.path.dirname(__file__))
DEFAULT_PROJECT_ROOT = os.path.abspath(os.path.join(SCRIPT_DIR, compiler.PROJECT_ROOT))
DEFAULT_INTERNAL_OUTPUT = os.path.join(DEFAULT_PROJECT_ROOT, "dist")
DEFAULT_DEV_HOST = "127.0.0.1"
DEFAULT_DEV_PORT = 3000
DEFAULT_PREVIEW_PORT = 4173
HIDDEN_FRAMEWORK_DIR = ".tw"
WATCH_EXTENSIONS = {
    ".tw", ".tss", ".ts", ".json", ".md",
    ".png", ".jpg", ".jpeg", ".gif", ".webp", ".svg", ".ico",
    ".env", ".txt",
}


@dataclass
class BuildSummary:
    built: int
    skipped: int
    removed: int
    errors: int
    output_dir: str


@dataclass
class RouteMatch:
    page_info: dict
    params: Dict[str, str]
    item: Optional[dict]
    route_path: str


def configure_compiler_paths(project_root: str):
    project_root = os.path.abspath(project_root)

    compiler.PROJECT_ROOT = project_root
    compiler.HOME_DIR = os.path.join(project_root, "[home]")
    compiler.COMPONENTS_DIR = os.path.join(compiler.HOME_DIR, "components")
    compiler.PAGES_DIR = os.path.join(compiler.HOME_DIR, "pages")
    compiler.ASSETS_DIR = os.path.join(compiler.HOME_DIR, "assets")
    compiler.LAYOUTS_DIR = os.path.join(compiler.HOME_DIR, "layouts")
    compiler.API_DIR = os.path.join(compiler.HOME_DIR, "api")
    compiler.INDEX_FILE = os.path.join(compiler.HOME_DIR, "index.tw")
    compiler.STYLE_FILE = os.path.join(compiler.HOME_DIR, "style.tss")
    compiler.CONFIG_FILE = os.path.join(project_root, "tw.config")

    compiler.INTERNAL_DIR = os.path.join(project_root, HIDDEN_FRAMEWORK_DIR)
    compiler.CACHE_DIR = os.path.join(compiler.INTERNAL_DIR, "cache")
    compiler.MANIFEST_DIR = os.path.join(compiler.INTERNAL_DIR, "manifest")
    compiler.COMPILER_DIR = os.path.join(compiler.INTERNAL_DIR, "compiler")

    compiler.PUBLIC_DIR = os.path.join(project_root, "dist")
    compiler.BUILD_DIR = compiler.PUBLIC_DIR
    compiler.PUBLIC_ASSETS_DIR = os.path.join(compiler.PUBLIC_DIR, "assets")
    compiler.CHUNKS_DIR = os.path.join(compiler.COMPILER_DIR, "chunks")
    compiler.CHUNKS_PUBLIC_DIR = os.path.join(compiler.PUBLIC_DIR, "_tw", "static", "chunks")
    compiler.CHUNKS_URL_PREFIX = "/_tw/static/chunks/"
    compiler.BUILD_MANIFEST_FILE = os.path.join(compiler.MANIFEST_DIR, "build-manifest.json")
    compiler.HASH_DB_FILE = os.path.join(compiler.CACHE_DIR, "hash-db.json")
    compiler.DEPENDENCY_GRAPH_FILE = os.path.join(compiler.CACHE_DIR, "dependency-graph.json")


@contextlib.contextmanager
def compiler_output_context(output_root: str):
    old_values = {
        "INTERNAL_DIR": getattr(compiler, "INTERNAL_DIR", None),
        "CACHE_DIR": getattr(compiler, "CACHE_DIR", None),
        "MANIFEST_DIR": getattr(compiler, "MANIFEST_DIR", None),
        "COMPILER_DIR": getattr(compiler, "COMPILER_DIR", None),
        "PUBLIC_DIR": compiler.PUBLIC_DIR,
        "BUILD_DIR": compiler.BUILD_DIR,
        "PUBLIC_ASSETS_DIR": compiler.PUBLIC_ASSETS_DIR,
        "CHUNKS_DIR": compiler.CHUNKS_DIR,
        "CHUNKS_PUBLIC_DIR": getattr(compiler, "CHUNKS_PUBLIC_DIR", None),
        "CHUNKS_URL_PREFIX": compiler.CHUNKS_URL_PREFIX,
        "BUILD_MANIFEST_FILE": compiler.BUILD_MANIFEST_FILE,
        "HASH_DB_FILE": getattr(compiler, "HASH_DB_FILE", None),
        "DEPENDENCY_GRAPH_FILE": getattr(compiler, "DEPENDENCY_GRAPH_FILE", None),
        "MINIFY_OUTPUT": getattr(compiler, "MINIFY_OUTPUT", False),
    }

    output_root = os.path.abspath(output_root)
    compiler.PUBLIC_DIR = output_root
    compiler.BUILD_DIR = output_root
    compiler.PUBLIC_ASSETS_DIR = os.path.join(output_root, "assets")
    compiler.CHUNKS_PUBLIC_DIR = os.path.join(output_root, "_tw", "static", "chunks")
    compiler.CHUNKS_URL_PREFIX = "/_tw/static/chunks/"
    compiler._CHUNK_CACHE.clear()

    try:
        yield
    finally:
        compiler.INTERNAL_DIR = old_values["INTERNAL_DIR"]
        compiler.CACHE_DIR = old_values["CACHE_DIR"]
        compiler.MANIFEST_DIR = old_values["MANIFEST_DIR"]
        compiler.COMPILER_DIR = old_values["COMPILER_DIR"]
        compiler.PUBLIC_DIR = old_values["PUBLIC_DIR"]
        compiler.BUILD_DIR = old_values["BUILD_DIR"]
        compiler.PUBLIC_ASSETS_DIR = old_values["PUBLIC_ASSETS_DIR"]
        compiler.CHUNKS_DIR = old_values["CHUNKS_DIR"]
        compiler.CHUNKS_PUBLIC_DIR = old_values["CHUNKS_PUBLIC_DIR"]
        compiler.CHUNKS_URL_PREFIX = old_values["CHUNKS_URL_PREFIX"]
        compiler.BUILD_MANIFEST_FILE = old_values["BUILD_MANIFEST_FILE"]
        compiler.HASH_DB_FILE = old_values["HASH_DB_FILE"]
        compiler.DEPENDENCY_GRAPH_FILE = old_values["DEPENDENCY_GRAPH_FILE"]
        compiler.MINIFY_OUTPUT = old_values["MINIFY_OUTPUT"]
        compiler._CHUNK_CACHE.clear()


def invalidate_compiler_caches():
    compiler._CHUNK_CACHE.clear()
    compiler._COMPONENT_AST_CACHE.clear()
    compiler._COMPONENT_EXISTS_CACHE.clear()
    if hasattr(compiler, "_COMPONENT_PATH_CACHE"):
        compiler._COMPONENT_PATH_CACHE.clear()
    compiler._LAYOUT_CACHE.clear()
    compiler._COMPONENT_DEP_GRAPH_CACHE.clear()
    compiler.INLINE_SCRIPTS.clear()
    # Reset script placeholder growth (prevents long-lived dev sessions from leaking memory)
    if hasattr(compiler, "_SCRIPT_COUNTER"):
        compiler._SCRIPT_COUNTER = 0
    # Optional caches introduced by newer versions
    if hasattr(compiler, "_LAYOUT_META_CACHE"):
        compiler._LAYOUT_META_CACHE.clear()


def normalize_url_path(path: str) -> str:
    clean = urllib.parse.urlparse(path).path
    clean = posixpath.normpath(clean)
    if clean == ".":
        clean = "/"
    if not clean.startswith("/"):
        clean = "/" + clean
    return clean


def strip_trailing_slash(path: str) -> str:
    if path != "/" and path.endswith("/"):
        return path[:-1]
    return path


def route_from_static_page(page_info: dict) -> str:
    segments = []
    if page_info["rel_dir"]:
        segments.extend(page_info["rel_dir"].split(os.sep))
    if page_info["name"] != "index":
        segments.append(page_info["name"])
    route = "/" + "/".join(filter(None, segments))
    return route if route != "" else "/"


def route_from_dynamic_page(page_info: dict, item: dict) -> str:
    segments = []
    if page_info["rel_dir"]:
        segments.extend(page_info["rel_dir"].split(os.sep))
    segments.extend(compiler.resolve_dynamic_segments(page_info, item))
    return "/" + "/".join(filter(None, segments))


def special_page_name_for_status(status_code: int) -> str:
    if status_code == 404:
        return "404"
    if status_code == 500:
        return "500"
    return str(status_code)


def inject_dev_client(html_text: str) -> str:
    # Robust live reload:
    # - Auto-reconnect on background tab / network hiccups
    # - Backoff retry to avoid CPU spikes
    client = """
<script>
(() => {
  let source = null;
  let retry = 500;
  const maxRetry = 5000;

  function connect() {
    try { if (source) source.close(); } catch (e) {}
    source = new EventSource('/__tw/events');
    source.onopen = () => { retry = 500; };
    source.onmessage = (event) => {
      if (event.data === 'reload') window.location.reload();
    };
    source.onerror = () => {
      try { if (source) source.close(); } catch (e) {}
      setTimeout(connect, retry);
      retry = Math.min(maxRetry, retry * 2);
    };
  }

  connect();
})();
</script>
"""
    if "</body>" in html_text:
        return html_text.replace("</body>", client + "\n</body>", 1)
    return html_text + client


def render_error_html(title: str, message: str, status_code: int = 500) -> bytes:
    doc = f"""<!DOCTYPE html>
<html>
<head>
  <meta charset="UTF-8">
  <title>{html.escape(title)}</title>
  <style>
    body {{ margin: 0; font-family: Inter, system-ui, sans-serif; background: #0b1020; color: #f9fafb; }}
    .overlay {{ min-height: 100vh; padding: 32px; background:
      radial-gradient(circle at top left, rgba(220, 38, 38, 0.25), transparent 35%),
      linear-gradient(180deg, #130d14 0%, #0b1020 100%);
    }}
    .card {{ max-width: 1100px; margin: 0 auto; border: 1px solid rgba(248,113,113,0.35); background: rgba(17,24,39,0.88); border-radius: 18px; box-shadow: 0 30px 80px rgba(0,0,0,0.45); overflow: hidden; }}
    .header {{ padding: 18px 22px; border-bottom: 1px solid rgba(248,113,113,0.18); background: rgba(127,29,29,0.22); }}
    .status {{ color: #fca5a5; font-size: 13px; letter-spacing: 0.08em; text-transform: uppercase; margin-bottom: 8px; }}
    h1 {{ margin: 0; font-size: 28px; }}
    pre {{ margin: 0; white-space: pre-wrap; background: #020617; padding: 22px; overflow: auto; line-height: 1.55; }}
  </style>
</head>
<body>
  <div class="overlay">
    <div class="card">
      <div class="header">
        <div class="status">TW Compile Error · HTTP {status_code}</div>
        <h1>{html.escape(title)}</h1>
      </div>
      <pre>{html.escape(message)}</pre>
    </div>
  </div>
</body>
</html>"""
    return doc.encode("utf-8")


def format_compiler_error(page_path: str, err: Exception) -> str:
    if isinstance(err, compiler.CompilerError) and os.path.exists(page_path):
        raw = compiler.read_text_file(page_path)
        emitter = compiler.DiagnosticEmitter(page_path, raw)
        return emitter.format(err)
    return str(err)


def safe_read_binary(path: str) -> Optional[bytes]:
    if not os.path.exists(path) or not os.path.isfile(path):
        return None
    with open(path, "rb") as f:
        return f.read()


def parse_env_file(path: str) -> Dict[str, str]:
    values = {}
    if not os.path.exists(path):
        return values
    with open(path, "r", encoding="utf-8") as f:
        for raw_line in f:
            line = raw_line.strip()
            if not line or line.startswith("#") or "=" not in line:
                continue
            key, value = line.split("=", 1)
            key = key.strip()
            value = value.strip().strip('"').strip("'")
            values[key] = value
    return values


def load_project_env(project_root: str, mode: str) -> Dict[str, str]:
    env = {}
    for name in [".env", f".env.{mode}", ".env.local"]:
        env.update(parse_env_file(os.path.join(project_root, name)))
    for key, value in env.items():
        os.environ[key] = value
    return env


def parse_cookie_header(raw_value: str) -> Dict[str, str]:
    cookies = {}
    if not raw_value:
        return cookies
    for part in raw_value.split(";"):
        if "=" not in part:
            continue
        key, value = part.split("=", 1)
        cookies[key.strip()] = urllib.parse.unquote(value.strip())
    return cookies


def match_path_pattern(path: str, pattern: str) -> bool:
    if not pattern or pattern in {"*", "/**"}:
        return True
    if pattern.endswith("/**"):
        return path.startswith(pattern[:-3] or "/")
    return fnmatch.fnmatch(path, pattern)


def middleware_file_candidates(project_root: str) -> List[str]:
    return [
        os.path.join(project_root, "middleware.tw"),
        os.path.join(compiler.HOME_DIR, "middleware.tw"),
        os.path.join(compiler.HOME_DIR, "middleware", "index.tw"),
    ]


def parse_value_token(tokens, i):
    token = tokens[i] if i < len(tokens) else None
    if not token or token.type not in {"STRING", "WORD"}:
        raise RuntimeError("Expected value token")
    return token.value, i + 1


def parse_middleware_rules(project_root: str) -> List[dict]:
    source_path = next((path for path in middleware_file_candidates(project_root) if os.path.exists(path)), None)
    if not source_path:
        return []

    tokens = compiler.tokenize_tw(compiler.read_text_file(source_path))
    rules = []
    i = 0
    while i < len(tokens):
        token = tokens[i]
        if token.type == "WORD" and token.value == "use":
            i += 1
            if i >= len(tokens) or tokens[i].type != "BRACE" or tokens[i].value != "{":
                raise RuntimeError("Expected `{` after `use` in middleware.tw")
            i += 1
            rule = {"match": "/**", "headers": [], "cookies": []}
            while i < len(tokens):
                tok = tokens[i]
                if tok.type == "BRACE" and tok.value == "}":
                    i += 1
                    break
                if tok.type != "WORD":
                    raise RuntimeError("Invalid middleware directive")
                key = tok.value
                i += 1
                if key == "match":
                    rule["match"], i = parse_value_token(tokens, i)
                elif key == "redirect":
                    rule["redirect"], i = parse_value_token(tokens, i)
                elif key == "rewrite":
                    rule["rewrite"], i = parse_value_token(tokens, i)
                elif key == "auth":
                    cookie_name, i = parse_value_token(tokens, i)
                    redirect_to, i = parse_value_token(tokens, i)
                    rule["auth"] = {"cookie": cookie_name, "redirect": redirect_to}
                elif key == "header":
                    header_name, i = parse_value_token(tokens, i)
                    header_value, i = parse_value_token(tokens, i)
                    rule["headers"].append((header_name, header_value))
                elif key == "cookie":
                    cookie_name, i = parse_value_token(tokens, i)
                    cookie_value, i = parse_value_token(tokens, i)
                    rule["cookies"].append((cookie_name, cookie_value))
                else:
                    raise RuntimeError(f"Unsupported middleware key: {key}")
            rules.append(rule)
            continue
        i += 1
    return rules


def discover_api_routes() -> List[dict]:
    routes = []
    if not os.path.isdir(compiler.API_DIR):
        return routes
    for root, _, files in os.walk(compiler.API_DIR):
        rel_dir = os.path.relpath(root, compiler.API_DIR)
        rel_dir = compiler.normalize_route_directory(rel_dir)
        for filename in sorted(files):
            if not filename.endswith(".tw"):
                continue
            name = filename[:-3]
            segments = ["api"]
            if rel_dir:
                segments.extend(rel_dir.split(os.sep))
            if name != "index":
                segments.append(name)
            route_path = "/" + "/".join(filter(None, segments))
            routes.append({"path": os.path.join(root, filename), "route": route_path})
    return routes


def parse_api_route_file(tw_path: str) -> Dict[str, dict]:
    tokens = compiler.tokenize_tw(compiler.read_text_file(tw_path))
    methods = {}
    i = 0
    while i < len(tokens):
        token = tokens[i]
        if token.type != "WORD":
            i += 1
            continue
        method = token.value.upper()
        if method not in {"GET", "POST", "PUT", "PATCH", "DELETE", "OPTIONS"}:
            i += 1
            continue
        i += 1
        if i >= len(tokens) or tokens[i].type != "BRACE" or tokens[i].value != "{":
            raise RuntimeError(f"Expected `{{` after `{method}` in {tw_path}")
        i += 1
        spec = {"status": 200, "headers": [], "cookies": []}
        while i < len(tokens):
            tok = tokens[i]
            if tok.type == "BRACE" and tok.value == "}":
                i += 1
                break
            if tok.type != "WORD":
                raise RuntimeError(f"Invalid API directive in {tw_path}")
            key = tok.value
            i += 1
            if key == "status":
                raw_status, i = parse_value_token(tokens, i)
                spec["status"] = int(raw_status)
            elif key in {"json", "text", "html", "redirect"}:
                spec[key], i = parse_value_token(tokens, i)
            elif key == "header":
                header_name, i = parse_value_token(tokens, i)
                header_value, i = parse_value_token(tokens, i)
                spec["headers"].append((header_name, header_value))
            elif key == "cookie":
                cookie_name, i = parse_value_token(tokens, i)
                cookie_value, i = parse_value_token(tokens, i)
                spec["cookies"].append((cookie_name, cookie_value))
            else:
                raise RuntimeError(f"Unsupported API key `{key}` in {tw_path}")
        methods[method] = spec
    return methods


def render_api_value(value, context):
    def render_nested(item):
        if isinstance(item, dict):
            return {key: render_nested(val) for key, val in item.items()}
        if isinstance(item, list):
            return [render_nested(val) for val in item]
        if isinstance(item, str):
            return compiler.parse_literal_value(compiler.interpolate(item, context))
        return item

    if isinstance(value, str):
        stripped = value.strip()
        if (stripped.startswith("{") and stripped.endswith("}")) or (stripped.startswith("[") and stripped.endswith("]")):
            try:
                return render_nested(json.loads(stripped))
            except Exception:
                pass
    rendered = compiler.interpolate(str(value), context)
    return compiler.parse_literal_value(rendered)


def decode_request_body(handler) -> object:
    length = int(handler.headers.get("Content-Length", "0") or "0")
    if length <= 0:
        return {}
    raw = handler.rfile.read(length)
    content_type = handler.headers.get("Content-Type", "")
    if "application/json" in content_type:
        try:
            return json.loads(raw.decode("utf-8"))
        except Exception:
            return {"raw": raw.decode("utf-8", errors="replace")}
    if "application/x-www-form-urlencoded" in content_type:
        parsed = urllib.parse.parse_qs(raw.decode("utf-8"), keep_blank_values=True)
        return {key: value[0] if len(value) == 1 else value for key, value in parsed.items()}
    return {"raw": raw.decode("utf-8", errors="replace"), "bytes": len(raw)}


class TWProject:
    def __init__(self, project_root: str):
        self.project_root = os.path.abspath(project_root)
        configure_compiler_paths(self.project_root)
        self.env = load_project_env(self.project_root, "development")
        self.config = compiler.load_config()

    @property
    def source_root(self) -> str:
        return compiler.HOME_DIR

    def list_source_files(self) -> List[str]:
        files = []
        if os.path.exists(self.project_root):
            config_path = compiler.CONFIG_FILE
            if os.path.exists(config_path):
                files.append(config_path)

        for root in [compiler.HOME_DIR]:
            if not os.path.exists(root):
                continue
            for dirpath, _, filenames in os.walk(root):
                for filename in filenames:
                    ext = os.path.splitext(filename)[1].lower()
                    if ext in WATCH_EXTENSIONS:
                        files.append(os.path.join(dirpath, filename))
        return sorted(set(os.path.abspath(p) for p in files))

    def source_signature(self) -> str:
        digest = hashlib.sha1()
        for path in self.list_source_files():
            stat = os.stat(path)
            digest.update(path.encode("utf-8"))
            digest.update(str(stat.st_mtime_ns).encode("utf-8"))
            digest.update(str(stat.st_size).encode("utf-8"))
        return digest.hexdigest()

    def invalidate(self):
        invalidate_compiler_caches()
        self.env = load_project_env(self.project_root, "development")
        self.config = compiler.load_config()

    def discover_pages(self) -> List[dict]:
        self.invalidate()
        return compiler.discover_pages()

    def find_special_page(self, status_code: int) -> Optional[dict]:
        expected_name = special_page_name_for_status(status_code)
        for page in self.discover_pages():
            if page["type"] == "static" and page.get("name") == expected_name:
                return page
        return None

    def resolve_asset(self, url_path: str) -> Optional[Tuple[bytes, str]]:
        path = normalize_url_path(url_path)

        if path == "/_tw/search-index.json":
            payload = json.dumps(self.build_dev_search_index(), ensure_ascii=False, indent=2).encode("utf-8")
            return payload, "application/json; charset=utf-8"

        if path.startswith("/assets/"):
            candidate = os.path.abspath(os.path.join(compiler.ASSETS_DIR, path[len("/assets/"):]))
            if candidate.startswith(os.path.abspath(compiler.ASSETS_DIR)):
                payload = safe_read_binary(candidate)
                if payload is not None:
                    content_type = mimetypes.guess_type(candidate)[0] or "application/octet-stream"
                    return payload, content_type

        if path.startswith("/_tw/static/chunks/"):
            candidate = os.path.abspath(os.path.join(compiler.CHUNKS_DIR, path.split("/_tw/static/chunks/", 1)[1]))
            if candidate.startswith(os.path.abspath(compiler.CHUNKS_DIR)):
                payload = safe_read_binary(candidate)
                if payload is not None:
                    content_type = mimetypes.guess_type(candidate)[0] or "application/javascript"
                    return payload, content_type

        return None

    def build_dev_search_index(self) -> List[dict]:
        # Dev-only: compile current static pages and extract searchable text.
        items = []
        for page in self.discover_pages():
            if page["type"] != "static":
                continue
            route = route_from_static_page(page)
            match = RouteMatch(page_info=page, params={}, item=None, route_path=route or "/")
            html_text = self.compile_match_to_html(match, dev_mode=False)
            text = strip_html_to_text(html_text)
            if not text:
                continue
            page_ast = compiler.load_page_ast_from_file(page["path"])
            title = page_ast.title or route
            items.append({
                "route": route,
                "title": title,
                "excerpt": text[:240],
                "content": text[:4000],
            })
        return items

    def resolve_route(self, raw_path: str) -> Optional[RouteMatch]:
        path = strip_trailing_slash(normalize_url_path(raw_path))
        pages = self.discover_pages()

        for page in pages:
            if page["type"] == "static":
                route = strip_trailing_slash(route_from_static_page(page))
                html_route = route + ".html" if route != "/" else "/index.html"
                pretty_html_route = (route + "/index.html") if route != "/" else "/index.html"
                if path in {route, html_route, strip_trailing_slash(pretty_html_route)}:
                    return RouteMatch(page_info=page, params={}, item=None, route_path=route or "/")
                continue

            items = compiler.load_dynamic_items(page["path"])
            for item in items:
                if not isinstance(item, dict):
                    continue
                route = strip_trailing_slash(route_from_dynamic_page(page, item))
                html_route = route + "/index.html" if route != "/" else "/index.html"
                if path in {route, strip_trailing_slash(html_route)}:
                    param = page["param"]
                    segments = compiler.resolve_dynamic_segments(page, item)
                    params = {param: "/".join(segments)}
                    if page.get("route_kind") != "single":
                        params[param + "Segments"] = segments
                    return RouteMatch(page_info=page, params=params, item=item, route_path=route or "/")

        return None

    def apply_middleware(self, raw_path: str, request_headers: Optional[Dict[str, str]] = None) -> dict:
        path = normalize_url_path(raw_path)
        request_headers = request_headers or {}
        cookies = parse_cookie_header(request_headers.get("Cookie", ""))
        result = {"path": path, "headers": [], "cookies": [], "redirect": None}

        for rule in parse_middleware_rules(self.project_root):
            if not match_path_pattern(path, str(rule.get("match", "/**"))):
                continue
            auth = rule.get("auth")
            if auth and not cookies.get(auth["cookie"]):
                result["redirect"] = auth["redirect"]
                return result
            if rule.get("rewrite"):
                result["path"] = normalize_url_path(rule["rewrite"])
            if rule.get("redirect"):
                result["redirect"] = rule["redirect"]
                return result
            result["headers"].extend(rule.get("headers", []))
            result["cookies"].extend(rule.get("cookies", []))

        return result

    def resolve_api_route(self, raw_path: str) -> Optional[dict]:
        path = strip_trailing_slash(normalize_url_path(raw_path))
        for route in discover_api_routes():
            if strip_trailing_slash(route["route"]) == path:
                return route
        return None

    def execute_api_route(self, api_route: dict, method: str, url_path: str, headers: Dict[str, str], body: object) -> dict:
        methods = parse_api_route_file(api_route["path"])
        spec = methods.get(method.upper())
        if not spec:
            allowed = ", ".join(sorted(methods))
            payload = json.dumps({"error": "Method not allowed", "allowed": sorted(methods)})
            return {
                "status": 405,
                "content_type": "application/json; charset=utf-8",
                "body": payload.encode("utf-8"),
                "headers": [("Allow", allowed)],
                "cookies": [],
            }

        query = urllib.parse.parse_qs(urllib.parse.urlparse(url_path).query, keep_blank_values=True)
        query = {key: value[0] if len(value) == 1 else value for key, value in query.items()}
        cookies = parse_cookie_header(headers.get("Cookie", ""))
        context = {
            "env": dict(os.environ),
            "query": query,
            "body": body,
            "headers": headers,
            "cookies": cookies,
            "request": {
                "method": method.upper(),
                "path": normalize_url_path(url_path),
                "query": query,
                "body": body,
                "headers": headers,
                "cookies": cookies,
            },
        }

        response_headers = list(spec.get("headers", []))
        response_cookies = list(spec.get("cookies", []))
        if "redirect" in spec:
            location = str(render_api_value(spec["redirect"], context))
            return {
                "status": int(spec.get("status", 302) or 302),
                "content_type": "text/plain; charset=utf-8",
                "body": f"Redirecting to {location}".encode("utf-8"),
                "headers": response_headers + [("Location", location)],
                "cookies": response_cookies,
            }
        if "json" in spec:
            payload = render_api_value(spec["json"], context)
            body_bytes = json.dumps(payload, ensure_ascii=False).encode("utf-8")
            return {
                "status": int(spec.get("status", 200)),
                "content_type": "application/json; charset=utf-8",
                "body": body_bytes,
                "headers": response_headers,
                "cookies": response_cookies,
            }
        if "html" in spec:
            payload = str(render_api_value(spec["html"], context))
            return {
                "status": int(spec.get("status", 200)),
                "content_type": "text/html; charset=utf-8",
                "body": payload.encode("utf-8"),
                "headers": response_headers,
                "cookies": response_cookies,
            }

        payload = str(render_api_value(spec.get("text", ""), context))
        return {
            "status": int(spec.get("status", 200)),
            "content_type": "text/plain; charset=utf-8",
            "body": payload.encode("utf-8"),
            "headers": response_headers,
            "cookies": response_cookies,
        }

    def compile_match_response(self, match: RouteMatch, dev_mode: bool = False, depth: int = 0) -> dict:
        if depth > 5:
            raise RuntimeError("Rewrite loop detected")

        page_info = match.page_info
        tw_path = page_info["path"]
        page_ast = compiler.load_page_ast_from_file(tw_path)
        css_url, _ = compiler.read_global_stylesheet()

        context = compiler.create_base_context(page_ast, tw_path)
        if match.item:
            context.update(match.item)
        context.update(match.params)
        context["_tw_route"] = match.route_path
        context["request"] = {"path": match.route_path, "params": match.params, "env": dict(os.environ)}

        if page_ast.rewrite_to:
            rewritten_path = compiler.interpolate(page_ast.rewrite_to, context)
            rewritten_match = self.resolve_route(rewritten_path)
            if rewritten_match:
                rewritten_match = RouteMatch(
                    page_info=rewritten_match.page_info,
                    params=rewritten_match.params,
                    item=rewritten_match.item,
                    route_path=match.route_path,
                )
                return self.compile_match_response(rewritten_match, dev_mode=dev_mode, depth=depth + 1)

        rendered = compiler.render_html(page_ast, context, css_url)
        status = 302 if page_ast.redirect_to else 200
        headers = []
        if page_ast.redirect_to:
            headers.append(("Location", compiler.interpolate(page_ast.redirect_to, context)))

        if dev_mode:
            rendered = inject_dev_client(rendered)
        return {"html": rendered, "status": status, "headers": headers}

    def compile_match_to_html(self, match: RouteMatch, dev_mode: bool = False) -> str:
        return self.compile_match_response(match, dev_mode=dev_mode)["html"]

    def compile_special_page(self, status_code: int, dev_mode: bool = False) -> Optional[str]:
        page_info = self.find_special_page(status_code)
        if not page_info:
            return None
        return self.compile_match_to_html(RouteMatch(page_info=page_info, params={}, item=None, route_path=f"/{status_code}"), dev_mode=dev_mode)


class TWDevState:
    def __init__(self, project: TWProject):
        self.project = project
        self.version = 0
        self.stop_event = threading.Event()
        self.lock = threading.Lock()

    def bump(self):
        with self.lock:
            self.version += 1

    def current_version(self) -> int:
        with self.lock:
            return self.version


class TWFileWatcher(threading.Thread):
    def __init__(self, state: TWDevState, interval: float = 1.0):
        super().__init__(daemon=True)
        self.state = state
        # Allow tuning:
        # - env: TW_WATCH_INTERVAL
        # - config: watch_interval
        configured = None
        try:
            configured = float(os.environ.get("TW_WATCH_INTERVAL", "") or "")
        except Exception:
            configured = None
        if configured is None:
            try:
                configured = float(state.project.config.get("watch_interval", state.project.config.get("watchInterval", interval)))
            except Exception:
                configured = None
        self.interval = max(0.2, min(2.0, configured if configured is not None else interval))

        self._tick = 0
        self._files = []
        self._stats = {}
        self._refresh_file_list()

    def _refresh_file_list(self):
        self._files = self.state.project.list_source_files()
        self._stats = {}
        for path in self._files:
            try:
                st = os.stat(path)
                self._stats[path] = (st.st_mtime_ns, st.st_size)
            except Exception:
                self._stats[path] = None

    def run(self):
        while not self.state.stop_event.is_set():
            time.sleep(self.interval)
            self._tick += 1

            changed = False
            for path in list(self._files):
                try:
                    st = os.stat(path)
                    sig = (st.st_mtime_ns, st.st_size)
                except Exception:
                    sig = None
                if self._stats.get(path) != sig:
                    changed = True
                    break

            # Periodically rescan to detect new files / deletions (low overhead)
            if not changed and (self._tick % 8 == 0):
                new_files = self.state.project.list_source_files()
                if set(new_files) != set(self._files):
                    changed = True

            if changed:
                self._refresh_file_list()
                self.state.project.invalidate()
                self.state.bump()


def make_dev_handler(state: TWDevState):
    class TWDevHandler(http.server.BaseHTTPRequestHandler):
        server_version = "TWDevServer/1.0"

        def log_message(self, fmt, *args):
            print(f"[dev] {self.address_string()} - {fmt % args}")

        def do_GET(self):
            self.handle_request("GET")

        def do_POST(self):
            self.handle_request("POST")

        def do_PUT(self):
            self.handle_request("PUT")

        def do_PATCH(self):
            self.handle_request("PATCH")

        def do_DELETE(self):
            self.handle_request("DELETE")

        def do_OPTIONS(self):
            self.handle_request("OPTIONS")

        def handle_request(self, method: str):
            path = normalize_url_path(self.path)
            if path == "/__tw/events":
                self.handle_events()
                return

            if path == "/__tw/health":
                self.respond_bytes(200, b"ok", "text/plain; charset=utf-8")
                return

            request_headers = {key: value for key, value in self.headers.items()}
            middleware = state.project.apply_middleware(self.path, request_headers)
            if middleware.get("redirect"):
                payload = f"Redirecting to {middleware['redirect']}".encode("utf-8")
                self.respond_bytes(
                    302,
                    payload,
                    "text/plain; charset=utf-8",
                    headers=[("Location", middleware["redirect"])] + middleware.get("headers", []),
                    cookies=middleware.get("cookies", []),
                )
                return
            path = normalize_url_path(middleware.get("path", path))

            api_route = state.project.resolve_api_route(path)
            if api_route is not None:
                body = decode_request_body(self) if method in {"POST", "PUT", "PATCH"} else {}
                try:
                    api_response = state.project.execute_api_route(api_route, method, self.path, request_headers, body)
                    self.respond_bytes(
                        api_response["status"],
                        api_response["body"],
                        api_response["content_type"],
                        headers=middleware.get("headers", []) + api_response.get("headers", []),
                        cookies=middleware.get("cookies", []) + api_response.get("cookies", []),
                    )
                except Exception as err:
                    body = render_error_html("API route error", str(err), 500)
                    self.respond_bytes(500, body, "text/html; charset=utf-8")
                return

            asset = state.project.resolve_asset(path)
            if asset is not None:
                payload, content_type = asset
                self.respond_bytes(200, payload, content_type, headers=middleware.get("headers", []), cookies=middleware.get("cookies", []))
                return

            match = state.project.resolve_route(path)
            if not match:
                custom_404 = state.project.compile_special_page(404, dev_mode=True)
                if custom_404 is not None:
                    self.respond_bytes(404, custom_404.encode("utf-8"), "text/html; charset=utf-8", headers=middleware.get("headers", []), cookies=middleware.get("cookies", []))
                    return
                body = render_error_html("Page not found", f"Route not found: {path}", 404)
                self.respond_bytes(404, body, "text/html; charset=utf-8", headers=middleware.get("headers", []), cookies=middleware.get("cookies", []))
                return

            try:
                response = state.project.compile_match_response(match, dev_mode=True)
                self.respond_bytes(
                    response["status"],
                    response["html"].encode("utf-8"),
                    "text/html; charset=utf-8",
                    headers=middleware.get("headers", []) + response.get("headers", []),
                    cookies=middleware.get("cookies", []),
                )
            except Exception as err:
                try:
                    custom_500 = state.project.compile_special_page(500, dev_mode=True)
                    if custom_500 is not None:
                        self.respond_bytes(500, custom_500.encode("utf-8"), "text/html; charset=utf-8", headers=middleware.get("headers", []), cookies=middleware.get("cookies", []))
                        return
                except Exception:
                    pass
                message = format_compiler_error(match.page_info["path"], err)
                body = render_error_html("Compile error", message, 500)
                self.respond_bytes(500, body, "text/html; charset=utf-8", headers=middleware.get("headers", []), cookies=middleware.get("cookies", []))

        def handle_events(self):
            self.send_response(200)
            self.send_header("Content-Type", "text/event-stream")
            self.send_header("Cache-Control", "no-cache")
            self.send_header("Connection", "keep-alive")
            self.end_headers()

            last_seen = state.current_version()
            try:
                # EventSource reconnection hint (ms)
                self.wfile.write(b"retry: 500\n\n")
                self.wfile.flush()
                while not state.stop_event.is_set():
                    current = state.current_version()
                    if current != last_seen:
                        self.wfile.write(b"data: reload\n\n")
                        self.wfile.flush()
                        last_seen = current
                    else:
                        self.wfile.write(b": ping\n\n")
                        self.wfile.flush()
                    time.sleep(1)
            except (BrokenPipeError, ConnectionResetError):
                return

        def respond_bytes(self, status: int, payload: bytes, content_type: str, headers: Optional[List[Tuple[str, str]]] = None, cookies: Optional[List[Tuple[str, str]]] = None):
            self.send_response(status)
            self.send_header("Content-Type", content_type)
            self.send_header("Content-Length", str(len(payload)))
            # Dev cache hardening: avoid stale HTML/CSS/JS when browser caches aggressively
            if content_type.startswith("text/html") or content_type.startswith("text/css") or "javascript" in content_type:
                self.send_header("Cache-Control", "no-store")
            else:
                self.send_header("Cache-Control", "no-cache")
            for header_name, header_value in headers or []:
                self.send_header(header_name, header_value)
            for cookie_name, cookie_value in cookies or []:
                rendered_value = urllib.parse.quote(str(cookie_value))
                self.send_header("Set-Cookie", f"{cookie_name}={rendered_value}; Path=/; HttpOnly; SameSite=Lax")
            self.end_headers()
            try:
                self.wfile.write(payload)
            except (BrokenPipeError, ConnectionResetError):
                return

    return TWDevHandler


class ThreadedTCPServer(socketserver.ThreadingMixIn, socketserver.TCPServer):
    allow_reuse_address = True
    daemon_threads = True


def run_dev_server(project_root: str, host: str, port: int):
    project = TWProject(project_root)
    state = TWDevState(project)
    watcher = TWFileWatcher(state)
    watcher.start()

    handler = make_dev_handler(state)
    try:
        server = ThreadedTCPServer((host, port), handler)
    except OSError as err:
        state.stop_event.set()
        raise RuntimeError(
            f"Port {port} bind nahi ho saka ({err}). Kya ye port already busy hai? "
            f"Try: `tw dev --port {port + 1}` ya koi free port use karo."
        ) from err

    print(f"TW dev server running at http://{host}:{port}")
    print("Source workflow active: edit `.tw`, `.tss`, `.ts`; browser auto-reload karega.")

    try:
        server.serve_forever()
    except KeyboardInterrupt:
        print("\nStopping dev server...")
    finally:
        state.stop_event.set()
        server.shutdown()
        server.server_close()


def build_preview_candidates(output_dir: str, path: str) -> List[str]:
    if path == "/":
        return [os.path.join(output_dir, "index.html")]

    trimmed = path.lstrip("/")
    candidates = [os.path.join(output_dir, trimmed)]
    if not os.path.splitext(trimmed)[1]:
        candidates.append(os.path.join(output_dir, trimmed + ".html"))
        candidates.append(os.path.join(output_dir, trimmed, "index.html"))
    return candidates


def make_preview_handler(output_dir: str):
    output_dir = os.path.abspath(output_dir)

    class TWPreviewHandler(http.server.BaseHTTPRequestHandler):
        server_version = "TWPreviewServer/1.0"

        def log_message(self, fmt, *args):
            print(f"[preview] {self.address_string()} - {fmt % args}")

        def do_GET(self):
            path = normalize_url_path(self.path)
            for candidate in build_preview_candidates(output_dir, path):
                candidate = os.path.abspath(candidate)
                if not candidate.startswith(output_dir):
                    continue
                payload = safe_read_binary(candidate)
                if payload is not None:
                    content_type = mimetypes.guess_type(candidate)[0] or "application/octet-stream"
                    self.respond_bytes(200, payload, content_type)
                    return

            custom_404 = safe_read_binary(os.path.join(output_dir, "404.html"))
            if custom_404 is not None:
                self.respond_bytes(404, custom_404, "text/html; charset=utf-8")
                return

            body = render_error_html("Page not found", f"Route not found: {path}", 404)
            self.respond_bytes(404, body, "text/html; charset=utf-8")

        def respond_bytes(self, status: int, payload: bytes, content_type: str):
            self.send_response(status)
            self.send_header("Content-Type", content_type)
            self.send_header("Content-Length", str(len(payload)))
            # Preview: prefer fresh content during local testing
            self.send_header("Cache-Control", "no-cache")
            self.end_headers()
            try:
                self.wfile.write(payload)
            except (BrokenPipeError, ConnectionResetError):
                return

    return TWPreviewHandler


def run_preview_server(output_dir: str, host: str, port: int):
    output_dir = os.path.abspath(output_dir)
    if not os.path.isdir(output_dir):
        raise RuntimeError(f"Preview output missing: {output_dir}. Pehle `tw build` ya `tw export` chalao.")

    handler = make_preview_handler(output_dir)
    server = ThreadedTCPServer((host, port), handler)
    print(f"TW preview server running at http://{host}:{port}")
    print(f"Serving static output from: {output_dir}")
    try:
        server.serve_forever()
    except KeyboardInterrupt:
        print("\nStopping preview server...")
    finally:
        server.shutdown()
        server.server_close()


def compile_typescript_sources(project_root: str, output_dir: str) -> List[str]:
    ts_files = []
    for dirpath, _, filenames in os.walk(os.path.join(project_root, "[home]")):
        for filename in filenames:
            if filename.endswith(".ts"):
                ts_files.append(os.path.join(dirpath, filename))

    if not ts_files:
        return []

    tsc_bin = shutil.which("tsc")
    if not tsc_bin:
        print("  ⚠️  TypeScript files found, but `tsc` nahi mila. TS compilation skip ki gayi.")
        return []

    out_dir = os.path.join(output_dir, "_tw", "ts")
    os.makedirs(out_dir, exist_ok=True)

    command = [
        tsc_bin,
        "--module", "esnext",
        "--target", "es2020",
        "--sourceMap",
        "--outDir", out_dir,
        "--rootDir", os.path.join(project_root, "[home]"),
        "--pretty", "false",
        "--skipLibCheck",
    ] + ts_files

    result = subprocess.run(command, capture_output=True, text=True)
    if result.returncode != 0:
        raise RuntimeError(f"TypeScript compile failed:\n{result.stdout}\n{result.stderr}".strip())

    emitted = []
    for root, _, files in os.walk(out_dir):
        for filename in files:
            emitted.append(os.path.join(root, filename))
    return emitted


def ensure_project_metadata(project_root: str):
    package_json_path = os.path.join(project_root, "package.json")
    if not os.path.exists(package_json_path):
        package_name = os.path.basename(os.path.abspath(project_root)).lower().replace(" ", "-")
        with open(package_json_path, "w", encoding="utf-8") as f:
            json.dump(
                {
                    "name": package_name or "tw-site",
                    "private": True,
                    "version": "0.1.0",
                    "scripts": {
                        "dev": "tw dev",
                        "build": "tw build",
                        "export": "tw export",
                        "preview": "tw preview",
                        "clean": "tw clean",
                        "doctor": "tw doctor",
                        "info": "tw info",
                        "deploy": "tw deploy",
                    },
                },
                f,
                indent=2,
            )
            f.write("\n")

    vercel_json_path = os.path.join(project_root, "vercel.json")
    if not os.path.exists(vercel_json_path):
        with open(vercel_json_path, "w", encoding="utf-8") as f:
            json.dump(
                {
                    "buildCommand": "tw build",
                    "outputDirectory": "dist",
                },
                f,
                indent=2,
            )
            f.write("\n")


def sync_runtime_chunks_to_output():
    os.makedirs(compiler.CHUNKS_DIR, exist_ok=True)
    os.makedirs(compiler.CHUNKS_PUBLIC_DIR, exist_ok=True)

    for filename in os.listdir(compiler.CHUNKS_DIR):
        src = os.path.join(compiler.CHUNKS_DIR, filename)
        dst = os.path.join(compiler.CHUNKS_PUBLIC_DIR, filename)
        if os.path.isfile(src):
            shutil.copy2(src, dst)


def write_hidden_cache_files(dependency_map: Dict[str, List[str]]):
    os.makedirs(compiler.CACHE_DIR, exist_ok=True)
    os.makedirs(compiler.MANIFEST_DIR, exist_ok=True)
    os.makedirs(compiler.COMPILER_DIR, exist_ok=True)

    hash_db = {}
    for page_key, dependencies in dependency_map.items():
        hash_db[page_key] = {
            "signature": compiler.compute_dependency_signature(dependencies),
            "dependencies": dependencies,
        }

    with open(compiler.HASH_DB_FILE, "w", encoding="utf-8") as f:
        json.dump(hash_db, f, indent=2, sort_keys=True)

    with open(compiler.DEPENDENCY_GRAPH_FILE, "w", encoding="utf-8") as f:
        json.dump(dependency_map, f, indent=2, sort_keys=True)


def write_text_file(path: str, content: str):
    os.makedirs(os.path.dirname(path), exist_ok=True)
    with open(path, "w", encoding="utf-8") as f:
        f.write(content)


def route_records_for_build() -> List[dict]:
    records = []
    for page in compiler.discover_pages():
        page_ast = compiler.load_page_ast_from_file(page["path"])
        if page["type"] == "static":
            route = route_from_static_page(page)
            records.append({
                "route": route,
                "type": "page",
                "render": page_ast.render_mode,
                "revalidate": page_ast.revalidate,
                "source": compiler.safe_relpath(page["path"], compiler.PROJECT_ROOT),
                "title": page_ast.title,
            })
            continue
        for item in compiler.load_dynamic_items(page["path"]):
            if not isinstance(item, dict):
                continue
            route = route_from_dynamic_page(page, item)
            records.append({
                "route": route,
                "type": "page",
                "render": page_ast.render_mode,
                "revalidate": page_ast.revalidate,
                "source": compiler.safe_relpath(page["path"], compiler.PROJECT_ROOT),
                "title": page_ast.title,
            })
    return sorted(records, key=lambda item: item["route"])


def write_route_artifacts(output_dir: str):
    config = compiler.load_config()
    site_url = str(config.get("site_url", "") or config.get("siteUrl", "") or "").rstrip("/")
    routes = [item for item in route_records_for_build() if item["route"] not in {"/404", "/500"}]
    write_text_file(os.path.join(output_dir, "_tw", "route-manifest.json"), json.dumps(routes, indent=2, ensure_ascii=False) + "\n")

    api_manifest = []
    for api in discover_api_routes():
        methods = parse_api_route_file(api["path"])
        api_manifest.append({
            "route": api["route"],
            "methods": sorted(methods.keys()),
            "source": compiler.safe_relpath(api["path"], compiler.PROJECT_ROOT),
        })
    write_text_file(os.path.join(output_dir, "_tw", "api-manifest.json"), json.dumps(api_manifest, indent=2, ensure_ascii=False) + "\n")

    if site_url:
        lines = ['<?xml version="1.0" encoding="UTF-8"?>', '<urlset xmlns="http://www.sitemaps.org/schemas/sitemap/0.9">']
        for route in routes:
            lines.append("  <url>")
            lines.append(f"    <loc>{html.escape(site_url + route['route'])}</loc>")
            lines.append("  </url>")
        lines.append("</urlset>")
        write_text_file(os.path.join(output_dir, "sitemap.xml"), "\n".join(lines) + "\n")

        rss_lines = [
            '<?xml version="1.0" encoding="UTF-8"?>',
            '<rss version="2.0">',
            "<channel>",
            f"  <title>{html.escape(str(config.get('name', 'TW Site')))}</title>",
            f"  <link>{html.escape(site_url)}</link>",
            f"  <description>{html.escape(str(config.get('description', 'TW generated feed')))}</description>",
        ]
        for route in routes:
            rss_lines.append("  <item>")
            rss_lines.append(f"    <title>{html.escape(str(route.get('title') or route['route']))}</title>")
            rss_lines.append(f"    <link>{html.escape(site_url + route['route'])}</link>")
            rss_lines.append(f"    <guid>{html.escape(site_url + route['route'])}</guid>")
            rss_lines.append("    <pubDate>" + formatdate(usegmt=True) + "</pubDate>")
            rss_lines.append("  </item>")
        rss_lines.extend(["</channel>", "</rss>"])
        write_text_file(os.path.join(output_dir, "rss.xml"), "\n".join(rss_lines) + "\n")

    robots_content = "User-agent: *\nAllow: /\n"
    if site_url:
        robots_content += f"Sitemap: {site_url}/sitemap.xml\n"
    write_text_file(os.path.join(output_dir, "robots.txt"), robots_content)

    # Optional: lightweight client-side search index
    search_enabled = bool(config.get("search", config.get("search_index", config.get("searchIndex", False))))
    if search_enabled:
        try:
            write_search_index(output_dir, routes)
        except Exception as err:
            print(f"  ⚠️  Search index build skipped: {err}")


def strip_html_to_text(html_text: str) -> str:
    # Remove script/style blocks
    html_text = re.sub(r"<script[\\s\\S]*?</script>", " ", html_text, flags=re.I)
    html_text = re.sub(r"<style[\\s\\S]*?</style>", " ", html_text, flags=re.I)
    # Remove tags
    html_text = re.sub(r"<[^>]+>", " ", html_text)
    # Decode entities + normalize whitespace
    html_text = html.unescape(html_text)
    html_text = re.sub(r"\\s+", " ", html_text).strip()
    return html_text


def write_search_index(output_dir: str, routes: List[dict]):
    """
    Generates: dist/_tw/search-index.json
    Format: [{route,title,excerpt,content}]
    """
    items = []
    for route in routes:
        route_path = str(route.get("route") or "/")
        title = str(route.get("title") or route_path)
        source_html = None
        for candidate in build_preview_candidates(output_dir, route_path):
            if os.path.exists(candidate) and os.path.isfile(candidate):
                source_html = compiler.read_text_file(candidate)
                break
        if not source_html:
            continue
        content = strip_html_to_text(source_html)
        if not content:
            continue
        excerpt = content[:240]
        items.append({
            "route": route_path,
            "title": title,
            "excerpt": excerpt,
            "content": content[:4000],
        })

    write_text_file(
        os.path.join(output_dir, "_tw", "search-index.json"),
        json.dumps(items, indent=2, ensure_ascii=False) + "\n",
    )


def precompress_output(output_dir: str):
    try:
        import brotli  # type: ignore
    except Exception:
        brotli = None

    compress_exts = {".html", ".css", ".js", ".json", ".xml", ".txt", ".svg"}
    for root, _, files in os.walk(output_dir):
        for filename in files:
            ext = os.path.splitext(filename)[1].lower()
            if ext not in compress_exts:
                continue
            path = os.path.join(root, filename)
            with open(path, "rb") as f:
                payload = f.read()
            with gzip.open(path + ".gz", "wb", compresslevel=9) as gz:
                gz.write(payload)
            if brotli is not None:
                with open(path + ".br", "wb") as br:
                    br.write(brotli.compress(payload))


def ensure_deploy_support_files(project_root: str):
    netlify_toml = os.path.join(project_root, "netlify.toml")
    if not os.path.exists(netlify_toml):
        write_text_file(netlify_toml, '[build]\ncommand = "tw build --prod"\npublish = "dist"\n')

    dockerfile = os.path.join(project_root, "Dockerfile")
    if not os.path.exists(dockerfile):
        write_text_file(
            dockerfile,
            "FROM nginx:alpine\nCOPY dist /usr/share/nginx/html\nEXPOSE 80\nCMD [\"nginx\", \"-g\", \"daemon off;\"]\n",
        )

    github_workflow = os.path.join(project_root, ".github", "workflows", "tw-pages.yml")
    if not os.path.exists(github_workflow):
        write_text_file(
            github_workflow,
            """name: Deploy TW Pages
on:
  push:
    branches: [main]
jobs:
  build:
    runs-on: ubuntu-latest
    steps:
      - uses: actions/checkout@v4
      - uses: actions/setup-python@v5
        with:
          python-version: "3.11"
      - run: pip install .
      - run: tw build --prod
      - uses: actions/upload-pages-artifact@v3
        with:
          path: dist
  deploy:
    needs: build
    permissions:
      pages: write
      id-token: write
    runs-on: ubuntu-latest
    environment:
      name: github-pages
    steps:
      - uses: actions/deploy-pages@v4
""",
        )


def build_hidden_site(project_root: str, output_dir: str, force: bool = False, workers: Optional[int] = None, minify: bool = True) -> BuildSummary:
    project_root = os.path.abspath(project_root)
    output_dir = os.path.abspath(output_dir)
    workers = workers or compiler.DEFAULT_WORKERS

    configure_compiler_paths(project_root)
    invalidate_compiler_caches()
    load_project_env(project_root, "production")
    ensure_project_metadata(project_root)
    ensure_deploy_support_files(project_root)
    previous_minify = getattr(compiler, "MINIFY_OUTPUT", False)
    try:
        with compiler_output_context(output_dir):
            compiler.MINIFY_OUTPUT = minify
            os.makedirs(output_dir, exist_ok=True)
            os.makedirs(compiler.PUBLIC_ASSETS_DIR, exist_ok=True)
            os.makedirs(compiler.CACHE_DIR, exist_ok=True)
            os.makedirs(compiler.MANIFEST_DIR, exist_ok=True)
            os.makedirs(compiler.COMPILER_DIR, exist_ok=True)

            css_url, _ = compiler.read_global_stylesheet()
            manifest = compiler.load_build_manifest()

            compiler.copy_assets()
            compiler.verify_api_isolated()

            pages = compiler.discover_pages()
            current_page_keys = {compiler.page_cache_key(page) for page in pages}
            removed = compiler.remove_deleted_page_outputs(manifest, current_page_keys)

            dependency_map = {}
            pages_to_build = []
            skipped = 0
            errors = 0
            built = 0

            options = compiler.BuildOptions(force=force, workers=workers)

            for page_info in pages:
                try:
                    dependencies = compiler.collect_page_dependencies(page_info["path"])
                    dependency_map[compiler.page_cache_key(page_info)] = dependencies
                    needs_build, reason = compiler.should_rebuild_page(page_info, dependencies, manifest, options)
                    if needs_build:
                        pages_to_build.append(page_info)
                    else:
                        skipped += 1
                        print(f"  ⏭️  {compiler.safe_relpath(page_info['path'], compiler.PROJECT_ROOT)} ({reason})")
                except Exception as err:
                    errors += 1
                    compiler.print_compiler_error(page_info, err)

            if pages_to_build:
                with compiler.concurrent.futures.ThreadPoolExecutor(max_workers=workers) as executor:
                    future_map = {
                        executor.submit(compiler.build_page_job, page_info, css_url): page_info
                        for page_info in pages_to_build
                    }
                    for future in compiler.concurrent.futures.as_completed(future_map):
                        page_info = future_map[future]
                        try:
                            result = future.result()
                            outputs = result["outputs"]
                            compiler.update_page_manifest_entry(
                                manifest,
                                page_info,
                                dependency_map[compiler.page_cache_key(page_info)],
                                outputs,
                            )
                            for out_path in outputs:
                                rel_out = os.path.relpath(out_path, output_dir)
                                print(f"  ✅ {rel_out}")
                                built += 1
                        except Exception as err:
                            errors += 1
                            compiler.print_compiler_error(page_info, err)

            try:
                ts_outputs = compile_typescript_sources(project_root, output_dir)
                if ts_outputs:
                    print(f"  ✅ TypeScript emitted: {len(ts_outputs)} file(s)")
            except Exception as err:
                errors += 1
                print(f"  ❌ {err}")

            sync_runtime_chunks_to_output()
            write_hidden_cache_files(dependency_map)
            compiler.save_build_manifest(manifest)
            write_route_artifacts(output_dir)
            precompress_output(output_dir)

        return BuildSummary(
            built=built,
            skipped=skipped,
            removed=removed,
            errors=errors,
            output_dir=output_dir,
        )
    finally:
        compiler.MINIFY_OUTPUT = previous_minify


def clean_project_outputs(project_root: str):
    project_root = os.path.abspath(project_root)
    configure_compiler_paths(project_root)

    for path in [compiler.PUBLIC_DIR, compiler.INTERNAL_DIR]:
        if os.path.exists(path):
            shutil.rmtree(path)

    os.makedirs(compiler.CACHE_DIR, exist_ok=True)
    os.makedirs(compiler.MANIFEST_DIR, exist_ok=True)
    os.makedirs(compiler.COMPILER_DIR, exist_ok=True)
    os.makedirs(compiler.PUBLIC_DIR, exist_ok=True)


def inspect_project(project_root: str) -> dict:
    project = TWProject(project_root)
    pages = project.discover_pages()
    components_dir = os.path.join(project_root, "[home]", "components")
    component_count = 0
    if os.path.isdir(components_dir):
        for name in os.listdir(components_dir):
            if name.endswith(".tw"):
                component_count += 1

    dynamic_routes = sum(1 for page in pages if page["type"] == "dynamic")
    static_routes = sum(1 for page in pages if page["type"] == "static")
    return {
        "project_root": project_root,
        "source_root": compiler.HOME_DIR,
        "output_dir": compiler.PUBLIC_DIR,
        "hidden_dir": compiler.INTERNAL_DIR,
        "page_count": len(pages),
        "static_routes": static_routes,
        "dynamic_routes": dynamic_routes,
        "component_count": component_count,
        "has_404": project.find_special_page(404) is not None,
        "has_500": project.find_special_page(500) is not None,
    }


def doctor_project(project_root: str) -> List[dict]:
    project_root = os.path.abspath(project_root)
    configure_compiler_paths(project_root)
    checks = []

    def add_check(name: str, ok: bool, detail: str):
        checks.append({"name": name, "ok": ok, "detail": detail})

    add_check("tw.config", os.path.exists(compiler.CONFIG_FILE), compiler.CONFIG_FILE)
    add_check("[home]", os.path.isdir(compiler.HOME_DIR), compiler.HOME_DIR)
    add_check("package.json", os.path.exists(os.path.join(project_root, "package.json")), os.path.join(project_root, "package.json"))
    add_check("vercel.json", os.path.exists(os.path.join(project_root, "vercel.json")), os.path.join(project_root, "vercel.json"))
    add_check("netlify.toml", os.path.exists(os.path.join(project_root, "netlify.toml")), os.path.join(project_root, "netlify.toml"))
    add_check("Dockerfile", os.path.exists(os.path.join(project_root, "Dockerfile")), os.path.join(project_root, "Dockerfile"))
    add_check("TypeScript compiler", shutil.which("tsc") is not None, shutil.which("tsc") or "`tsc` not installed")
    add_check("Vercel CLI", shutil.which("vercel") is not None, shutil.which("vercel") or "`vercel` not installed")
    add_check("Cloudflare Wrangler", shutil.which("wrangler") is not None, shutil.which("wrangler") or "`wrangler` not installed")

    project_info = inspect_project(project_root)
    add_check("Route discovery", project_info["page_count"] > 0, f"{project_info['page_count']} route(s) discovered")
    add_check(
        "Custom 404 page",
        project_info["has_404"],
        "`[home]/pages/404.tw` detected" if project_info["has_404"] else "Add `[home]/pages/404.tw` for branded not-found pages",
    )
    add_check(
        "Custom 500 page",
        project_info["has_500"],
        "`[home]/pages/500.tw` detected" if project_info["has_500"] else "Add `[home]/pages/500.tw` for branded server error pages",
    )
    add_check("API routes", len(discover_api_routes()) >= 0, f"{len(discover_api_routes())} API route(s) discovered")
    return checks


def deploy_with_vercel(output_dir: str, production: bool):
    vercel_bin = shutil.which("vercel")
    if not vercel_bin:
        raise RuntimeError("`vercel` CLI install nahi hai. Pehle Vercel CLI install karo.")

    command = [vercel_bin, "deploy", output_dir, "--yes"]
    if production:
        command.append("--prod")

    token = os.environ.get("VERCEL_TOKEN")
    if token:
        command.extend(["--token", token])

    subprocess.run(command, check=True)


def deploy_with_cloudflare(output_dir: str, project_name: str):
    wrangler_bin = shutil.which("wrangler")
    if not wrangler_bin:
        raise RuntimeError("`wrangler` CLI install nahi hai. Pehle Cloudflare Wrangler install karo.")

    command = [
        wrangler_bin,
        "pages",
        "deploy",
        output_dir,
        "--project-name",
        project_name,
    ]
    subprocess.run(command, check=True)


def deploy_with_netlify(output_dir: str):
    netlify_bin = shutil.which("netlify")
    if not netlify_bin:
        print("`netlify` CLI nahi mila. Static output aur `netlify.toml` ready hain.")
        return
    subprocess.run([netlify_bin, "deploy", "--dir", output_dir, "--prod"], check=True)


def deploy_with_docker(project_root: str, production: bool):
    docker_bin = shutil.which("docker")
    if not docker_bin:
        print("`docker` CLI nahi mila. `Dockerfile` ready hai.")
        return
    tag = os.path.basename(os.path.abspath(project_root)).lower().replace("_", "-") + (":prod" if production else ":latest")
    subprocess.run([docker_bin, "build", "-t", tag, project_root], check=True)


def run_deploy(project_root: str, output_dir: str, provider: str, production: bool):
    ensure_deploy_support_files(project_root)
    checks = doctor_project(project_root)
    blocking_failures = [check for check in checks if not check["ok"] and check["name"] in {"tw.config", "[home]", "Route discovery"}]
    if blocking_failures:
        raise RuntimeError("Project checks failed. Config ya route structure pehle theek karo.")
    summary = build_hidden_site(project_root, output_dir, force=True, minify=production)
    if summary.errors:
        raise RuntimeError("Build me errors aaye. Deploy abort kar diya gaya.")

    if provider == "local":
        print(f"Local deploy package ready: {summary.output_dir}")
        return

    if provider == "vercel":
        deploy_with_vercel(summary.output_dir, production)
        return

    if provider == "cloudflare":
        project_name = os.path.basename(os.path.abspath(project_root)).lower().replace("_", "-")
        deploy_with_cloudflare(summary.output_dir, project_name)
        return

    if provider == "netlify":
        deploy_with_netlify(summary.output_dir)
        return

    if provider == "github-pages":
        print("GitHub Pages workflow file ready hai. Repo push karte hi deploy run hoga.")
        return

    if provider == "docker":
        deploy_with_docker(project_root, production)
        return

    raise RuntimeError(f"Unsupported provider: {provider}")


def parse_args():
    parser = argparse.ArgumentParser(description="TW framework CLI")
    parser.add_argument("--project-root", default=DEFAULT_PROJECT_ROOT, help="TW project root")

    subparsers = parser.add_subparsers(dest="command", required=True)

    dev_parser = subparsers.add_parser("dev", help="In-memory dev server chalao")
    dev_parser.add_argument("--host", default=DEFAULT_DEV_HOST)
    dev_parser.add_argument("--port", type=int, default=DEFAULT_DEV_PORT)

    build_parser = subparsers.add_parser("build", help="Hidden production build generate karo")
    build_parser.add_argument("--out-dir", default=DEFAULT_INTERNAL_OUTPUT)
    build_parser.add_argument("--force", action="store_true")
    build_parser.add_argument("--workers", type=int, default=compiler.DEFAULT_WORKERS)

    deploy_parser = subparsers.add_parser("deploy", help="Build karke hosting par bhejo")
    deploy_parser.add_argument("--out-dir", default=DEFAULT_INTERNAL_OUTPUT)
    deploy_parser.add_argument("--provider", default="local", choices=["local", "vercel", "cloudflare", "netlify", "github-pages", "docker"])
    deploy_parser.add_argument("--prod", action="store_true")

    return parser.parse_args()


def main():
    args = parse_args()

    if args.command == "dev":
        run_dev_server(args.project_root, args.host, args.port)
        return

    if args.command == "build":
        summary = build_hidden_site(
            project_root=args.project_root,
            output_dir=args.out_dir,
            force=args.force,
            workers=args.workers,
        )
        print(
            f"\nTW build complete — {summary.built} generated, "
            f"{summary.skipped} skipped, {summary.removed} removed, {summary.errors} errors"
        )
        print(f"Internal output: {summary.output_dir}")
        return

    if args.command == "deploy":
        run_deploy(
            project_root=args.project_root,
            output_dir=args.out_dir,
            provider=args.provider,
            production=args.prod,
        )
        print("Deploy complete.")
        return


if __name__ == "__main__":
    main()
