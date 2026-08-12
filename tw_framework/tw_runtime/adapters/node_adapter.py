"""
TW Framework — Node.js Runtime Adapter (v0.9.0)

Full Node.js runtime: supports filesystem, native modules, network,
subprocess, database drivers, crypto, cache, env — everything.

This adapter delegates to the persistent Node.js worker for .twm execution
but provides tw.* common API adapters that map to Node.js capabilities.
"""

from __future__ import annotations
import os
import shutil
from typing import Any, Dict, List, Optional, Union

from ..base import BaseRuntime, RuntimeCapability
from ..abstractions import StorageAPI, HttpAPI, CryptoAPI, EnvAPI, CacheAPI
import urllib
import urllib


class NodeStorage(StorageAPI):
    """Node.js storage adapter — maps tw.storage to Node fs (via Python os as fallback)."""

    def read(self, path: str, encoding: str = "utf-8") -> Union[str, bytes]:
        mode = "r" if encoding else "rb"
        with open(path, mode, encoding=encoding if encoding else None) as f:
            return f.read()

    def write(self, path: str, data: Union[str, bytes]) -> bool:
        mode = "w" if isinstance(data, str) else "wb"
        with open(path, mode, encoding="utf-8" if mode == "w" else None) as f:
            f.write(data)
        return True

    def delete(self, path: str) -> bool:
        try:
            os.remove(path)
            return True
        except FileNotFoundError:
            return False

    def exists(self, path: str) -> bool:
        return os.path.exists(path)

    def list(self, dir_path: str, pattern: str = "*") -> List[str]:
        import glob
        return glob.glob(os.path.join(dir_path, pattern))


class NodeHttp(HttpAPI):
    """Node.js HTTP adapter — uses Python urllib (proxy for Node fetch)."""

    def fetch(self, url: str, options: Optional[dict] = None) -> dict:
        import urllib.request
        import urllib.error
        opts = options or {}
        method = opts.get("method", "GET").upper()
        headers = opts.get("headers", {})
        body = opts.get("body")
        timeout = opts.get("timeout", 30)

        req_body = None
        if body is not None:
            if isinstance(body, (dict, list)):
                req_body = __import__("json").dumps(body).encode("utf-8")
                if "content-type" not in {k.lower() for k in headers}:
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
                        data = __import__("json").loads(text)
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
            text = e.read().decode("utf-8", errors="replace") if e.fp else ""
            return {
                "ok": False,
                "status": e.code,
                "statusText": e.reason,
                "url": url,
                "headers": dict(e.headers),
                "text": text,
                "data": text,
            }


class NodeRuntime(BaseRuntime):
    """Node.js runtime — full capabilities, persistent worker for .twm execution."""

    @property
    def runtime_name(self) -> str:
        return "nodejs"

    @property
    def display_name(self) -> str:
        return "Node.js"

    _cached_version: str = ""

    @property
    def version(self) -> str:
        # v0.9.08 FIX #15: Cache version (was spawning subprocess on every access!)
        if self._cached_version:
            return self._cached_version
        try:
            import subprocess
            result = subprocess.run(["node", "--version"], capture_output=True, text=True, timeout=5)
            if result.returncode == 0:
                self._cached_version = result.stdout.strip().lstrip("v")
                return self._cached_version
        except Exception:
            pass
        self._cached_version = "unknown"
        return self._cached_version

    def capabilities(self) -> Dict[str, bool]:
        return {
            RuntimeCapability.FILESYSTEM.value: True,
            RuntimeCapability.NETWORK.value: True,
            RuntimeCapability.NATIVE_MODULES.value: True,
            RuntimeCapability.SUBPROCESS.value: True,
            RuntimeCapability.DATABASE.value: True,
            RuntimeCapability.CRYPTO.value: True,
            RuntimeCapability.CACHE.value: True,
            RuntimeCapability.ENV_VARS.value: True,
            RuntimeCapability.PERSISTENT_STORAGE.value: True,
            RuntimeCapability.TIMERS.value: True,
            RuntimeCapability.STREAMING.value: True,
        }

    def is_available(self) -> bool:
        from ...npm_manager import find_node
        return find_node() is not None

    # ── API Adapters ──────────────────────────────────────────────────

    @property
    def storage(self) -> NodeStorage:
        return NodeStorage()

    @property
    def http(self) -> NodeHttp:
        return NodeHttp()

    @property
    def cache(self) -> CacheAPI:
        return CacheAPI()  # In-memory cache (Node worker also has its own)

    @property
    def crypto(self) -> CryptoAPI:
        return CryptoAPI()  # Python hashlib (same algorithms as Node crypto)

    @property
    def env(self) -> EnvAPI:
        return EnvAPI()  # os.environ (maps to process.env in Node context)
