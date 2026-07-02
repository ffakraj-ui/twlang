"""
TW Production Server Runtime
- Real SSR (render server / render edge)
- Real API routes (production)
- Middleware (same as dev)
- Static file serving with ETag/Cache-Control
- Graceful shutdown, threading, keep-alive
"""

import gzip
import http.server
import json
import logging
import mimetypes
import os
from collections import OrderedDict
import signal
import socketserver
import sys
import threading
import time
import urllib.parse
from typing import Dict, List, Optional, Tuple

from . import compiler
from .common import content_hash, log
from .framework import (
    TWProject,
    RouteMatch,
    is_path_within,
    normalize_url_path,
    strip_trailing_slash,
    render_error_html,
    format_compiler_error,
    decode_request_body,
    parse_cookie_header,
    render_cookie_header,
    safe_read_binary,
    load_project_env,
    configure_compiler_paths,
    invalidate_compiler_caches,
    build_preview_candidates,
)


logger = logging.getLogger(__name__)


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

    def _enforce_namespace_limit(self, namespace: Optional[str], namespace_max: Optional[int]):
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
    ):
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

    def invalidate(self, key: str):
        with self._lock:
            self._store.pop(key, None)

    def clear(self):
        with self._lock:
            self._store.clear()


# ─── ETag / static file helpers ──────────────────────────────────────────────

def compute_etag(data: bytes) -> str:
    return '"' + content_hash(data) + '"'


def serve_static_file(path: str) -> Optional[Tuple[bytes, str, str]]:
    """Returns (body, content_type, etag) or None."""
    if not os.path.isfile(path):
        return None
    with open(path, "rb") as f:
        body = f.read()
    content_type = mimetypes.guess_type(path)[0] or "application/octet-stream"
    etag = compute_etag(body)
    return body, content_type, etag


def try_brotli_or_gzip(path: str) -> Optional[Tuple[bytes, str]]:
    """Returns (compressed_body, encoding) if pre-compressed variant exists."""
    for variant, encoding in [(path + ".br", "br"), (path + ".gz", "gz")]:
        if os.path.isfile(variant):
            with open(variant, "rb") as f:
                return f.read(), encoding
    return None


# ─── Production Request Handler ──────────────────────────────────────────────

def make_production_handler(project: TWProject, output_dir: Optional[str], ssr_cache: SSRCache):

    output_dir_abs = os.path.abspath(output_dir) if output_dir else None

    class TWProductionHandler(http.server.BaseHTTPRequestHandler):
        server_version = "TWServer/1.0"

        def log_message(self, fmt, *args):
            ts = time.strftime("%H:%M:%S")
            log(f"[{ts}] {self.command} {self.path} — {fmt % args}")

        def do_GET(self):    self._handle("GET")
        def do_POST(self):   self._handle("POST")
        def do_PUT(self):    self._handle("PUT")
        def do_PATCH(self):  self._handle("PATCH")
        def do_DELETE(self): self._handle("DELETE")
        def do_OPTIONS(self):self._handle("OPTIONS")
        def do_HEAD(self):   self._handle("HEAD")

        def _handle(self, method: str):
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
            api_route = project.resolve_api_route(url_path)
            if api_route is not None:
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
                        compressed = try_brotli_or_gzip(candidate)
                        if compressed:
                            cbody, enc = compressed
                            if (enc == "br" and "br" in accept_enc) or (enc == "gz" and "gzip" in accept_enc):
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
                        self._send(200, body_bytes if method != "HEAD" else b"", ct,
                                   extra_headers=[("ETag", etag), ("Cache-Control", "public, max-age=3600")] + mw.get("headers", []),
                                   cookies=mw.get("cookies", []))
                        return

            # ── SSR / dynamic page ────────────────────────────────────────
            match = project.resolve_route(url_path)
            if not match:
                self._serve_404(mw)
                return

            self._serve_page(match, method, mw, raw_path, request_headers)

        def _build_page_cache_key(self, match: RouteMatch, raw_path: str, request_headers: Dict[str, str], render_mode: str, page_ast) -> str:
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

        def _serve_page(self, match: RouteMatch, method: str, mw: dict, raw_path: str, request_headers: Dict[str, str]):
            page_path = match.page_info["path"]
            try:
                page_ast = compiler.load_page_ast_from_file(page_path)
            except Exception as err:
                self._serve_500(format_compiler_error(page_path, err), mw)
                return

            render_mode = getattr(page_ast, "render_mode", "static")
            revalidate_ttl = getattr(page_ast, "revalidate", None)
            if revalidate_ttl is not None:
                try:
                    revalidate_ttl = float(revalidate_ttl)
                except (TypeError, ValueError):
                    logger.exception("Invalid `revalidate` value in %s: %r", page_path, revalidate_ttl)
                    revalidate_ttl = None

            cache_key = self._build_page_cache_key(match, raw_path, request_headers, render_mode, page_ast)
            cache_size = getattr(page_ast, "cache_size", None)
            try:
                cache_size = int(cache_size) if cache_size is not None else None
            except (TypeError, ValueError):
                cache_size = None

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

            body_bytes = response["html"].encode("utf-8")
            status = response.get("status", 200)
            page_headers = response.get("headers", [])

            # Cache rendered output for static/edge pages with revalidate
            if render_mode in {"static", "edge"} and revalidate_ttl:
                ssr_cache.set(
                    cache_key,
                    body_bytes,
                    revalidate_ttl,
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
                ] + mw.get("headers", []) + page_headers,
                cookies=mw.get("cookies", []),
            )

        def _serve_404(self, mw: dict):
            try:
                custom = project.compile_special_page(404, dev_mode=False)
                if custom:
                    self._send(404, custom.encode("utf-8"), "text/html; charset=utf-8",
                               extra_headers=mw.get("headers", []), cookies=mw.get("cookies", []))
                    return
            except Exception as err:
                logger.exception("Failed to compile custom 404 page")
            self._send(404, render_error_html("Not Found", f"Route not found: {normalize_url_path(self.path)}", 404),
                       "text/html; charset=utf-8", extra_headers=mw.get("headers", []), cookies=mw.get("cookies", []))

        def _serve_500(self, message: str, mw: dict):
            try:
                custom = project.compile_special_page(500, dev_mode=False)
                if custom:
                    self._send(500, custom.encode("utf-8"), "text/html; charset=utf-8",
                               extra_headers=mw.get("headers", []), cookies=mw.get("cookies", []))
                    return
            except Exception as err:
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
                  cookies: Optional[List] = None):
            self.send_response(status)
            self.send_header("Content-Type", content_type)
            self.send_header("Content-Length", str(len(body)))
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
            if body:
                try:
                    self.wfile.write(body)
                except (BrokenPipeError, ConnectionResetError):
                    pass

    return TWProductionHandler


# ─── Threaded TCP server ──────────────────────────────────────────────────────

class ThreadedTCPServer(socketserver.ThreadingMixIn, socketserver.TCPServer):
    allow_reuse_address = True
    daemon_threads = True


# ─── run_production_server ────────────────────────────────────────────────────

def run_production_server(
    project_root: str,
    host: str = "0.0.0.0",
    port: int = 8000,
    output_dir: Optional[str] = None,
    workers: Optional[int] = None,
):
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
    ssr_cache = SSRCache(max_entries=int(config_cache_max) if config_cache_max is not None else 512)

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
    if output_dir and os.path.isdir(output_dir):
        log(f"   Static:    {os.path.abspath(output_dir)}")
    log("   SSR cache: enabled")
    log("   Press Ctrl+C to stop\n")

    stop_event = threading.Event()

    def _shutdown(signum, frame):
        log("\nShutting down...")
        stop_event.set()
        threading.Thread(target=server.shutdown, daemon=True).start()

    signal.signal(signal.SIGTERM, _shutdown)
    signal.signal(signal.SIGINT, _shutdown)

    try:
        server.serve_forever()
    except KeyboardInterrupt:
        pass
    finally:
        server.server_close()
        log("Server stopped.")
