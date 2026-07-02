import argparse
import base64
import contextlib
import fnmatch
import gzip
import hashlib
import hmac
import html
import http.server
import json
import logging
import mimetypes
import os
import posixpath
import re
import secrets
import shutil
import socketserver
import subprocess
import sys
import threading
import time
import ctypes
import select
import struct
import urllib.parse
from email.utils import formatdate
from dataclasses import dataclass
from typing import Dict, List, Optional, Tuple

from . import compiler
from .common import content_hash, log
from .plugin_runtime import ExtensionManager
from .twm_parser import compile_twm_module_to_cjs, parse_twm_functions

logger = logging.getLogger(__name__)


for ext, content_type in {
    ".avif": "image/avif",
    ".mjs": "application/javascript",
    ".wasm": "application/wasm",
    ".webmanifest": "application/manifest+json",
    ".woff": "font/woff",
    ".woff2": "font/woff2",
    ".yaml": "application/yaml",
    ".yml": "application/yaml",
    ".toml": "application/toml",
}.items():
    mimetypes.add_type(content_type, ext)


SCRIPT_DIR = os.path.abspath(os.path.dirname(__file__))
DEFAULT_PROJECT_ROOT = os.path.abspath(os.path.join(SCRIPT_DIR, compiler.PROJECT_ROOT))
DEFAULT_INTERNAL_OUTPUT = os.path.join(DEFAULT_PROJECT_ROOT, "dist")
DEFAULT_DEV_HOST = "127.0.0.1"
DEFAULT_DEV_PORT = 3000
DEFAULT_PREVIEW_PORT = 4173
HIDDEN_FRAMEWORK_DIR = ".tw"
WATCH_EXTENSIONS = {
    ".tw", ".tss", ".ts", ".twm", ".json", ".md", ".py",
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
    warnings: int = 0
    route_collisions: int = 0


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
    if hasattr(compiler, "_COMPONENT_STYLESHEET_PATHS"):
        compiler._COMPONENT_STYLESHEET_PATHS.clear()
    compiler.INLINE_SCRIPTS.clear()
    # Reset script placeholder growth (prevents long-lived dev sessions from leaking memory)
    if hasattr(compiler, "_SCRIPT_COUNTER"):
        compiler._SCRIPT_COUNTER = 0
    # Optional caches introduced by newer versions
    if hasattr(compiler, "_LAYOUT_META_CACHE"):
        compiler._LAYOUT_META_CACHE.clear()


def use_modular_pipeline(config: Optional[Dict] = None) -> bool:
    env_value = os.environ.get("TW_USE_MODULAR_PIPELINE")
    if env_value is not None and str(env_value).strip() != "":
        return str(env_value).strip().lower() in {"1", "true", "yes", "on"}
    config = config or compiler.load_config()
    return compiler.to_bool(config.get("modular_pipeline", config.get("modularPipeline", False)))


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


def build_page_with_modular_pipeline(page_info: dict, css_url: str) -> List[str]:
    tw_path = page_info["path"]
    config = compiler.load_config()
    pretty_urls = compiler.to_bool(config.get("pretty_urls", config.get("prettyUrls", False)))

    def render_and_write(route_path: str, render_context: Dict, out_path: str) -> str:
        artifacts = compiler.compile_file_pipeline(
            tw_path,
            context=render_context,
            css_href=css_url,
            route_path=route_path,
        )
        html_text = artifacts.html or ""
        if compiler.MINIFY_OUTPUT:
            html_text = compiler.minify_html_content(html_text)
        os.makedirs(os.path.dirname(out_path), exist_ok=True)
        with open(out_path, "w", encoding="utf-8") as handle:
            handle.write(html_text)
        return out_path

    if page_info["type"] == "static":
        page_ast = compiler.load_page_ast_from_file(tw_path)
        route_path = compiler.route_path_from_page_info(page_info)
        base_context = compiler.build_page_context(page_info, page_ast, tw_path, route_path=route_path)
        out_dir = os.path.join(compiler.BUILD_DIR, page_info["rel_dir"]) if page_info["rel_dir"] else compiler.BUILD_DIR
        if pretty_urls and page_info["name"] != "index":
            out_dir = os.path.join(out_dir, page_info["name"])
            out_path = os.path.join(out_dir, "index.html")
        else:
            out_path = os.path.join(out_dir, f"{page_info['name']}.html")
        return [render_and_write(route_path, base_context, out_path)]

    built_paths: List[str] = []
    items = compiler.load_dynamic_items(tw_path)
    for item in items:
        if not isinstance(item, dict):
            continue
        segments = compiler.resolve_dynamic_segments(page_info, item)
        route_path = compiler.route_path_from_page_info(page_info, item=item)
        context = compiler.build_page_context(page_info, compiler.load_page_ast_from_file(tw_path), tw_path, item=item, route_path=route_path)
        out_parts = [compiler.BUILD_DIR]
        if page_info["rel_dir"]:
            out_parts.append(page_info["rel_dir"])
        out_parts.extend(segments)
        out_dir = os.path.join(*out_parts)
        built_paths.append(render_and_write(route_path or "/", context, os.path.join(out_dir, "index.html")))
    return built_paths


def build_page_job_modular(page_info: dict, css_url: str) -> dict:
    outputs = build_page_with_modular_pipeline(page_info, css_url)
    return {"page_info": page_info, "outputs": outputs}


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


def is_path_within(root_path: str, candidate_path: str) -> bool:
    try:
        root_abs = os.path.abspath(root_path)
        candidate_abs = os.path.abspath(candidate_path)
        return os.path.commonpath([root_abs, candidate_abs]) == root_abs
    except (ValueError, OSError):
        return False


def _normalize_config_headers(raw_value) -> List[Tuple[str, str]]:
    if not raw_value:
        return []
    if isinstance(raw_value, dict):
        return [(str(key), str(value)) for key, value in raw_value.items()]
    if isinstance(raw_value, list):
        normalized = []
        for item in raw_value:
            if isinstance(item, dict):
                normalized.extend((str(key), str(value)) for key, value in item.items())
            elif isinstance(item, (list, tuple)) and len(item) == 2:
                normalized.append((str(item[0]), str(item[1])))
        return normalized
    return []


def get_security_headers(config: Optional[Dict]) -> List[Tuple[str, str]]:
    config = config or {}
    return (
        _normalize_config_headers(compiler.get_config_value(config, "security", "headers"))
        or _normalize_config_headers(config.get("security.headers"))
        or _normalize_config_headers(config.get("security_headers"))
        or _normalize_config_headers(config.get("headers"))
    )


def get_cookie_secure_mode(config: Optional[Dict]) -> str:
    config = config or {}
    raw_value = (
        compiler.get_config_value(config, "cookies", "secure")
        or config.get("cookies.secure")
        or config.get("cookies_secure")
        or "auto"
    )
    value = str(raw_value).strip().lower()
    if value in {"true", "1", "yes", "on"}:
        return "true"
    if value in {"false", "0", "no", "off"}:
        return "false"
    return "auto"


def request_uses_https(request_headers: Optional[Dict[str, str]] = None, server_port: Optional[int] = None) -> bool:
    request_headers = request_headers or {}
    forwarded_proto = str(request_headers.get("X-Forwarded-Proto", "")).split(",", 1)[0].strip().lower()
    if forwarded_proto:
        return forwarded_proto == "https"
    forwarded = str(request_headers.get("Forwarded", "")).lower()
    if "proto=https" in forwarded:
        return True
    return server_port == 443


def render_cookie_header(
    name: str,
    value: object,
    *,
    config: Optional[Dict] = None,
    request_headers: Optional[Dict[str, str]] = None,
    server_port: Optional[int] = None,
) -> str:
    rendered_value = urllib.parse.quote(str(value))
    parts = [f"{name}={rendered_value}", "Path=/", "HttpOnly", "SameSite=Lax"]
    secure_mode = get_cookie_secure_mode(config)
    if secure_mode == "true" or (secure_mode == "auto" and request_uses_https(request_headers, server_port=server_port)):
        parts.append("Secure")
    return "; ".join(parts)


def _csrf_secret() -> str:
    return (
        os.environ.get("TW_CSRF_SECRET")
        or os.environ.get("SECRET_KEY")
        or os.environ.get("API_TOKEN")
        or "tw-dev-csrf-secret"
    )


def _csrf_session_hint(request: Optional[Dict]) -> str:
    cookies = dict((request or {}).get("cookies") or {})
    for key in ("session_id", "session", "sid"):
        if cookies.get(key):
            return str(cookies[key])
    return ""


def generate_csrf_token(request: Optional[Dict] = None) -> str:
    issued_at = str(int(time.time()))
    nonce = secrets.token_urlsafe(16)
    session_hint = _csrf_session_hint(request)
    payload = f"{issued_at}:{nonce}:{session_hint}"
    signature = hmac.new(_csrf_secret().encode("utf-8"), payload.encode("utf-8"), hashlib.sha256).hexdigest()
    token = f"{payload}:{signature}".encode("utf-8")
    return base64.urlsafe_b64encode(token).decode("ascii").rstrip("=")


def verify_csrf_token(token: str, request: Optional[Dict] = None, *, max_age: int = 7200) -> bool:
    if not token:
        return False
    try:
        padding = "=" * (-len(token) % 4)
        decoded = base64.urlsafe_b64decode((token + padding).encode("ascii")).decode("utf-8")
        issued_at, nonce, session_hint, signature = decoded.split(":", 3)
        payload = f"{issued_at}:{nonce}:{session_hint}"
    except Exception:
        return False
    expected_signature = hmac.new(_csrf_secret().encode("utf-8"), payload.encode("utf-8"), hashlib.sha256).hexdigest()
    if not hmac.compare_digest(signature, expected_signature):
        return False
    try:
        if int(time.time()) - int(issued_at) > int(max_age):
            return False
    except (TypeError, ValueError):
        return False
    return session_hint == _csrf_session_hint(request)


class TokenBucketRateLimiter:
    def __init__(self, capacity: int, window_seconds: float):
        self.capacity = max(1, int(capacity))
        self.window_seconds = max(float(window_seconds), 1.0)
        self.refill_rate = self.capacity / self.window_seconds
        self._state: Dict[str, Tuple[float, float]] = {}
        self._lock = threading.Lock()

    def allow(self, bucket_key: str) -> bool:
        now = time.monotonic()
        with self._lock:
            tokens, updated_at = self._state.get(bucket_key, (float(self.capacity), now))
            elapsed = max(0.0, now - updated_at)
            tokens = min(float(self.capacity), tokens + elapsed * self.refill_rate)
            if tokens < 1.0:
                self._state[bucket_key] = (tokens, now)
                return False
            self._state[bucket_key] = (tokens - 1.0, now)
            return True


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
            value = value.strip()
            # Support `KEY=value # comment` (comment starts only when preceded by whitespace).
            # If value is quoted, keep everything inside quotes.
            if value.startswith(("'", '"')) and len(value) >= 2:
                quote = value[0]
                # Find the matching quote; anything after it is ignored (including comments).
                end_idx = value.find(quote, 1)
                if end_idx != -1:
                    value = value[1:end_idx]
                else:
                    value = value.strip(quote)
            else:
                value = re.split(r"\s+#", value, 1)[0].strip()
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
    expr, j = compiler.collect_until_eol(tokens, i, stop_on_block_open=True)
    if not expr:
        raise RuntimeError("Expected value token")
    return compiler.parse_literal_value(expr), j


def parse_middleware_rules(project_root: str) -> List[dict]:
    source_path = next((path for path in middleware_file_candidates(project_root) if os.path.exists(path)), None)
    if not source_path:
        return []

    tokens = compiler.tokenize_tw(compiler.read_text_file(source_path))
    rules = []

    def skip_separators(index):
        while index < len(tokens) and compiler.is_statement_separator(tokens[index]):
            index += 1
        return index

    def expect_block(index, label):
        index = skip_separators(index)
        if index >= len(tokens) or tokens[index].type != "BRACE" or tokens[index].value != "{":
            raise RuntimeError(f"Expected `{{` after `{label}` in middleware.tw")
        return index + 1

    def ensure_list(value):
        if value is None:
            return []
        if isinstance(value, (list, tuple, set)):
            return [str(item) for item in value]
        return [str(value)]

    def parse_object_block(index):
        index = expect_block(index, "json")
        data = {}
        while index < len(tokens):
            tok = tokens[index]
            if compiler.is_statement_separator(tok):
                index += 1
                continue
            if tok.type == "BRACE" and tok.value == "}":
                index += 1
                break
            if tok.type != "WORD":
                raise RuntimeError("Invalid object key in middleware.tw")
            key = tok.value
            index += 1
            index = skip_separators(index)
            if index < len(tokens) and tokens[index].type == "BRACE" and tokens[index].value == "{":
                value, index = parse_object_block(index - 0)
            else:
                value, index = parse_value_token(tokens, index)
            data[key] = value
        return data, index

    def parse_response_block(index):
        index = expect_block(index, "response")
        response = {"headers": [], "cookies": []}
        while index < len(tokens):
            tok = tokens[index]
            if compiler.is_statement_separator(tok):
                index += 1
                continue
            if tok.type == "BRACE" and tok.value == "}":
                index += 1
                break
            if tok.type != "WORD":
                raise RuntimeError("Invalid response directive in middleware.tw")
            key = tok.value
            index += 1
            if key == "status":
                response["status"], index = parse_value_token(tokens, index)
            elif key in {"text", "html", "content_type"}:
                response[key], index = parse_value_token(tokens, index)
            elif key == "json":
                response["json"], index = parse_object_block(index)
            elif key == "header":
                header_name, index = parse_value_token(tokens, index)
                header_value, index = parse_value_token(tokens, index)
                response["headers"].append((str(header_name), str(header_value)))
            elif key == "cookie":
                cookie_name, index = parse_value_token(tokens, index)
                cookie_value, index = parse_value_token(tokens, index)
                response["cookies"].append((str(cookie_name), str(cookie_value)))
            else:
                raise RuntimeError(f"Unsupported response key: {key}")
        return response, index

    def parse_user_agent_block(index):
        index = expect_block(index, "user_agent")
        spec = {"allow": [], "block": [], "empty_is_blocked": False}
        while index < len(tokens):
            tok = tokens[index]
            if compiler.is_statement_separator(tok):
                index += 1
                continue
            if tok.type == "BRACE" and tok.value == "}":
                index += 1
                break
            if tok.type != "WORD":
                raise RuntimeError("Invalid user_agent directive in middleware.tw")
            key = tok.value
            index += 1
            if key in {"allow", "block"}:
                value, index = parse_value_token(tokens, index)
                spec[key] = ensure_list(value)
            elif key == "empty_is_blocked":
                value, index = parse_value_token(tokens, index)
                spec["empty_is_blocked"] = bool(value)
            else:
                raise RuntimeError(f"Unsupported user_agent key: {key}")
        return spec, index

    def parse_origin_block(index):
        index = expect_block(index, "origin")
        spec = {"allow": [], "allow_referer": True, "require": False}
        while index < len(tokens):
            tok = tokens[index]
            if compiler.is_statement_separator(tok):
                index += 1
                continue
            if tok.type == "BRACE" and tok.value == "}":
                index += 1
                break
            if tok.type != "WORD":
                raise RuntimeError("Invalid origin directive in middleware.tw")
            key = tok.value
            index += 1
            if key == "allow":
                value, index = parse_value_token(tokens, index)
                spec["allow"] = ensure_list(value)
            elif key in {"allow_referer", "require"}:
                value, index = parse_value_token(tokens, index)
                spec[key] = bool(value)
            else:
                raise RuntimeError(f"Unsupported origin key: {key}")
        return spec, index

    def parse_path_block(index):
        index = expect_block(index, "path")
        spec = {
            "prefixes": [],
            "contains": [],
            "extensions": [],
            "regex": [],
            "single_segment_max": 0,
            "deny_traversal": True,
            "deny_null_bytes": True,
        }
        while index < len(tokens):
            tok = tokens[index]
            if compiler.is_statement_separator(tok):
                index += 1
                continue
            if tok.type == "BRACE" and tok.value == "}":
                index += 1
                break
            if tok.type != "WORD":
                raise RuntimeError("Invalid path directive in middleware.tw")
            key = tok.value
            index += 1
            if key in {"prefixes", "contains", "extensions", "regex"}:
                value, index = parse_value_token(tokens, index)
                spec[key] = ensure_list(value)
            elif key == "single_segment_max":
                value, index = parse_value_token(tokens, index)
                spec[key] = int(value or 0)
            elif key in {"deny_traversal", "deny_null_bytes"}:
                value, index = parse_value_token(tokens, index)
                spec[key] = bool(value)
            else:
                raise RuntimeError(f"Unsupported path key: {key}")
        return spec, index

    def parse_auth_block(index):
        index = expect_block(index, "auth")
        spec = {"cookie": "", "jwt_secret": "", "jwt_secret_env": "", "required": True}
        while index < len(tokens):
            tok = tokens[index]
            if compiler.is_statement_separator(tok):
                index += 1
                continue
            if tok.type == "BRACE" and tok.value == "}":
                index += 1
                break
            if tok.type != "WORD":
                raise RuntimeError("Invalid auth directive in middleware.tw")
            key = tok.value
            index += 1
            if key in {"cookie", "jwt_secret", "jwt_secret_env"}:
                spec[key], index = parse_value_token(tokens, index)
            elif key == "required":
                value, index = parse_value_token(tokens, index)
                spec["required"] = bool(value)
            else:
                raise RuntimeError(f"Unsupported auth key: {key}")
        return spec, index

    def parse_rate_limit_block(index):
        index = expect_block(index, "rate_limit")
        rate_limit = {"identity": "ip", "bucket_segments": 2}
        while index < len(tokens):
            tok = tokens[index]
            if compiler.is_statement_separator(tok):
                index += 1
                continue
            if tok.type == "BRACE" and tok.value == "}":
                index += 1
                break
            if tok.type != "WORD":
                raise RuntimeError("Invalid rate_limit directive")
            inner_key = tok.value
            index += 1
            inner_value, index = parse_value_token(tokens, index)
            rate_limit[inner_key] = inner_value
        requests = int(compiler.parse_config_scalar(rate_limit.get("requests", 0)) or 0)
        window = float(compiler.parse_config_scalar(rate_limit.get("window", 0)) or 0)
        if requests <= 0 or window <= 0:
            raise RuntimeError("`rate_limit` requires positive `requests` and `window` values")
        return {
            "requests": requests,
            "window": window,
            "identity": str(rate_limit.get("identity", "ip") or "ip"),
            "bucket_segments": int(rate_limit.get("bucket_segments", 2) or 2),
        }, index

    i = 0
    while i < len(tokens):
        token = tokens[i]
        if compiler.is_statement_separator(token):
            i += 1
            continue
        if token.type == "WORD" and token.value in {"use", "rule"}:
            i += 1
            i = skip_separators(i)
            rule = {"name": "", "match": "/**", "methods": [], "headers": [], "cookies": []}
            if i < len(tokens) and tokens[i].type in {"STRING", "WORD"}:
                next_tok = tokens[i + 1] if i + 1 < len(tokens) else None
                if next_tok and next_tok.type == "BRACE" and next_tok.value == "{":
                    rule["name"] = str(tokens[i].value)
                    i += 1
            i = expect_block(i, token.value)
            while i < len(tokens):
                tok = tokens[i]
                if compiler.is_statement_separator(tok):
                    i += 1
                    continue
                if tok.type == "BRACE" and tok.value == "}":
                    i += 1
                    break
                if tok.type != "WORD":
                    raise RuntimeError("Invalid middleware directive")
                key = tok.value
                i += 1
                if key == "match":
                    rule["match"], i = parse_value_token(tokens, i)
                elif key == "methods":
                    methods, i = parse_value_token(tokens, i)
                    rule["methods"] = [str(item).upper() for item in ensure_list(methods)]
                elif key == "redirect":
                    rule["redirect"], i = parse_value_token(tokens, i)
                elif key == "rewrite":
                    rule["rewrite"], i = parse_value_token(tokens, i)
                elif key == "response":
                    rule["response"], i = parse_response_block(i)
                elif key == "user_agent":
                    rule["user_agent"], i = parse_user_agent_block(i)
                elif key == "origin":
                    rule["origin"], i = parse_origin_block(i)
                elif key == "path":
                    rule["path_rule"], i = parse_path_block(i)
                elif key == "auth_rule":
                    rule["auth_rule"], i = parse_auth_block(i)
                elif key == "deny":
                    # Syntax:
                    #   deny 403 "Forbidden"
                    # Returns an immediate response without redirect/rewrite.
                    raw_status, i = parse_value_token(tokens, i)
                    status = int(compiler.parse_config_scalar(raw_status) or raw_status)
                    # Optional message/body
                    message = "Forbidden"
                    if i < len(tokens) and not compiler.is_statement_separator(tokens[i]) and not (
                        tokens[i].type == "BRACE" and tokens[i].value == "}"
                    ):
                        message, i = parse_value_token(tokens, i)
                    rule["deny"] = {"status": status, "body": str(message)}
                elif key == "auth":
                    i = skip_separators(i)
                    if i < len(tokens) and tokens[i].type == "BRACE" and tokens[i].value == "{":
                        rule["auth_rule"], i = parse_auth_block(i)
                    else:
                        cookie_name, i = parse_value_token(tokens, i)
                        redirect_to, i = parse_value_token(tokens, i)
                        rule["auth"] = {"cookie": cookie_name, "redirect": redirect_to}
                elif key == "header":
                    header_name, i = parse_value_token(tokens, i)
                    header_value, i = parse_value_token(tokens, i)
                    rule["headers"].append((str(header_name), str(header_value)))
                elif key == "cookie":
                    cookie_name, i = parse_value_token(tokens, i)
                    cookie_value, i = parse_value_token(tokens, i)
                    rule["cookies"].append((str(cookie_name), str(cookie_value)))
                elif key == "rate_limit":
                    rule["rate_limit"], i = parse_rate_limit_block(i)
                elif key in {"status", "text", "html", "content_type"}:
                    rule.setdefault("response", {"headers": [], "cookies": []})
                    value, i = parse_value_token(tokens, i)
                    rule["response"][key] = value
                elif key == "json":
                    rule.setdefault("response", {"headers": [], "cookies": []})
                    rule["response"]["json"], i = parse_object_block(i)
                else:
                    raise RuntimeError(f"Unsupported middleware key: {key}")
            rules.append(rule)
            continue
        i += 1
    return rules


def _middleware_header(request_headers: Dict[str, str], name: str, default: str = "") -> str:
    lname = str(name).lower()
    for key, value in (request_headers or {}).items():
        if str(key).lower() == lname:
            return str(value)
    return default


def _middleware_list(value) -> List[str]:
    if value is None:
        return []
    if isinstance(value, (list, tuple, set)):
        return [str(item) for item in value]
    return [str(value)]


def _middleware_referer_origin(referer: str) -> str:
    parsed = urllib.parse.urlparse(str(referer or ""))
    if not parsed.scheme or not parsed.netloc:
        return ""
    return f"{parsed.scheme}://{parsed.netloc}"


def _jwt_b64url_decode(value: str) -> bytes:
    padding = "=" * ((4 - (len(value) % 4)) % 4)
    return base64.urlsafe_b64decode((value + padding).encode("ascii"))


def _verify_hs256_jwt(token: str, secret: str) -> bool:
    try:
        parts = str(token or "").split(".")
        if len(parts) != 3:
            return False
        header, payload, signature = parts
        signing_input = f"{header}.{payload}".encode("utf-8")
        expected = hmac.new(str(secret or "").encode("utf-8"), signing_input, hashlib.sha256).digest()
        actual = _jwt_b64url_decode(signature)
        if not hmac.compare_digest(expected, actual):
            return False
        payload_obj = json.loads(_jwt_b64url_decode(payload).decode("utf-8", errors="replace") or "{}")
        exp = payload_obj.get("exp")
        if exp and time.time() > float(exp):
            return False
        return True
    except Exception:
        return False


def _build_middleware_response(
    rule: dict,
    result: dict,
    *,
    default_status: int,
    default_text: str,
    default_content_type: str = "text/plain; charset=utf-8",
    extra_headers: Optional[List[Tuple[str, str]]] = None,
) -> dict:
    spec = dict(rule.get("response") or {})
    status = int(spec.get("status", default_status) or default_status)
    headers = list(result.get("headers", [])) + list(spec.get("headers", [])) + list(extra_headers or [])
    cookies = list(result.get("cookies", [])) + list(spec.get("cookies", []))
    if "json" in spec:
        body = json.dumps(spec.get("json"), ensure_ascii=False).encode("utf-8")
        content_type = str(spec.get("content_type") or "application/json; charset=utf-8")
    elif "html" in spec:
        body = str(spec.get("html", default_text) or default_text).encode("utf-8")
        content_type = str(spec.get("content_type") or "text/html; charset=utf-8")
    else:
        body = str(spec.get("text", default_text) or default_text).encode("utf-8")
        content_type = str(spec.get("content_type") or default_content_type)
    return {
        "status": status,
        "content_type": content_type,
        "body": body,
        "headers": headers,
        "cookies": cookies,
    }


def discover_api_routes() -> List[dict]:
    return discover_twm_api_handlers()


def discover_twm_api_handlers() -> List[dict]:
    """
    Discover folder-based route handlers as server-side TW script API handlers.

    Contract:
    - `get(request)`, `post(request)`, ... or `handler(request)`
    - No top-level statements allowed in `.twm` (enforced by parser)
    """
    routes = []
    if not os.path.isdir(compiler.API_DIR):
        return routes
    for root, _, files in os.walk(compiler.API_DIR):
        rel_dir = os.path.relpath(root, compiler.API_DIR)
        rel_dir = compiler.normalize_route_directory(rel_dir)
        for filename in sorted(files):
            if filename != "route.twm":
                continue
            segments = ["api"]
            if rel_dir and rel_dir != ".":
                segments.extend(rel_dir.split(os.sep))
            route_path = "/" + "/".join(filter(None, segments))
            routes.append({"path": os.path.join(root, filename), "route": route_path, "lang": "twm"})
    return routes


def _compile_twm_api_handler_to_cache(handler_path: str) -> str:
    cache_dir = os.path.join(compiler.CACHE_DIR, "twm_api")
    os.makedirs(cache_dir, exist_ok=True)
    with open(handler_path, "r", encoding="utf-8") as f:
        src = f.read()
    digest = content_hash(f"{handler_path}::{src}", length=16)
    out_path = os.path.join(cache_dir, f"{digest}.cjs")
    if not os.path.isfile(out_path):
        js = compile_twm_module_to_cjs(src, module_id=handler_path)
        with open(out_path, "w", encoding="utf-8") as f:
            f.write(js)
    return out_path


def execute_twm_api_handler(handler_path: str, method: str, url_path: str,
                            headers: Dict[str, str], body: object) -> dict:
    """
    Execute a `.twm` API handler (server-side TW scripting) via Node.js.

    The `.twm` module should export one of:
      - `get/post/put/patch/delete/options(request)`
      - or a generic `handler(request)`

    Response shapes (JS):
      - string => text/plain
      - object => JSON (unless it includes {json|text|html|body,status,headers,cookies})
      - array => [body, status] or [body, status, headers]
    """
    compiled = _compile_twm_api_handler_to_cache(handler_path)
    runner = os.path.join(SCRIPT_DIR, "twm_api_runner.js")
    if not os.path.isfile(runner):
        raise RuntimeError("Missing twm_api_runner.js (framework installation is incomplete).")

    query = urllib.parse.parse_qs(urllib.parse.urlparse(url_path).query, keep_blank_values=True)
    query = {k: v[0] if len(v) == 1 else v for k, v in query.items()}
    cookies = parse_cookie_header(headers.get("Cookie", ""))
    project_root = os.path.abspath(getattr(compiler, "PROJECT_ROOT", os.getcwd()) or os.getcwd())
    request = {
        "method": method.upper(),
        "path": normalize_url_path(url_path),
        "query": query,
        "body": body,
        "headers": headers,
        "cookies": cookies,
        "env": dict(os.environ),
        "project_root": project_root,
    }

    timeout_s = float(os.environ.get("TW_TWM_TIMEOUT", "10") or "10")
    proc = subprocess.run(
        ["node", runner, compiled],
        input=json.dumps(request, ensure_ascii=False),
        text=True,
        capture_output=True,
        timeout=max(1.0, timeout_s),
        cwd=project_root,
    )
    if proc.returncode != 0:
        raise RuntimeError(f"TWM handler failed (exit={proc.returncode}): {proc.stderr.strip() or proc.stdout.strip()}")

    try:
        resp = json.loads(proc.stdout or "{}")
    except json.JSONDecodeError as err:
        raise RuntimeError(f"TWM runner returned invalid JSON: {err}: {proc.stdout[:2000]!r}") from err

    status = int(resp.get("status", 200) or 200)
    content_type = str(resp.get("content_type") or "application/json; charset=utf-8")
    headers_out = resp.get("headers") or []
    cookies_out = resp.get("cookies") or []
    body_val = resp.get("body", "")

    if isinstance(body_val, (dict, list)):
        body_bytes = json.dumps(body_val, ensure_ascii=False).encode("utf-8")
        content_type = "application/json; charset=utf-8"
    else:
        body_bytes = str(body_val).encode("utf-8")

    return {
        "status": status,
        "content_type": content_type,
        "body": body_bytes,
        "headers": list(headers_out),
        "cookies": list(cookies_out),
    }


def parse_api_route_file(tw_path: str) -> Dict[str, dict]:
    tokens = compiler.tokenize_tw(compiler.read_text_file(tw_path))
    methods = {}
    i = 0
    while i < len(tokens):
        token = tokens[i]
        if compiler.is_statement_separator(token):
            i += 1
            continue
        if token.type != "WORD":
            i += 1
            continue
        method = token.value.upper()
        if method not in {"GET", "POST", "PUT", "PATCH", "DELETE", "OPTIONS"}:
            i += 1
            continue
        i += 1
        while i < len(tokens) and compiler.is_statement_separator(tokens[i]):
            i += 1
        if i >= len(tokens) or tokens[i].type != "BRACE" or tokens[i].value != "{":
            raise RuntimeError(f"Expected `{{` after `{method}` in {tw_path}")
        i += 1
        spec = {"status": 200, "headers": [], "cookies": []}
        while i < len(tokens):
            tok = tokens[i]
            if compiler.is_statement_separator(tok):
                i += 1
                continue
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
            except json.JSONDecodeError:
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
        except (json.JSONDecodeError, UnicodeDecodeError):
            return {"raw": raw.decode("utf-8", errors="replace")}
    if "application/x-www-form-urlencoded" in content_type:
        parsed = urllib.parse.parse_qs(raw.decode("utf-8"), keep_blank_values=True)
        return {key: value[0] if len(value) == 1 else value for key, value in parsed.items()}
    return {"raw": raw.decode("utf-8", errors="replace"), "bytes": len(raw)}


class TWProject:
    def __init__(self, project_root: str):
        self.project_root = os.path.abspath(project_root)
        self._lock = threading.RLock()
        configure_compiler_paths(self.project_root)
        self.env = load_project_env(self.project_root, "development")
        self.config = compiler.load_config()
        self.modular_pipeline = use_modular_pipeline(self.config)
        self.extensions = ExtensionManager(self.project_root, self.config, self.env).refresh()
        self._rate_limiters: Dict[str, TokenBucketRateLimiter] = {}

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
        self.modular_pipeline = use_modular_pipeline(self.config)
        self.extensions.refresh(self.config, self.env)

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
            if is_path_within(compiler.ASSETS_DIR, candidate):
                payload = safe_read_binary(candidate)
                if payload is not None:
                    content_type = mimetypes.guess_type(candidate)[0] or "application/octet-stream"
                    return payload, content_type

        if path.startswith("/_tw/static/chunks/"):
            candidate = os.path.abspath(os.path.join(compiler.CHUNKS_DIR, path.split("/_tw/static/chunks/", 1)[1]))
            if is_path_within(compiler.CHUNKS_DIR, candidate):
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

    def _get_rate_limiter(self, rule: dict) -> Optional[TokenBucketRateLimiter]:
        rate_limit = rule.get("rate_limit")
        if not rate_limit:
            return None
        limiter_key = f"{rule.get('match', '/**')}::{rate_limit['requests']}::{rate_limit['window']}"
        limiter = self._rate_limiters.get(limiter_key)
        if limiter is None:
            limiter = TokenBucketRateLimiter(rate_limit["requests"], rate_limit["window"])
            self._rate_limiters[limiter_key] = limiter
        return limiter

    def _resolve_rate_limit_identity(self, request_headers: Dict[str, str], request_meta: Optional[Dict[str, str]] = None) -> str:
        request_meta = request_meta or {}
        forwarded_for = str(request_headers.get("X-Forwarded-For", "")).split(",", 1)[0].strip()
        return (
            request_meta.get("client_ip")
            or forwarded_for
            or str(request_headers.get("X-Real-IP", "")).strip()
            or "anonymous"
        )

    def apply_middleware(
        self,
        raw_path: str,
        request_headers: Optional[Dict[str, str]] = None,
        request_meta: Optional[Dict[str, str]] = None,
        method: str = "GET",
    ) -> dict:
        path = normalize_url_path(raw_path)
        request_headers = request_headers or {}
        method = str(method or "GET").upper()
        cookies = parse_cookie_header(_middleware_header(request_headers, "Cookie", ""))
        result = {
            "path": path,
            "headers": list(get_security_headers(self.config)),
            "cookies": [],
            "redirect": None,
            "response": None,
        }

        for rule in parse_middleware_rules(self.project_root):
            if not match_path_pattern(path, str(rule.get("match", "/**"))):
                continue
            allowed_methods = [str(item).upper() for item in rule.get("methods", [])]
            if allowed_methods and method not in allowed_methods:
                continue

            # Modern rule engine for root `middleware.tw`
            path_rule = rule.get("path_rule") or {}
            if path_rule:
                url_lower = path.lower()
                block_match = False
                if path_rule.get("deny_traversal", True) and ".." in path:
                    block_match = True
                if path_rule.get("deny_null_bytes", True) and "%00" in url_lower:
                    block_match = True
                for prefix in _middleware_list(path_rule.get("prefixes")):
                    if url_lower.startswith(str(prefix).lower()):
                        block_match = True
                        break
                if not block_match:
                    for part in _middleware_list(path_rule.get("contains")):
                        if str(part).lower() in url_lower:
                            block_match = True
                            break
                if not block_match:
                    for ext in _middleware_list(path_rule.get("extensions")):
                        if url_lower.endswith(str(ext).lower()):
                            block_match = True
                            break
                if not block_match:
                    for pattern in _middleware_list(path_rule.get("regex")):
                        if re.search(str(pattern), path):
                            block_match = True
                            break
                single_segment_max = int(path_rule.get("single_segment_max", 0) or 0)
                if not block_match and single_segment_max > 0:
                    m = re.match(r"^/([^/?#]+)$", path)
                    if m and len(m.group(1)) > single_segment_max:
                        block_match = True
                if block_match:
                    result["response"] = _build_middleware_response(rule, result, default_status=404, default_text="Not Found")
                    return result

            user_agent_rule = rule.get("user_agent") or {}
            if user_agent_rule:
                ua = _middleware_header(request_headers, "User-Agent", "")
                ua_lower = ua.lower()
                allow_patterns = [item.lower() for item in _middleware_list(user_agent_rule.get("allow"))]
                block_patterns = [item.lower() for item in _middleware_list(user_agent_rule.get("block"))]
                exempt = bool(ua and any(pattern in ua_lower for pattern in allow_patterns))
                blocked = (not ua and bool(user_agent_rule.get("empty_is_blocked"))) or (
                    (not exempt) and any(pattern in ua_lower for pattern in block_patterns)
                )
                if blocked:
                    result["response"] = _build_middleware_response(rule, result, default_status=403, default_text="Forbidden")
                    return result

            origin_rule = rule.get("origin") or {}
            if origin_rule:
                allowed = {str(item) for item in _middleware_list(origin_rule.get("allow"))}
                origin = _middleware_header(request_headers, "Origin", "")
                referer_origin = _middleware_referer_origin(_middleware_header(request_headers, "Referer", ""))
                require_origin = bool(origin_rule.get("require"))
                allow_referer = bool(origin_rule.get("allow_referer", True))
                is_allowed = False
                if origin and origin in allowed:
                    is_allowed = True
                elif allow_referer and referer_origin and referer_origin in allowed:
                    is_allowed = True
                elif not origin and not referer_origin and not require_origin:
                    is_allowed = True
                if allowed and not is_allowed:
                    result["response"] = _build_middleware_response(rule, result, default_status=403, default_text="Access Denied")
                    return result

            auth_rule = rule.get("auth_rule") or {}
            if auth_rule:
                cookie_name = str(auth_rule.get("cookie") or "").strip()
                if cookie_name:
                    token = cookies.get(cookie_name, "")
                    if not token and bool(auth_rule.get("required", True)):
                        result["response"] = _build_middleware_response(rule, result, default_status=401, default_text="Unauthorized")
                        return result
                    if token:
                        secret = str(auth_rule.get("jwt_secret") or "")
                        secret_env = str(auth_rule.get("jwt_secret_env") or "")
                        if secret_env:
                            secret = os.environ.get(secret_env, secret)
                        if secret and not _verify_hs256_jwt(token, secret):
                            result["response"] = _build_middleware_response(rule, result, default_status=401, default_text="Invalid token")
                            return result

            auth = rule.get("auth")
            if auth and not cookies.get(auth["cookie"]):
                result["redirect"] = auth["redirect"]
                return result
            limiter = self._get_rate_limiter(rule)
            if limiter is not None:
                identity = self._resolve_rate_limit_identity(request_headers, request_meta=request_meta)
                if str(rule["rate_limit"].get("identity", "ip")).lower() == "path":
                    bucket_segments = max(1, int(rule["rate_limit"].get("bucket_segments", 2) or 2))
                    bucket = "/".join(path.split("/")[: bucket_segments + 1]) or "/"
                    identity = f"{identity}::{bucket}"
                if not limiter.allow(f"{rule.get('match', '/**')}::{identity}"):
                    result["response"] = _build_middleware_response(
                        rule,
                        result,
                        default_status=429,
                        default_text="Too Many Requests",
                        extra_headers=[("Retry-After", str(int(rule["rate_limit"]["window"])))],
                    )
                    return result
            deny = rule.get("deny")
            if deny:
                body = str(deny.get("body", "Forbidden") or "Forbidden").encode("utf-8")
                result["response"] = {
                    "status": int(deny.get("status", 403) or 403),
                    "content_type": "text/plain; charset=utf-8",
                    "body": body,
                    "headers": list(result["headers"]),
                    "cookies": list(result["cookies"]),
                }
                return result
            if rule.get("response") and not any(
                rule.get(key)
                for key in ["user_agent", "origin", "path_rule", "auth_rule", "rate_limit", "deny", "redirect", "rewrite", "auth"]
            ):
                result["response"] = _build_middleware_response(rule, result, default_status=403, default_text="Forbidden")
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
        for route in discover_twm_api_handlers():
            if strip_trailing_slash(route["route"]) == path:
                return route
        return None

    def execute_api_route(self, api_route: dict, method: str, url_path: str, headers: Dict[str, str], body: object) -> dict:
        if api_route.get("lang") == "twm":
            return execute_twm_api_handler(api_route["path"], method, url_path, headers, body)
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
        context["generate_csrf_token"] = lambda: generate_csrf_token(context["request"])
        context["verify_csrf_token"] = lambda token, max_age=7200: verify_csrf_token(token, context["request"], max_age=max_age)

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

        context = compiler.build_page_context(
            page_info,
            page_ast,
            tw_path,
            item=match.item,
            route_path=match.route_path,
            request_params=match.params,
        )
        hook_state = self.extensions.emit(
            "beforeRoute",
            match=match,
            page_info=page_info,
            page_ast=page_ast,
            context=context,
            dev_mode=dev_mode,
        )
        context = hook_state.get("context", context)

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

        if self.modular_pipeline:
            artifacts = compiler.compile_file_pipeline(
                tw_path,
                context=context,
                css_href=css_url,
                route_path=match.route_path,
            )
            rendered = artifacts.html or ""
            program = artifacts.program
            redirect_to = None
            if program is not None:
                redirect_to = program.meta.redirect_to or getattr(getattr(program, "legacy_page", None), "redirect_to", None)
                rewrite_to = program.meta.rewrite_to or getattr(getattr(program, "legacy_page", None), "rewrite_to", None)
                if rewrite_to:
                    rewritten_path = compiler.interpolate(rewrite_to, context)
                    rewritten_match = self.resolve_route(rewritten_path)
                    if rewritten_match:
                        rewritten_match = RouteMatch(
                            page_info=rewritten_match.page_info,
                            params=rewritten_match.params,
                            item=rewritten_match.item,
                            route_path=match.route_path,
                        )
                        return self.compile_match_response(rewritten_match, dev_mode=dev_mode, depth=depth + 1)
            status = 302 if redirect_to else 200
        else:
            rendered = compiler.render_html(page_ast, context, css_url)
            redirect_to = page_ast.redirect_to
            status = 302 if redirect_to else 200
        headers = []
        if redirect_to:
            headers.append(("Location", compiler.interpolate(redirect_to, context)))

        if dev_mode:
            rendered = inject_dev_client(rendered)
        response = {"html": rendered, "status": status, "headers": headers}
        hook_state = self.extensions.emit(
            "afterRoute",
            match=match,
            page_info=page_info,
            page_ast=page_ast,
            context=context,
            response=response,
            dev_mode=dev_mode,
        )
        return hook_state.get("response", response)

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
        except (ValueError, TypeError):
            configured = None
        if configured is None:
            try:
                configured = float(state.project.config.get("watch_interval", state.project.config.get("watchInterval", interval)))
            except (ValueError, TypeError):
                configured = None
        self.interval = max(0.2, min(2.0, configured if configured is not None else interval))
        # How often to rescan the full file list (for new/deleted files).
        # Default is fairly aggressive to reduce "new file not detected" latency.
        rescan_ticks = None
        try:
            rescan_ticks = int(os.environ.get("TW_WATCH_RESCAN_TICKS", "") or "")
        except (ValueError, TypeError):
            rescan_ticks = None
        if rescan_ticks is None:
            try:
                rescan_ticks = int(state.project.config.get("watch_rescan_ticks", state.project.config.get("watchRescanTicks", 2)))
            except (ValueError, TypeError):
                rescan_ticks = None
        self.rescan_ticks = max(1, int(rescan_ticks if rescan_ticks is not None else 2))

        self._tick = 0
        self._files = []
        self._stats = {}
        self.backend = str(os.environ.get("TW_WATCH_BACKEND", "auto") or "auto").strip().lower()
        self._inotify_fd: Optional[int] = None
        self._wd_to_dir: Dict[int, str] = {}
        self._debounce_s = max(0.05, float(os.environ.get("TW_WATCH_DEBOUNCE", "0.15") or 0.15))
        self._refresh_file_list()

    def _refresh_file_list(self):
        self._files = self.state.project.list_source_files()
        self._stats = {}
        for path in self._files:
            try:
                st = os.stat(path)
                self._stats[path] = (st.st_mtime_ns, st.st_size)
            except OSError:
                self._stats[path] = None

    def _can_use_inotify(self) -> bool:
        if self.backend == "poll":
            return False
        if self.backend == "inotify":
            return True
        # auto
        return sys.platform.startswith("linux")

    def _inotify_setup(self) -> bool:
        if not self._can_use_inotify():
            return False
        if self._inotify_fd is not None:
            return True
        try:
            libc = ctypes.CDLL("libc.so.6", use_errno=True)
        except OSError:
            return False

        inotify_init1 = getattr(libc, "inotify_init1", None)
        inotify_add_watch = getattr(libc, "inotify_add_watch", None)
        if inotify_init1 is None or inotify_add_watch is None:
            return False

        # Flags: IN_NONBLOCK (0x800) | IN_CLOEXEC (0x80000)
        fd = int(inotify_init1(0x800 | 0x80000))
        if fd < 0:
            return False
        self._inotify_fd = fd

        # NOTE: We watch directories (not individual files). For new directories,
        # we also add a watch dynamically when created.
        try:
            self._inotify_refresh_watches(libc)
        except Exception:
            logger.exception("Failed to setup inotify watches, falling back to polling")
            try:
                os.close(fd)
            except OSError:
                pass
            self._inotify_fd = None
            self._wd_to_dir = {}
            return False
        return True

    def _inotify_refresh_watches(self, libc):
        inotify_add_watch = libc.inotify_add_watch
        inotify_add_watch.argtypes = [ctypes.c_int, ctypes.c_char_p, ctypes.c_uint32]
        inotify_add_watch.restype = ctypes.c_int

        # Watch events: create/delete/move/modify/attrib on dirs and files
        mask = (
            0x00000100  # IN_CREATE
            | 0x00000200  # IN_DELETE
            | 0x00000002  # IN_MODIFY
            | 0x00000004  # IN_ATTRIB
            | 0x00000040  # IN_MOVED_FROM
            | 0x00000080  # IN_MOVED_TO
            | 0x00000400  # IN_DELETE_SELF
            | 0x00000800  # IN_MOVE_SELF
        )

        # Clear and rebuild watch list (simple and robust).
        self._wd_to_dir = {}
        roots = [self.state.project.project_root, os.path.join(self.state.project.project_root, "[home]")]
        for root in roots:
            if not root or not os.path.isdir(root):
                continue
            for dirpath, dirnames, _ in os.walk(root):
                # skip hidden caches inside project (don't waste watches)
                dirnames[:] = [d for d in dirnames if d not in {".tw", "dist", "__pycache__", ".pytest_cache"}]
                wd = int(inotify_add_watch(self._inotify_fd, dirpath.encode("utf-8"), mask))
                if wd >= 0:
                    self._wd_to_dir[wd] = dirpath

    def _inotify_read_events(self) -> List[tuple]:
        """Returns list of (mask, name, watched_dir)."""
        assert self._inotify_fd is not None
        try:
            data = os.read(self._inotify_fd, 65536)
        except BlockingIOError:
            return []
        except OSError:
            logger.exception("inotify read failed")
            return []

        events = []
        off = 0
        # struct inotify_event { int wd; uint32_t mask; uint32_t cookie; uint32_t len; char name[]; }
        while off + 16 <= len(data):
            wd, mask, _cookie, name_len = struct.unpack_from("iIII", data, off)
            off += 16
            name = b""
            if name_len:
                name = data[off : off + name_len].split(b"\x00", 1)[0]
                off += name_len
            watched_dir = self._wd_to_dir.get(int(wd), "")
            events.append((int(mask), name.decode("utf-8", errors="replace"), watched_dir))
        return events


        # Prefer inotify on Linux for better latency and battery usage.
        if self._inotify_setup():
            log("👀 File watcher: inotify mode")
            try:
                libc = ctypes.CDLL("libc.so.6", use_errno=True)
            except OSError:
                libc = None
            last_change = 0.0
            while not self.state.stop_event.is_set():
                fd = self._inotify_fd
                if fd is None:
                    break
                rlist, _, _ = select.select([fd], [], [], 0.5)
                if not rlist:
                    continue
                events = self._inotify_read_events()
                if not events:
                    continue
                changed = True

                # If new dirs created, refresh watches (simple, avoids edge cases).
                if libc is not None:
                    for mask, name, watched_dir in events:
                        # IN_ISDIR (0x40000000) + IN_CREATE
                        if (mask & 0x40000000) and (mask & 0x00000100):
                            try:
                                self._inotify_refresh_watches(libc)
                            except Exception:
                                logger.exception("Failed to refresh inotify watches")
                            break

                now = time.monotonic()
                if changed:
                    # Debounce to avoid bumping multiple times during a save burst.
                    if (now - last_change) < self._debounce_s:
                        continue
                    last_change = now
                    self._refresh_file_list()
                    self.state.project.invalidate()
                    self.state.bump()

            if self._inotify_fd is not None:
                try:
                    os.close(self._inotify_fd)
                except OSError:
                    pass
                self._inotify_fd = None
            return

        # Polling fallback (portable)
        log("👀 File watcher: polling mode")
    def run(self):
        while not self.state.stop_event.is_set():
            time.sleep(self.interval)

            changed = False
            for path in list(self._files):
                try:
                    st = os.stat(path)
                    sig = (st.st_mtime_ns, st.st_size)
                except OSError:
                    sig = None
                if self._stats.get(path) != sig:
                    changed = True
                    break

            # Periodically rescan to detect new files / deletions (low overhead)
            if not changed and (self._tick % self.rescan_ticks == 0):
                new_files = self.state.project.list_source_files()
                if set(new_files) != set(self._files):
                    changed = True

            if changed:
                self._refresh_file_list()
                with self.state.project._lock:
                    self.state.project.invalidate()
                self.state.bump()


def make_dev_handler(state: TWDevState):
    class TWDevHandler(http.server.BaseHTTPRequestHandler):
        server_version = "TWDevServer/1.0"

        def log_message(self, fmt, *args):
            log(f"[dev] {self.address_string()} - {fmt % args}")

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
            # ── Modern request middleware hook (extensions) ───────────────
            # Allows project code to intercept/block/redirect/rewrite before TW middleware/api/routes.
            hook_state = state.project.extensions.emit(
                "beforeRequest",
                method=method,
                raw_path=self.path,
                url_path=path,
                request_headers=request_headers,
                request_meta={"client_ip": self.client_address[0] if self.client_address else ""},
                dev_mode=True,
            )
            if hook_state.get("response"):
                response = hook_state["response"]
                self.respond_bytes(
                    response["status"],
                    response["body"],
                    response["content_type"],
                    headers=response.get("headers", []),
                    cookies=response.get("cookies", []),
                )
                return
            if hook_state.get("redirect"):
                location = str(hook_state["redirect"])
                self.respond_bytes(
                    302,
                    b"",
                    "text/plain; charset=utf-8",
                    headers=[("Location", location)] + list(hook_state.get("headers", [])),
                    cookies=list(hook_state.get("cookies", [])),
                )
                return
            if hook_state.get("rewrite"):
                path = normalize_url_path(str(hook_state["rewrite"]))
            request_headers = hook_state.get("request_headers", request_headers)
            middleware = state.project.apply_middleware(
                self.path,
                request_headers,
                request_meta={"client_ip": self.client_address[0] if self.client_address else ""},
                method=method,
            )
            if middleware.get("response"):
                response = middleware["response"]
                self.respond_bytes(
                    response["status"],
                    response["body"],
                    response["content_type"],
                    headers=response.get("headers", []),
                    cookies=response.get("cookies", []),
                )
                return
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
            with state.project._lock:
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
                        logger.exception("Unhandled API route error (dev): %s %s -> %s", method, self.path, api_route)
                        body = render_error_html("API route error", str(err), 500)
                        self.respond_bytes(500, body, "text/html; charset=utf-8", headers=middleware.get("headers", []), cookies=middleware.get("cookies", []))
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
                    except Exception as err:
                        logger.exception("Failed to compile custom 500 page (dev)")
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
                self.send_header(
                    "Set-Cookie",
                    render_cookie_header(
                        cookie_name,
                        cookie_value,
                        config=state.project.config,
                        request_headers={key: value for key, value in self.headers.items()},
                        server_port=self.server.server_address[1],
                    ),
                )
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
            f"Could not bind to port {port} ({err}). Is the port already in use? "
            f"Try: `tw dev --port {port + 1}` or choose a free port."
        ) from err

    log(f"TW dev server running at http://{host}:{port}")
    log("Source workflow active: edit `.tw`, `.tss`, `.ts`; the browser will auto-reload.")

    try:
        server.serve_forever()
    except KeyboardInterrupt:
        log("\nStopping dev server...")
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
            log(f"[preview] {self.address_string()} - {fmt % args}")

        def do_GET(self):
            path = normalize_url_path(self.path)
            for candidate in build_preview_candidates(output_dir, path):
                candidate = os.path.abspath(candidate)
                if not is_path_within(output_dir, candidate):
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
            if (
                (
                    content_type.startswith("text/html")
                    or content_type.startswith("text/css")
                    or "javascript" in content_type
                )
                and "charset=" not in content_type.lower()
            ):
                content_type = f"{content_type}; charset=utf-8"
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
        raise RuntimeError(f"Preview output missing: {output_dir}. Run `tw build` or `tw export` first.")

    handler = make_preview_handler(output_dir)
    server = ThreadedTCPServer((host, port), handler)
    log(f"TW preview server running at http://{host}:{port}")
    log(f"Serving static output from: {output_dir}")
    try:
        server.serve_forever()
    except KeyboardInterrupt:
        log("\nStopping preview server...")
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
        log("  ⚠️  TypeScript files found, but `tsc` was not found. Skipping TS compilation.", level="warning")
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
                    "engines": {
                        "node": ">=18",
                    },
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
                    "dependencies": {},
                    "devDependencies": {},
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


def write_hidden_cache_files(dependency_map: Dict[str, List[str]], metadata_map: Optional[Dict[str, dict]] = None):
    os.makedirs(compiler.CACHE_DIR, exist_ok=True)
    os.makedirs(compiler.MANIFEST_DIR, exist_ok=True)
    os.makedirs(compiler.COMPILER_DIR, exist_ok=True)

    hash_db = {}
    for page_key, dependencies in dependency_map.items():
        hash_db[page_key] = {
            "signature": compiler.compute_dependency_signature(dependencies),
            "dependencies": dependencies,
            "metadata": dict((metadata_map or {}).get(page_key) or {}),
        }

    with open(compiler.HASH_DB_FILE, "w", encoding="utf-8") as f:
        json.dump(hash_db, f, indent=2, sort_keys=True)


def write_text_file(path: str, content: str):
    os.makedirs(os.path.dirname(path), exist_ok=True)
    with open(path, "w", encoding="utf-8") as f:
        f.write(content)


def route_records_for_build() -> List[dict]:
    records = []
    config = compiler.load_config()
    pipeline_name = "modular" if use_modular_pipeline(config) else "legacy"
    for page in compiler.discover_pages():
        page_ast = compiler.load_page_ast_from_file(page["path"])
        if page["type"] == "static":
            route = route_from_static_page(page)
            metadata = compiler.collect_page_metadata(page, page_ast=page_ast, route_path=route, pipeline=pipeline_name)
            records.append({
                "route": route,
                "type": "page",
                "render": page_ast.render_mode,
                "revalidate": page_ast.revalidate,
                "source": compiler.safe_relpath(page["path"], compiler.PROJECT_ROOT),
                "title": page_ast.title,
                "layouts": metadata["layouts"],
                "components": metadata["components"],
                "pipeline": metadata["pipeline"],
            })
            continue
        for item in compiler.load_dynamic_items(page["path"]):
            if not isinstance(item, dict):
                continue
            route = route_from_dynamic_page(page, item)
            metadata = compiler.collect_page_metadata(page, page_ast=page_ast, route_path=route, pipeline=pipeline_name, item=item)
            records.append({
                "route": route,
                "type": "page",
                "render": page_ast.render_mode,
                "revalidate": page_ast.revalidate,
                "source": compiler.safe_relpath(page["path"], compiler.PROJECT_ROOT),
                "title": page_ast.title,
                "layouts": metadata["layouts"],
                "components": metadata["components"],
                "pipeline": metadata["pipeline"],
                "route_kind": metadata["route_kind"],
            })
    return sorted(records, key=lambda item: item["route"])


def write_route_artifacts(output_dir: str):
    config = compiler.load_config()
    site_url = str(config.get("site_url", "") or config.get("siteUrl", "") or "").rstrip("/")
    routes = [item for item in route_records_for_build() if item["route"] not in {"/404", "/500"}]
    # Route collision detection (warn by default; can be escalated by callers).
    # Collision = same final route emitted by multiple source pages/items.
    collisions = {}
    for entry in routes:
        route = entry.get("route") or "/"
        src = entry.get("source") or ""
        collisions.setdefault(route, []).append(src)
    collisions = {r: srcs for r, srcs in collisions.items() if len(set(srcs)) > 1}
    if collisions:
        for route, srcs in sorted(collisions.items()):
            sources = ", ".join(sorted(set(srcs)))
            log(f"  ⚠️  Route collision: {route} <- {sources}", level="warning")
    write_text_file(os.path.join(output_dir, "_tw", "route-manifest.json"), json.dumps(routes, indent=2, ensure_ascii=False) + "\n")

    api_manifest = []
    for api in discover_api_routes():
        if api.get("lang") == "twm":
            with open(api["path"], "r", encoding="utf-8") as handle:
                funcs = parse_twm_functions(handle.read())
            method_names = {"get", "post", "put", "patch", "delete", "options"}
            methods = sorted({fn["name"].upper() for fn in funcs if fn["name"].lower() in method_names})
            if not methods and any(fn["name"].lower() == "handler" for fn in funcs):
                methods = ["ANY"]
        else:
            methods = sorted(parse_api_route_file(api["path"]).keys())
        api_manifest.append({
            "route": api["route"],
            "methods": methods,
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
            log(f"  ⚠️  Search index build skipped: {err}", level="warning")
    return len(collisions)


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
    except ImportError:
        brotli = None

    compress_exts = {".html", ".css", ".js", ".json", ".xml", ".txt", ".svg"}
    brotli_warned = False
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
            elif not brotli_warned:
                log("⚠️  Brotli dependency not installed; generated gzip precompression only.", level="warning")
                brotli_warned = True


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


def build_hidden_site(project_root: str, output_dir: str, force: bool = False, workers: Optional[int] = None, minify: bool = True, strict: bool = False) -> BuildSummary:
    project_root = os.path.abspath(project_root)
    output_dir = os.path.abspath(output_dir)
    workers = workers or compiler.DEFAULT_WORKERS

    configure_compiler_paths(project_root)
    invalidate_compiler_caches()
    env = load_project_env(project_root, "production")
    ensure_project_metadata(project_root)
    ensure_deploy_support_files(project_root)
    config = compiler.load_config()
    modular_pipeline = use_modular_pipeline(config)
    extensions = ExtensionManager(project_root, config, env).refresh()
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
            page_metadata_map = {}
            pages_to_build = []
            skipped = 0
            errors = 0
            built = 0
            warnings = 0

            options = compiler.BuildOptions(force=force, workers=workers)
            shared_dependencies = extensions.dependency_paths()
            if extensions.errors:
                for message in extensions.errors:
                    log(f"  ❌ Extension error: {message}", level="error")
                errors += len(extensions.errors)
            extensions.emit(
                "beforeBuild",
                output_dir=output_dir,
                force=force,
                workers=workers,
                minify=minify,
            )

            for page_info in pages:
                try:
                    page_ast = compiler.load_page_ast_from_file(page_info["path"])
                    analysis_context = compiler.build_page_context(page_info, page_ast, page_info["path"], route_path=compiler.route_path_from_page_info(page_info))
                    if page_info["type"] == "dynamic":
                        items = compiler.load_dynamic_items(page_info["path"])
                        sample_item = next((item for item in items if isinstance(item, dict)), None)
                        if sample_item:
                            analysis_context = compiler.build_page_context(
                                page_info,
                                page_ast,
                                page_info["path"],
                                item=sample_item,
                                route_path=compiler.route_path_from_page_info(page_info, item=sample_item),
                            )
                    if modular_pipeline:
                        analysis_route = analysis_context.get("_tw_route", "/")
                        artifacts = compiler.compile_file_pipeline(
                            page_info["path"],
                            context=analysis_context,
                            css_href=css_url,
                            route_path=analysis_route,
                        )
                        diagnostics = [compiler.Diagnostic(**item) for item in artifacts.diagnostics]
                    else:
                        diagnostics = compiler.analyze_page_semantics(page_ast, analysis_context, page_info["path"], page_info=page_info)
                    for diagnostic in diagnostics:
                        if diagnostic.severity == "warning":
                            warnings += 1
                            compiler.print_diagnostic(diagnostic)
                    dependencies = compiler.collect_page_dependencies(page_info["path"]) + shared_dependencies
                    dependencies = sorted(set(dependencies))
                    dependency_map[compiler.page_cache_key(page_info)] = dependencies
                    page_metadata = compiler.collect_page_metadata(
                        page_info,
                        page_ast=page_ast,
                        route_path=analysis_context.get("_tw_route", "/"),
                        pipeline="modular" if modular_pipeline else "legacy",
                    )
                    page_metadata["dependency_count"] = len(dependencies)
                    page_metadata_map[compiler.page_cache_key(page_info)] = page_metadata
                    needs_build, reason = compiler.should_rebuild_page(page_info, dependencies, manifest, options)
                    if needs_build:
                        pages_to_build.append(page_info)
                    else:
                        skipped += 1
                        log(f"  ⏭️  {compiler.safe_relpath(page_info['path'], compiler.PROJECT_ROOT)} ({reason})")
                except Exception as err:
                    errors += 1
                    compiler.print_compiler_error(page_info, err)

            if pages_to_build:
                with compiler.concurrent.futures.ThreadPoolExecutor(max_workers=workers) as executor:
                    future_map = {
                        executor.submit(build_page_job_modular if modular_pipeline else compiler.build_page_job, page_info, css_url): page_info
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
                                metadata=page_metadata_map.get(compiler.page_cache_key(page_info)),
                            )
                            for out_path in outputs:
                                rel_out = os.path.relpath(out_path, output_dir)
                                log(f"  ✅ {rel_out}")
                                built += 1
                        except Exception as err:
                            errors += 1
                            compiler.print_compiler_error(page_info, err)

            try:
                ts_outputs = compile_typescript_sources(project_root, output_dir)
                if ts_outputs:
                    log(f"  ✅ TypeScript emitted: {len(ts_outputs)} file(s)")
            except Exception as err:
                errors += 1
                log(f"  ❌ {err}", level="error")

            sync_runtime_chunks_to_output()
            write_hidden_cache_files(dependency_map, page_metadata_map)
            compiler.save_build_manifest(manifest)
            compiler.save_dependency_graph({"forward": dependency_map, "metadata": page_metadata_map})
            route_collisions = 0
            try:
                route_collisions = write_route_artifacts(output_dir)
            except Exception as err:
                # Route artifact generation should not take down builds silently.
                errors += 1
                log(f"  ❌ Failed to write route artifacts: {err}", level="error")
            if route_collisions:
                if strict:
                    errors += route_collisions
                    log(f"  ❌ Route collisions treated as errors (--strict): {route_collisions}", level="error")
                else:
                    warnings += route_collisions
                    log(f"  ⚠️  Route collisions: {route_collisions}", level="warning")
            precompress_output(output_dir)
            extensions.emit(
                "afterBuild",
                output_dir=output_dir,
                summary={
                    "built": built,
                    "skipped": skipped,
                    "removed": removed,
                    "errors": errors,
                    "warnings": warnings,
                },
            )
            if warnings:
                log(f"  ⚠️  Semantic warnings: {warnings}", level="warning")

        return BuildSummary(
            built=built,
            skipped=skipped,
            removed=removed,
            errors=errors,
            warnings=warnings,
            route_collisions=route_collisions,
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
        "modular_pipeline": project.modular_pipeline,
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
        raise RuntimeError("`vercel` CLI is not installed. Please install the Vercel CLI first.")

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
        raise RuntimeError("`wrangler` CLI is not installed. Please install Cloudflare Wrangler first.")

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
        log("`netlify` CLI not found. Static output and `netlify.toml` are ready.", level="warning")
        return
    subprocess.run([netlify_bin, "deploy", "--dir", output_dir, "--prod"], check=True)


def deploy_with_docker(project_root: str, production: bool):
    docker_bin = shutil.which("docker")
    if not docker_bin:
        log("`docker` CLI not found. `Dockerfile` is ready.", level="warning")
        return
    tag = os.path.basename(os.path.abspath(project_root)).lower().replace("_", "-") + (":prod" if production else ":latest")
    subprocess.run([docker_bin, "build", "-t", tag, project_root], check=True)


def run_deploy(project_root: str, output_dir: str, provider: str, production: bool, dry_run: bool = False):
    ensure_deploy_support_files(project_root)
    checks = doctor_project(project_root)
    blocking_failures = [check for check in checks if not check["ok"] and check["name"] in {"tw.config", "[home]", "Route discovery"}]
    if blocking_failures:
        raise RuntimeError("Project checks failed. Fix the config or route structure first.")
    summary = build_hidden_site(project_root, output_dir, force=True, minify=production)
    if summary.errors:
        raise RuntimeError("Build failed with errors. Deployment was aborted.")
    if dry_run:
        log("✔ Deploy dry-run: checks + build OK (no upload performed).")
        return

    if provider == "local":
        log(f"Local deploy package ready: {summary.output_dir}")
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
        log("GitHub Pages workflow file is ready. Deployment will run after you push the repo.")
        return

    if provider == "docker":
        deploy_with_docker(project_root, production)
        return

    raise RuntimeError(f"Unsupported provider: {provider}")


def parse_args():
    parser = argparse.ArgumentParser(description="TW framework CLI")
    parser.add_argument("--project-root", default=DEFAULT_PROJECT_ROOT, help="TW project root")

    subparsers = parser.add_subparsers(dest="command", required=True)

    dev_parser = subparsers.add_parser("dev", help="Run the in-memory dev server")
    dev_parser.add_argument("--host", default=DEFAULT_DEV_HOST)
    dev_parser.add_argument("--port", type=int, default=DEFAULT_DEV_PORT)

    build_parser = subparsers.add_parser("build", help="Generate a hidden production build")
    build_parser.add_argument("--out-dir", default=DEFAULT_INTERNAL_OUTPUT)
    build_parser.add_argument("--force", action="store_true")
    build_parser.add_argument("--workers", type=int, default=compiler.DEFAULT_WORKERS)

    deploy_parser = subparsers.add_parser("deploy", help="Build and deploy to a hosting provider")
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
        log(
            f"\nTW build complete — {summary.built} generated, "
            f"{summary.skipped} skipped, {summary.removed} removed, {summary.errors} errors"
        )
        log(f"Internal output: {summary.output_dir}")
        return

    if args.command == "deploy":
        run_deploy(
            project_root=args.project_root,
            output_dir=args.out_dir,
            provider=args.provider,
            production=args.prod,
        )
        log("Deploy complete.")
        return


if __name__ == "__main__":
    main()
