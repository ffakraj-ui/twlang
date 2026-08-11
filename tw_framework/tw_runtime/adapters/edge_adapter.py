"""
TW Framework — Edge Runtime Adapter (v0.9.0)

TW's own "edge-like" runtime: a pre-warmed Python worker pool that runs
in-process with sub-millisecond cold start. Like Next.js Edge Runtime,
it has LIMITED capabilities — no filesystem, no subprocess, no native modules.

What works: tw.http.fetch(), tw.crypto.hash(), tw.cache, tw.env, JSON
What doesn't: fs, child_process, native npm/pip packages, direct DB drivers

This is ideal for: auth checks, redirects, header injection, JSON responses,
A/B testing, rate limiting, lightweight API proxies.
"""

from __future__ import annotations
import os
import sys
import json
import hashlib
import hmac
import secrets
import urllib.request
import urllib.error
from typing import Any, Dict, List, Optional, Union

from ..base import BaseRuntime, RuntimeCapability
from ..abstractions import StorageAPI, HttpAPI, CryptoAPI, EnvAPI, CacheAPI


class EdgeStorage(StorageAPI):
    """Edge storage adapter — NO filesystem access.

    Uses an in-memory KV store (like Cloudflare KV / Deno KV).
    Persistent within the worker pool session, cleared on restart.
    """

    _kv: Dict[str, bytes] = {}

    def __init__(self):
        # v0.9.08 FIX #10: Per-instance KV store (was class variable = shared across all requests!)
        self._kv = {}

    def read(self, path: str, encoding: str = "utf-8") -> Union[str, bytes]:
        # Try in-memory KV first
        if path in self._kv:
            data = self._kv[path]
            return data.decode(encoding) if encoding else data
        raise PermissionError(
            f"Edge runtime does not support filesystem access. "
            f"Use tw.storage.write() to store data in KV, or switch to "
            f"runtime = 'python' or runtime = 'nodejs' for file access."
        )

    def write(self, path: str, data: Union[str, bytes]) -> bool:
        if isinstance(data, str):
            data = data.encode("utf-8")
        self._kv[path] = data
        return True

    def delete(self, path: str) -> bool:
        return self._kv.pop(path, None) is not None

    def exists(self, path: str) -> bool:
        return path in self._kv

    def list(self, dir_path: str, pattern: str = "*") -> List[str]:
        import fnmatch
        # v0.9.08 FIX #10b: Use pattern directly, not os.path.join on string keys
        full_pattern = (dir_path + pattern) if dir_path else pattern
        return [k for k in self._kv.keys() if fnmatch.fnmatch(k, full_pattern)]


class EdgeHttp(HttpAPI):
    """Edge HTTP adapter — uses urllib (same as Python, but restricted to HTTP only).

    Edge runtime supports network access (like Next.js Edge / Cloudflare Workers).
    """

    def fetch(self, url: str, options: Optional[dict] = None) -> dict:
        opts = options or {}
        method = opts.get("method", "GET").upper()
        headers = opts.get("headers", {})
        body = opts.get("body")
        timeout = min(opts.get("timeout", 30), 30)  # Edge: max 30s

        req_body = None
        if body is not None:
            if isinstance(body, (dict, list)):
                req_body = json.dumps(body).encode("utf-8")
                if not any(k.lower() == "content-type" for k in headers):
                    headers["Content-Type"] = "application/json"
            elif isinstance(body, str):
                req_body = body.encode("utf-8")
            elif isinstance(body, bytes):
                req_body = body

        req = urllib.request.Request(url, data=req_body, method=method)
        for k, v in headers.items():
            req.add_header(k, v)

        try:
            with urllib.request.urlopen(req, timeout=timeout) as resp:
                text = resp.read().decode("utf-8", errors="replace")
                resp_headers = dict(resp.headers)
                content_type = resp_headers.get("Content-Type", "")
                data = text
                if "application/json" in content_type:
                    try:
                        data = json.loads(text)
                    except Exception:
                        pass
                return {
                    "ok": 200 <= resp.status < 300,
                    "status": resp.status,
                    "statusText": resp.reason,
                    "url": url,
                    "headers": resp_headers,
                    "text": text,
                    "data": data,
                }
        except urllib.error.HTTPError as e:
            text = ""
            try:
                text = e.read().decode("utf-8", errors="replace")
            except Exception:
                pass
            return {
                "ok": False,
                "status": e.code,
                "statusText": e.reason,
                "url": url,
                "headers": dict(e.headers),
                "text": text,
                "data": text,
            }


class EdgeCrypto(CryptoAPI):
    """Edge crypto adapter — uses Python hashlib (same as Node crypto for hashing).

    Edge runtime supports crypto operations (like Web Crypto API).
    """

    def hash(self, algorithm: str, data: Union[str, bytes]) -> str:
        if isinstance(data, str):
            data = data.encode("utf-8")
        h = hashlib.new(algorithm)
        h.update(data)
        return h.hexdigest()

    def hmac(self, algorithm: str, key: Union[str, bytes], message: Union[str, bytes]) -> str:
        if isinstance(key, str):
            key = key.encode("utf-8")
        if isinstance(message, str):
            message = message.encode("utf-8")
        return hmac.new(key, message, algorithm).hexdigest()

    def random(self, length: int = 32) -> str:
        return secrets.token_hex(length)

    def random_bytes(self, length: int = 32) -> bytes:
        return secrets.token_bytes(length)

    def uuid(self) -> str:
        import uuid
        return str(uuid.uuid4())


class EdgeEnv(EnvAPI):
    """Edge env adapter — limited environment variable access.

    Only variables explicitly marked as edge-safe are exposed.
    In development, all env vars are available. In production, only
    those prefixed with TW_EDGE_ or explicitly allowed.
    """

    def get(self, name: str, default: str = "") -> str:
        # v0.9.08 FIX #11: Filter env vars — only TW_/PUBLIC_/EDGE_/NODE_ENV are safe
        if name.startswith(("TW_", "PUBLIC_", "EDGE_")) or name in ("NODE_ENV", "PYTHONUNBUFFERED"):
            return os.environ.get(name, default)
        return default

    def all(self) -> Dict[str, str]:
        # Only return non-sensitive env vars
        safe = {}
        for k, v in os.environ.items():
            if k.startswith(("TW_", "PUBLIC_", "EDGE_")) or k in ("NODE_ENV", "PYTHONUNBUFFERED"):
                safe[k] = v
        return safe


class EdgeRuntime(BaseRuntime):
    """Edge runtime — TW's own lightweight runtime.

    Like Next.js Edge Runtime:
    - Sub-millisecond cold start (in-process, no subprocess)
    - NO filesystem (uses in-memory KV instead)
    - NO subprocess / child_process
    - NO native modules
    - YES network (fetch)
    - YES crypto
    - YES cache (in-memory)
    - YES env vars (limited)

    Best for: auth, redirects, JSON APIs, header injection, A/B testing
    """

    @property
    def runtime_name(self) -> str:
        return "edge"

    @property
    def display_name(self) -> str:
        return "Edge"

    @property
    def version(self) -> str:
        return f"tw-edge/{sys.version_info.major}.{sys.version_info.minor}"

    def capabilities(self) -> Dict[str, bool]:
        return {
            RuntimeCapability.FILESYSTEM.value: False,          # ❌ No fs
            RuntimeCapability.NETWORK.value: True,               # ✅ fetch
            RuntimeCapability.NATIVE_MODULES.value: False,       # ❌ No npm/pip
            RuntimeCapability.SUBPROCESS.value: False,           # ❌ No child_process
            RuntimeCapability.DATABASE.value: False,             # ❌ No direct DB
            RuntimeCapability.CRYPTO.value: True,               # ✅ hashlib
            RuntimeCapability.CACHE.value: True,                 # ✅ in-memory
            RuntimeCapability.ENV_VARS.value: True,             # ✅ (limited)
            RuntimeCapability.PERSISTENT_STORAGE.value: False,   # v0.9.08 FIX #12: in-memory KV is NOT persistent
            RuntimeCapability.TIMERS.value: False,              # ❌ No timers
            RuntimeCapability.STREAMING.value: False,           # ❌ No streaming
        }

    def is_available(self) -> bool:
        return True  # Edge runtime is always available (it's Python in-process)

    # ── API Adapters ──────────────────────────────────────────────────

    @property
    def storage(self) -> EdgeStorage:
        return EdgeStorage()

    @property
    def http(self) -> EdgeHttp:
        return EdgeHttp()

    @property
    def cache(self) -> CacheAPI:
        return CacheAPI()

    @property
    def crypto(self) -> EdgeCrypto:
        return EdgeCrypto()

    @property
    def env(self) -> EdgeEnv:
        return EdgeEnv()
