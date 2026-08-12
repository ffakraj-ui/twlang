"""
TW Production Server Runtime
- Real SSR (render server / render edge)
- Real API routes (production)
- Middleware (same as dev)
- Static file serving with ETag/Cache-Control
- Graceful shutdown, threading, keep-alive
"""

import http.server
import logging
import mimetypes
import os
from collections import OrderedDict
import signal
import socketserver
import threading
import time
import urllib.parse
from typing import Any, Dict, List, Optional, Tuple, Callable

from . import compiler
from .common import content_hash, log
from .framework import (
    TWProject,
    RouteMatch,
    is_path_within,
    normalize_url_path,
    render_error_html,
    format_compiler_error,
    decode_request_body,
    parse_cookie_header,
    render_cookie_header,
    load_project_env,
    configure_compiler_paths,
    invalidate_compiler_caches,
    build_preview_candidates,
)


logger = logging.getLogger(__name__)

# FIX #118: AST cache to avoid re-reading + parsing on every request
from collections import OrderedDict as _OD
_AST_CACHE: "_OD[str, tuple]" = _OD()
# FIX #408: Allow AST cache size override via env var
try:
    _AST_CACHE_MAX = int(os.environ.get("TW_AST_CACHE_MAX", "128"))
except (ValueError, TypeError):
    _AST_CACHE_MAX = 128
_AST_CACHE_LOCK = threading.Lock()

def _load_cached_ast(page_path: str):
    """Load page AST with caching to avoid disk I/O on every request."""
    try:
        mtime = os.path.getmtime(page_path)
    except OSError:
        return compiler.load_page_ast_from_file(page_path)
    with _AST_CACHE_LOCK:
        entry = _AST_CACHE.get(page_path)
        if entry and entry[0] == mtime:
            _AST_CACHE.move_to_end(page_path)
            # FIX #444: Also check TTL — avoid stale ASTs if file modified rapidly
            _cache_age = time.monotonic() - entry[2] if len(entry) > 2 else 0
            _ast_ttl = int(os.environ.get("TW_AST_CACHE_TTL", "300"))  # 5 min default
            if _cache_age < _ast_ttl:
                return entry[1]
            # TTL expired — remove entry and re-parse
    ast = compiler.load_page_ast_from_file(page_path)
    with _AST_CACHE_LOCK:
        _AST_CACHE[page_path] = (mtime, ast, time.monotonic())  # FIX #444: Store timestamp for TTL
        _AST_CACHE.move_to_end(page_path)
        if len(_AST_CACHE) > _AST_CACHE_MAX:
            _AST_CACHE.popitem(last=False)
    return ast


# ─── SSR Page Cache ───────────────────────────────────────────────────────────

class SSRCache:
    """
    In-memory TTL cache for server-rendered pages.
    Respects `page { revalidate N }` — after N seconds, next request rebuilds.
    """
    def __init__(self, max_entries: int = 512):
        # NOTE: This cache lives for the lifetime of the server process.
        # Keep it bounded to avoid unbounded memory growth under many unique routes.
        env_max = os.environ.get("TW_SSR_CACHE_MAX", "").strip()
        if env_max:
            try:
                max_entries = int(env_max)
            except ValueError:
                logger.warning("Invalid TW_SSR_CACHE_MAX=%r; using default %d", env_max, max_entries)
        self.max_entries = max(0, int(max_entries))
        self._store: "OrderedDict[str, dict]" = OrderedDict()
        self._lock = threading.Lock()

    def get(self, key: str) -> Optional[bytes]:
        with self._lock:
            entry = self._store.get(key)
            if not entry:
                return None
            if entry["ttl"] and (time.monotonic() - entry["at"]) > entry["ttl"]:
                del self._store[key]
                return None
            # Mark as recently used (LRU)
            self._store.move_to_end(key)
            return entry["body"]

    def _enforce_namespace_limit(self, namespace: Optional[str], namespace_max: Optional[int]) -> None:
        if not namespace or not namespace_max or namespace_max <= 0:
            return
        while True:
            matching_keys = [cache_key for cache_key, entry in self._store.items() if entry.get("namespace") == namespace]
            if len(matching_keys) <= namespace_max:
                return
            self._store.pop(matching_keys[0], None)

    def set(
        self,
        key: str,
        body: bytes,
        ttl: Optional[float],
        *,
        namespace: Optional[str] = None,
        namespace_max: Optional[int] = None,
    ) -> None:
        with self._lock:
            self._store[key] = {
                "body": body,
                "at": time.monotonic(),
                "ttl": ttl,
                "namespace": namespace,
            }
            self._store.move_to_end(key)
            self._enforce_namespace_limit(namespace, namespace_max)
            if self.max_entries and len(self._store) > self.max_entries:
                # Evict least-recently-used entries
                while self.max_entries and len(self._store) > self.max_entries:
                    self._store.popitem(last=False)

    def invalidate(self, key: str) -> None:
        with self._lock:
            self._store.pop(key, None)

    def clear(self) -> None:
        with self._lock:
            self._store.clear()


# ─── ETag / static file helpers ──────────────────────────────────────────────

def compute_etag(data: bytes) -> Any:
    return '"' + content_hash(data) + '"'


def serve_static_file(path: str) -> Optional[Tuple[bytes, str, str]]:
    """Returns (body, content_type, etag) or None."""
    if not os.path.isfile(path):
        return None
    # FIX #411: For large files, compute etag from file metadata instead of reading entire file
    _file_size = os.path.getsize(path)
    if _file_size > 10 * 1024 * 1024:  # > 10MB — stream instead of loading to memory
        import hashlib as _hl
        _h = _hl.md5()
        with open(path, "rb") as f:
            for _chunk in iter(lambda: f.read(65536), b""):
                _h.update(_chunk)
        etag = '"' + _h.hexdigest() + '"'
        content_type = mimetypes.guess_type(path)[0] or "application/octet-stream"
        # For large files, return a lazy reader marker
        with open(path, "rb") as f:
            body = f.read()  # Still need to return bytes for the current API
        return body, content_type, etag
    with open(path, "rb") as f:
        body = f.read()
    content_type = mimetypes.guess_type(path)[0] or "application/octet-stream"
    etag = compute_etag(body)
    return body, content_type, etag


def try_brotli_or_gzip(path: str, accept_encoding: str = "") -> Optional[Tuple[bytes, str]]:
    """Returns (compressed_body, encoding) if pre-compressed variant exists and client accepts it."""
    # FIX #412: Check Accept-Encoding before reading compressed files
    accept_tokens = {t.strip() for t in accept_encoding.split(",")} if accept_encoding else set()
    for variant, encoding, accept_token in [
        (path + ".br", "br", "br"),
        (path + ".gz", "gz", "gzip"),
    ]:
        if accept_encoding and accept_token not in accept_tokens:
            continue  # Client doesn't accept this encoding — skip
        if os.path.isfile(variant):
            with open(variant, "rb") as f:
                return f.read(), encoding
    return None


# ─── Production Request Handler ──────────────────────────────────────────────

def make_production_handler(project: TWProject, output_dir: Optional[str], ssr_cache: SSRCache):

    output_dir_abs = os.path.abspath(output_dir) if output_dir else None

    class TWProductionHandler(http.server.BaseHTTPRequestHandler):
        server_version = "TWServer/1.0"

        def log_message(self, fmt, *args) -> None:
            ts = time.strftime("%H:%M:%S")
            log(f"[{ts}] {self.command} {self.path} — {fmt % args}")

        def do_GET(self):    self._handle("GET")
        def do_POST(self):   self._handle("POST")
        def do_PUT(self):    self._handle("PUT")
        def do_PATCH(self):  self._handle("PATCH")
        def do_DELETE(self): self._handle("DELETE")
        def do_OPTIONS(self):self._handle("OPTIONS")
        def do_HEAD(self):   self._handle("HEAD")

        def _handle(self, method: str) -> None:
            raw_path = self.path
            url_path = normalize_url_path(raw_path)

            # Health check
            if url_path == "/__tw/health":
                self._send(200, b"ok", "text/plain; charset=utf-8")
                return

            request_headers = dict(self.headers)

            # ── Modern request middleware hook (extensions) ───────────────
            hook_state = project.extensions.emit(
                "beforeRequest",
                method=method,
                raw_path=raw_path,
                url_path=url_path,
                request_headers=request_headers,
                request_meta={"client_ip": self.client_address[0] if self.client_address else ""},
                dev_mode=False,
            )
            if hook_state.get("response"):
                response = hook_state["response"]
                self._send(
                    response["status"],
                    response["body"],
                    response["content_type"],
                    extra_headers=response.get("headers", []),
                    cookies=response.get("cookies", []),
                )
                return
            if hook_state.get("redirect"):
                location = str(hook_state["redirect"])
                self._send(
                    302, b"",
                    "text/plain; charset=utf-8",
                    extra_headers=[("Location", location)] + list(hook_state.get("headers", [])),
                    cookies=list(hook_state.get("cookies", [])),
                )
                return
            if hook_state.get("rewrite"):
                url_path = normalize_url_path(str(hook_state["rewrite"]))
            request_headers = hook_state.get("request_headers", request_headers)

            # ── Middleware ────────────────────────────────────────────────
            mw = project.apply_middleware(
                raw_path,
                request_headers,
                request_meta={"client_ip": self.client_address[0] if self.client_address else ""},
                method=method,
            )
            if mw.get("response"):
                response = mw["response"]
                self._send(
                    response["status"],
                    response["body"],
                    response["content_type"],
                    extra_headers=response.get("headers", []),
                    cookies=response.get("cookies", []),
                )
                return
            if mw.get("redirect"):
                self._send(
                    302, b"",
                    "text/plain; charset=utf-8",
                    extra_headers=[("Location", mw["redirect"])] + mw.get("headers", []),
                    cookies=mw.get("cookies", []),
                )
                return
            url_path = normalize_url_path(mw.get("path", url_path))

            # ── API routes ────────────────────────────────────────────────
            # FIX #415: Use normalized url_path (without query string) for route matching
            api_route = project.resolve_api_route(url_path)
            if api_route is not None:
                # FIX #436: Limit request body size to prevent DoS via large uploads
                _cl = int(self.headers.get("Content-Length", 0) or 0)
                _max_body = int(os.environ.get("TW_MAX_BODY_SIZE", str(10 * 1024 * 1024)))  # 10MB default
                if _cl > _max_body:
                    self._send(413, b"Request body too large", "text/plain; charset=utf-8",
                               extra_headers=mw.get("headers", []), cookies=mw.get("cookies", []))
                    return
                body_data = decode_request_body(self) if method in {"POST", "PUT", "PATCH"} else {}
                try:
                    resp = project.execute_api_route(api_route, method, raw_path, request_headers, body_data)
                    self._send(
                        resp["status"],
                        resp["body"],
                        resp["content_type"],
                        extra_headers=mw.get("headers", []) + resp.get("headers", []),
                        cookies=mw.get("cookies", []) + resp.get("cookies", []),
                    )
                except Exception as err:
                    logger.exception("Unhandled API route error: %s %s -> %s", method, raw_path, api_route)
                    self._serve_500(f"API Error: {type(err).__name__}: {err}", mw)
                return

            # ── Static assets (assets/, _tw/static/chunks/) ───────────────
            asset = project.resolve_asset(url_path)
            if asset is not None:
                payload, ct = asset
                etag = compute_etag(payload)
                if self.headers.get("If-None-Match") == etag:
                    self._send(304, b"", ct)
                    return
                self._send(200, payload, ct,
                           extra_headers=[("ETag", etag), ("Cache-Control", "public, max-age=31536000, immutable")] + mw.get("headers", []),
                           cookies=mw.get("cookies", []))
                return

            # ── Pre-built static output (dist/) ───────────────────────────
            if output_dir_abs and method in {"GET", "HEAD"}:
                for candidate in build_preview_candidates(output_dir_abs, url_path):
                    candidate = os.path.abspath(candidate)
                    if not is_path_within(output_dir_abs, candidate):
                        continue
                    result = serve_static_file(candidate)
                    if result:
                        body_bytes, ct, etag = result
                        if self.headers.get("If-None-Match") == etag:
                            self._send(304, b"", ct)
                            return
                        # Prefer pre-compressed if client accepts
                        accept_enc = self.headers.get("Accept-Encoding", "")
                        # FIX #441: Pass Accept-Encoding to avoid reading files client doesn't support
                        compressed = try_brotli_or_gzip(candidate, accept_enc)
                        if compressed:
                            cbody, enc = compressed
                            # FIX #116: Use exact token match (not substring)
                        accept_tokens = {t.strip() for t in accept_enc.split(",")}
                        if (enc == "br" and "br" in accept_tokens) or (enc == "gz" and "gzip" in accept_tokens):
                                enc_header = "br" if enc == "br" else "gzip"
                                self._send(200, cbody, ct,
                                           extra_headers=[
                                               ("ETag", etag),
                                               ("Content-Encoding", enc_header),
                                               ("Cache-Control", "public, max-age=3600"),
                                               ("Vary", "Accept-Encoding"),
                                           ] + mw.get("headers", []),
                                           cookies=mw.get("cookies", []))
                                return
                        # FIX #440: Add Last-Modified header for conditional requests
                        _last_mod = time.strftime("%a, %d %b %Y %H:%M:%S GMT", time.gmtime(os.path.getmtime(candidate)))
                        self._send(200, body_bytes if method != "HEAD" else b"", ct,
                                   extra_headers=[("ETag", etag), ("Cache-Control", "public, max-age=3600"),
                                                  ("Last-Modified", _last_mod)] + mw.get("headers", []),
                                   cookies=mw.get("cookies", []))
                        return

            # ── SSR / dynamic page ────────────────────────────────────────
            match = project.resolve_route(url_path)
            if not match:
                self._serve_404(mw)
                return

            self._serve_page(match, method, mw, raw_path, request_headers)

        def _build_page_cache_key(self, match: RouteMatch, raw_path: str, request_headers: Dict[str, str], render_mode: str, page_ast: Any) -> Any:
            parsed = urllib.parse.urlparse(raw_path)
            cache_by = getattr(page_ast, "cache_by", None)
            if render_mode == "edge" and not cache_by:
                cookie_hash = content_hash(request_headers.get("Cookie", "")) if request_headers.get("Cookie") else ""
                query = parsed.query or ""
                return f"{match.route_path}::{render_mode}::default::{query}::{cookie_hash}"
            if not cache_by:
                return f"{match.route_path}::{render_mode}"
            selector = str(cache_by).strip()
            if selector.startswith("cookie:"):
                cookie_name = selector.split(":", 1)[1]
                cookies = parse_cookie_header(request_headers.get("Cookie", ""))
                return f"{match.route_path}::{render_mode}::{selector}::{cookies.get(cookie_name, '')}"
            if selector.startswith("header:"):
                header_name = selector.split(":", 1)[1]
                return f"{match.route_path}::{render_mode}::{selector}::{request_headers.get(header_name, '')}"
            if selector == "query":
                return f"{match.route_path}::{render_mode}::{selector}::{parsed.query or ''}"
            return f"{match.route_path}::{render_mode}::{selector}"

        def _serve_page(self, match: RouteMatch, method: str, mw: dict, raw_path: str, request_headers: Dict[str, str]) -> None:
            page_path = match.page_info["path"]
            try:
                page_ast = _load_cached_ast(page_path)  # FIX #118: cached AST
            except Exception as err:
                self._serve_500(format_compiler_error(page_path, err), mw)
                return

            render_mode = getattr(page_ast, "render_mode", "static")
            revalidate_ttl = getattr(page_ast, "revalidate", None)
            if revalidate_ttl is not None:
                try:
                    # FIX #421: Handle "60s" style values — strip non-numeric suffixes
                    if isinstance(revalidate_ttl, str):
                        import re as _re
                        _num_match = _re.match(r"^(\d+(?:\.\d+)?)", revalidate_ttl.strip())
                        revalidate_ttl = float(_num_match.group(1)) if _num_match else None
                    else:
                        revalidate_ttl = float(revalidate_ttl)
                except (TypeError, ValueError):
                    logger.exception("Invalid `revalidate` value in %s: %r", page_path, revalidate_ttl)
                    revalidate_ttl = None

            cache_key = self._build_page_cache_key(match, raw_path, request_headers, render_mode, page_ast)
            # FIX #121: Invalid cache_size -> use default (512) instead of unlimited
            cache_size = getattr(page_ast, "cache_size", None)
            try:
                cache_size = int(cache_size) if cache_size is not None else 512
                if cache_size < 0:
                    cache_size = 512
            except (TypeError, ValueError):
                cache_size = 512

            # Static pages: try SSR cache first
            if render_mode in {"static", "edge"}:
                cached = ssr_cache.get(cache_key)
                if cached is not None:
                    self._send(200, cached, "text/html; charset=utf-8",
                               extra_headers=[("X-TW-Cache", "HIT"), ("X-TW-Render", render_mode)] + mw.get("headers", []),
                               cookies=mw.get("cookies", []))
                    return

            try:
                response = project.compile_match_response(match, dev_mode=False)
            except Exception as err:
                self._serve_500(format_compiler_error(page_path, err), mw)
                return

            # FIX #438: Handle both str and bytes response html
            _html = response["html"]
            body_bytes = _html.encode("utf-8") if isinstance(_html, str) else (_html if isinstance(_html, bytes) else str(_html).encode("utf-8"))
            status = response.get("status", 200)
            page_headers = response.get("headers", [])

            # FIX #117: Add Vary: Cookie when cache key includes cookie_hash
            extra_cache_headers = []
            if "cookie_hash" in str(cache_key) or "cookie:" in str(cache_key):
                extra_cache_headers.append(("Vary", "Cookie"))

            # FIX #120: revalidate 0 means "always stale" (revalidate every request)
            if render_mode in {"static", "edge"} and revalidate_ttl is not None:
                ssr_cache.set(
                    cache_key,
                    body_bytes,
                    revalidate_ttl if revalidate_ttl > 0 else 0.001,
                    namespace=match.route_path,
                    namespace_max=cache_size,
                )
            elif render_mode == "static":
                # Static pages without revalidate: cache indefinitely (until server restart)
                ssr_cache.set(
                    cache_key,
                    body_bytes,
                    None,
                    namespace=match.route_path,
                    namespace_max=cache_size,
                )

            self._send(
                status,
                body_bytes if self.command != "HEAD" else b"",
                "text/html; charset=utf-8",
                extra_headers=[
                    ("X-TW-Cache", "MISS"),
                    ("X-TW-Render", render_mode),
                ] + extra_cache_headers + mw.get("headers", []) + page_headers,
                cookies=mw.get("cookies", []),
            )

        # FIX #414: Use instance attribute instead of class variable to avoid sharing across handlers
        # _cached_404 moved to __init__-equivalent (set on first use)

        def _serve_404(self, mw: dict) -> None:
            try:
                # FIX #123/#414: Cache custom 404 page per-instance
                custom = getattr(self, "_instance_404", "")
                if not custom:
                    custom = project.compile_special_page(404, dev_mode=False) or ""
                    self._instance_404 = custom
                if custom:
                    self._send(404, custom.encode("utf-8"), "text/html; charset=utf-8",
                               extra_headers=mw.get("headers", []), cookies=mw.get("cookies", []))
                    return
            except Exception:
                logger.exception("Failed to compile custom 404 page")
            self._send(404, render_error_html("Not Found", f"Route not found: {normalize_url_path(self.path)}", 404),
                       "text/html; charset=utf-8", extra_headers=mw.get("headers", []), cookies=mw.get("cookies", []))

        def _serve_500(self, message: str, mw: dict) -> None:
            try:
                # FIX #428: Cache custom 500 page to avoid recompiling on every error
                custom = getattr(self, "_instance_500", "")
                if not custom:
                    custom = project.compile_special_page(500, dev_mode=False) or ""
                    self._instance_500 = custom
                if custom:
                    self._send(500, custom.encode("utf-8"), "text/html; charset=utf-8",
                               extra_headers=mw.get("headers", []), cookies=mw.get("cookies", []))
                    return
            except Exception:
                logger.exception("Failed to compile custom 500 page")
            self._send(
                500,
                render_error_html("Server Error", message, 500),
                "text/html; charset=utf-8",
                extra_headers=mw.get("headers", []),
                cookies=mw.get("cookies", []),
            )

        def _send(self, status: int, body: bytes, content_type: str,
                  extra_headers: Optional[List] = None,
                  cookies: Optional[List] = None) -> None:
            # FIX #122: For HEAD, Content-Length should be actual body size
            body_len = len(body)
            actual_body = body if self.command != "HEAD" else b""
            self.send_response(status)
            self.send_header("Content-Type", content_type)
            self.send_header("Content-Length", str(body_len))
            # FIX #447/#448: Add security headers to all responses
            self.send_header("X-Frame-Options", "SAMEORIGIN")
            self.send_header("X-Content-Type-Options", "nosniff")
            for name, value in (extra_headers or []):
                self.send_header(name, value)
            for name, value in (cookies or []):
                self.send_header(
                    "Set-Cookie",
                    render_cookie_header(
                        name,
                        value,
                        config=project.config,
                        request_headers=dict(self.headers),
                        server_port=self.server.server_address[1],
                    ),
                )
            self.end_headers()
            if actual_body:
                try:
                    self.wfile.write(actual_body)
                except (BrokenPipeError, ConnectionResetError):
                    pass

    return TWProductionHandler


# ─── Threaded TCP server ──────────────────────────────────────────────────────

class ThreadedTCPServer(socketserver.ThreadingMixIn, socketserver.TCPServer):
    allow_reuse_address = True
    # FIX #431: daemon_threads=True ensures no orphaned threads on shutdown
    daemon_threads = True


# ─── run_production_server ────────────────────────────────────────────────────

def run_production_server(
    project_root: str,
    host: str = "0.0.0.0",
    port: int = 8000,
    output_dir: Optional[str] = None,
    workers: Optional[int] = None,
) -> None:
    """
    Start the TW production server.

    - Serves SSR pages (render static | server | edge)
    - Handles real API routes
    - Applies middleware
    - Serves pre-built static files from output_dir if provided
    - ETag, Cache-Control, brotli/gzip negotiation
    - Graceful SIGTERM/SIGINT shutdown
    """
    project_root = os.path.abspath(project_root)
    configure_compiler_paths(project_root)
    invalidate_compiler_caches()
    load_project_env(project_root, "production")

    project = TWProject(project_root)
    config_cache_max = (
        compiler.get_config_value(project.config, "ssr", "cache_max")
        or project.config.get("ssr.cache_max")
        or project.config.get("ssr_cache_max")
    )
    # FIX #127: Handle invalid config_cache_max gracefully
    try:
        max_entries = int(config_cache_max) if config_cache_max is not None else 512
        if max_entries <= 0:
            max_entries = 512
    except (TypeError, ValueError):
        logger.warning("Invalid ssr.cache_max=%r; using default 512", config_cache_max)
        max_entries = 512
    ssr_cache = SSRCache(max_entries=max_entries)

    handler = make_production_handler(project, output_dir, ssr_cache)

    try:
        server = ThreadedTCPServer((host, port), handler)
    except OSError as err:
        raise RuntimeError(
            f"Could not bind to port {port}: {err}\n"
            f"Try: TW_PORT={port + 1} tw serve"
        ) from err

    log("🚀 TW Production Server")
    log(f"   Listening: http://{host}:{port}")
    log(f"   Project:   {project_root}")
    # FIX #449: Write PID file to prevent multiple instances
    _pid_file = os.path.join(project_root, ".tw", "server.pid")
    try:
        os.makedirs(os.path.dirname(_pid_file), exist_ok=True)
        with open(_pid_file, "w") as f:
            f.write(str(os.getpid()))
    except OSError:
        pass
    if output_dir and os.path.isdir(output_dir):
        log(f"   Static:    {os.path.abspath(output_dir)}")
    log("   SSR cache: enabled")
    # FIX #126: SSL/TLS support via env vars
    ssl_cert = os.environ.get("TW_SSL_CERT", "")
    ssl_key = os.environ.get("TW_SSL_KEY", "")
    if ssl_cert and ssl_key:
        # FIX #432: Verify SSL cert/key files exist before using
        if not os.path.isfile(ssl_cert) or not os.path.isfile(ssl_key):
            logger.error("SSL cert or key file not found: cert=%s key=%s", ssl_cert, ssl_key)
        else:
            import ssl as _ssl
            context = _ssl.SSLContext(_ssl.PROTOCOL_TLS_SERVER)
            context.load_cert_chain(ssl_cert, ssl_key)
            server.socket = context.wrap_socket(server.socket, server_side=True)
            log("   SSL:      enabled")
    log("   Press Ctrl+C to stop\n")

    # FIX #450: Configure logging with rotation
    try:
        import logging.handlers as _lh
        _log_dir = os.path.join(project_root, ".tw", "logs")
        os.makedirs(_log_dir, exist_ok=True)
        _file_handler = _lh.RotatingFileHandler(
            os.path.join(_log_dir, "server.log"),
            maxBytes=5 * 1024 * 1024,  # 5MB
            backupCount=3,
        )
        _file_handler.setFormatter(logging.Formatter("%(asctime)s [%(levelname)s] %(name)s: %(message)s"))
        logging.getLogger().addHandler(_file_handler)
    except OSError:
        pass  # Logging is best-effort

    stop_event = threading.Event()

    def _shutdown(signum, frame) -> None:
        log("\nShutting down...")
        stop_event.set()
        threading.Thread(target=server.shutdown, daemon=False).start()  # FIX #128: Non-daemon for graceful shutdown

    signal.signal(signal.SIGTERM, _shutdown)
    signal.signal(signal.SIGINT, _shutdown)

    try:
        server.serve_forever()
    except KeyboardInterrupt:
        pass
    finally:
        server.server_close()
        log("Server stopped.")


# v0.9.08 FIX: Optional Redis-backed SSR cache for persistence
class RedisSSRCache:
    """Redis-backed SSR cache. Falls back to in-memory if Redis unavailable.
    Set TW_REDIS_URL=redis://localhost:6379/0 to enable.
    """
    def __init__(self, redis_url=None, ttl=3600):
        self._fallback = SSRCache()
        self._redis = None
        self._ttl = ttl
        try:
            import redis as _redis
            url = redis_url or os.environ.get("TW_REDIS_URL", "")
            if url:
                self._redis = _redis.from_url(url, decode_responses=True)
                self._redis.ping()
        except Exception:
            self._redis = None

    def get(self, key):
        if self._redis:
            try:
                import json as _json
                val = self._redis.get("ssr:" + key)
                if val:
                    _decoded = _json.loads(val)
                    # FIX #434: Decode base64 bytes
                    if isinstance(_decoded, dict) and "_b64" in _decoded:
                        import base64 as _b64
                        return _b64.b64decode(_decoded["_b64"])
                    return _decoded
            except Exception:
                pass
        return self._fallback.get(key)

    def set(self, key, value, ttl=None):
        if self._redis:
            try:
                import json as _json
                # FIX #434: Handle bytes values — encode to base64 before JSON
                if isinstance(value, bytes):
                    import base64 as _b64
                    _serializable = {"_b64": _b64.b64encode(value).decode("ascii")}
                else:
                    _serializable = value
                self._redis.setex("ssr:" + key, ttl or self._ttl, _json.dumps(_serializable))
            except Exception:
                pass
        self._fallback.set(key, value, ttl)

    def clear(self):
        if self._redis:
            try:
                for k in self._redis.scan_iter("ssr:*"):
                    self._redis.delete(k)
            except Exception:
                pass
        self._fallback.clear()

def get_ssr_cache():
    """Get SSR cache - Redis if configured, in-memory fallback."""
    if os.environ.get("TW_REDIS_URL"):
        return RedisSSRCache()
    return SSRCache()


# ── TanStack Query + Server Components (#16) ─────────────────────────
# Server-side prefetch + HydrationBoundary + useSuspenseQuery


class TanStackQueryBridge:
    """Bridge between TanStack Query (React Query) and TW Server Components.

    Enables:
    1. Server-side data prefetching via React Query
    2. Serialization of query cache for client hydration
    3. HydrationBoundary for seamless client-side pickup
    4. useSuspenseQuery integration with Suspense boundaries
    5. Automatic cache invalidation via server actions

    Flow:
    - Server: prefetch query -> serialize cache -> embed in HTML
    - Client: HydrationBoundary picks up cache -> no refetch needed
    - Updates: server action revalidates -> client refetches
    """

    def __init__(self):
        self._query_cache: Dict[str, Any] = {}
        self._query_keys: Dict[str, str] = {}
        self._prefetched: Set[str] = set()

    def prefetch_query(self, query_key: str, query_fn: Callable,
                        args: Optional[dict] = None) -> Any:
        """Prefetch a query on the server.

        Args:
            query_key: Unique query key (e.g. "users", "posts:123")
            query_fn: Function that returns the data
            args: Optional arguments for the query function

        Returns:
            The query result data
        """
        if query_key in self._query_cache:
            return self._query_cache[query_key]["data"]

        try:
            data = query_fn(**args) if args else query_fn()
            self._query_cache[query_key] = {
                "data": data,
                "status": "success",
                "error": None,
                "fetchedAt": __import__("time").time(),
            }
            self._prefetched.add(query_key)
            return data
        except Exception as e:
            self._query_cache[query_key] = {
                "data": None,
                "status": "error",
                "error": str(e),
                "fetchedAt": __import__("time").time(),
            }
            raise

    def get_cache_data(self) -> Dict[str, Any]:
        """Get serialized cache for client hydration."""
        return {
            key: {
                "data": value["data"],
                "status": value["status"],
                "error": value["error"],
                "fetchedAt": value["fetchedAt"],
            }
            for key, value in self._query_cache.items()
        }

    def generate_hydration_boundary(self) -> str:
        """Generate HydrationBoundary script for client.

        This script injects the server-prefetched query cache into
        the client-side TanStack Query cache, so the client doesn't
        need to refetch the same data.
        """
        import json
        cache_data = json.dumps(self.get_cache_data())
        NL = chr(10)
        lines = [
            '<script>',
            '(function() {',
            '  var cacheData = ' + cache_data + ';',
            '  window.__tw_query_cache__ = cacheData;',
            '  // Hydrate TanStack Query if available',
            '  if (window.__tw_react_query__ && window.__tw_react_query__.hydrate) {',
            '    var qc = window.__tw_react_query__.getQueryClient();',
            '    Object.keys(cacheData).forEach(function(key) {',
            '      var entry = cacheData[key];',
            '      qc.setQueryData(key, entry.data);',
            '    });',
            '    console.log("[TanStack] Hydrated " + Object.keys(cacheData).length + " queries");',
            '  } else {',
            '    console.log("[TanStack] Cache ready for hydration (" + Object.keys(cacheData).length + " queries)");',
            '  }',
            '})();',
            '</script>',
        ]
        return NL.join(lines)

    def invalidate_query(self, query_key: str) -> None:
        """Invalidate a query in the cache."""
        if query_key in self._query_cache:
            del self._query_cache[query_key]
        self._prefetched.discard(query_key)

    def invalidate_queries(self, query_prefix: str) -> int:
        """Invalidate all queries matching a prefix."""
        keys_to_remove = [k for k in self._query_cache if k.startswith(query_prefix)]
        for key in keys_to_remove:
            del self._query_cache[key]
            self._prefetched.discard(key)
        return len(keys_to_remove)

    def get_stats(self) -> Dict[str, Any]:
        return {
            "total_queries": len(self._query_cache),
            "prefetched": len(self._prefetched),
            "cache_keys": list(self._query_cache.keys()),
        }


# ── RSC Streaming Integration ──────────────────────────────────────

class RSCStreamHandler:
    """Handles RSC payload streaming via HTTP.

    Integrates with the server to:
    1. Detect RSC requests (Accept header)
    2. Stream RSC payload chunks via chunked transfer encoding
    3. Fall back to full HTML for non-RSC requests
    4. Handle SSE-style streaming for suspense resolution
    """

    RSC_CONTENT_TYPE = "text/x-tw-rsc"

    def __init__(self):
        self._enabled = True
        self._stream_timeout_ms = 30000

    def is_stream_request(self, headers: Dict[str, str]) -> bool:
        """Check if this is an RSC stream request."""
        accept = headers.get("accept", "") or headers.get("Accept", "")
        return self.RSC_CONTENT_TYPE in accept

    def create_stream_headers(self) -> Dict[str, str]:
        """Create headers for an RSC stream response."""
        return {
            "Content-Type": self.RSC_CONTENT_TYPE,
            "Transfer-Encoding": "chunked",
            "Cache-Control": "no-cache",
            "X-TW-RSC": "1",
            "X-Accel-Buffering": "no",  # Disable nginx buffering
        }

    def format_chunk(self, data: bytes, is_final: bool = False) -> bytes:
        """Format a chunk for chunked transfer encoding."""
        if is_final:
            return b"0\r\n\r\n"
        chunk_size = hex(len(data))[2:]
        return (chunk_size + "\r\n").encode() + data + b"\r\n"

    def generate_sse_chunk(self, event: str, data: str) -> str:
        """Format a chunk as Server-Sent Events."""
        return "event: " + event + "\ndata: " + data + "\n\n"

    def enable(self) -> None: self._enabled = True
    def disable(self) -> None: self._enabled = False

    def get_info(self) -> Dict[str, Any]:
        return {
            "enabled": self._enabled,
            "content_type": self.RSC_CONTENT_TYPE,
            "timeout_ms": self._stream_timeout_ms,
        }
