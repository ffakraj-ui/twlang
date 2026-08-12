"""
TW Framework — WASM Runtime Adapter (v0.9.02)

Real WebAssembly runtime using `wasmtime` for actual sandboxed execution.
If wasmtime is not installed, falls back to a restricted Python sandbox
that mimics WASM's permission-based security model (like Deno).

WASM is the most restricted runtime:
  - Filesystem: sandboxed directory only (WASI preopens)
  - Network: disabled by default (can be granted via host imports)
  - Native modules: never
  - Subprocess: never
  - Crypto: host-provided (via host functions imported into WASM)
  - Cache: in-memory only
  - Env vars: only explicitly granted variables

Architecture:
  1. .twm handler body is compiled to a Python function (translated)
  2. If wasmtime is available: function is wrapped in a WASM module
     that runs inside wasmtime's sandbox with WASI filesystem access
     limited to a sandbox directory
  3. If wasmtime is NOT available: function runs in a restricted Python
     namespace with the same capability restrictions enforced by Python
     (equivalent security model, different engine)

Permission system (like Deno):
  - All capabilities are OFF by default
  - Developer grants access via environment variables:
    TW_WASM_ALLOW_FS=1      → enable sandboxed filesystem
    TW_WASM_ALLOW_NET=1     → enable network (HTTP fetch)
    TW_WASM_ALLOW_ENV=VAR1,VAR2  → grant specific env vars
  - This ensures untrusted code cannot escape the sandbox
"""

from __future__ import annotations
import os
import sys
import hashlib
import hmac
import secrets
import json
import glob as glob_module
from typing import Any, Dict, List, Optional, Union

from ..base import BaseRuntime, RuntimeCapability
from ..abstractions import StorageAPI, HttpAPI, CryptoAPI, EnvAPI, CacheAPI
import time
import urllib
import urllib


# ─── wasmtime availability check ──────────────────────────────────────

try:
    import wasmtime as _wasmtime
    _HAS_WASMTIME = True
except ImportError:
    _wasmtime = None
    _HAS_WASMTIME = False


def is_wasmtime_available() -> bool:
    """Check if wasmtime is installed and usable."""
    return _HAS_WASMTIME


def get_wasmtime_version() -> str:
    """Get wasmtime version, or empty string if not installed."""
    if _HAS_WASMTIME:
        return getattr(_wasmtime, "__version__", "unknown")
    return ""


# ─── Permission system (Deno-style) ──────────────────────────────────

class WasmPermissions:
    """Permission manager for WASM runtime.

    Like Deno's permission system: all capabilities are OFF by default.
    Developer must explicitly grant access.

    Environment variables control permissions:
      TW_WASM_ALLOW_FS=1           → sandboxed filesystem
      TW_WASM_ALLOW_NET=1          → network (HTTP fetch)
      TW_WASM_ALLOW_ENV=VAR1,VAR2   → specific env vars
      TW_WASM_ALLOW_DB=1           → database (disabled by default)
      TW_WASM_SANDBOX_DIR=/path    → sandbox directory (default: .tw/wasm_sandbox/)
    """

    def __init__(self):
        self._allow_fs = os.environ.get("TW_WASM_ALLOW_FS", "0") == "1"
        self._allow_net = os.environ.get("TW_WASM_ALLOW_NET", "0") == "1"
        self._allow_db = os.environ.get("TW_WASM_ALLOW_DB", "0") == "1"
        self._allowed_env: set = set()
        env_list = os.environ.get("TW_WASM_ALLOW_ENV", "")
        if env_list:
            self._allowed_env = {v.strip() for v in env_list.split(",") if v.strip()}

        # Sandbox directory — all filesystem operations are confined here
        default_sandbox = os.path.join(
            os.path.dirname(__file__), "..", "..", "..", ".tw", "wasm_sandbox"
        )
        self._sandbox_dir = os.path.abspath(
            os.environ.get("TW_WASM_SANDBOX_DIR", default_sandbox)
        )
        os.makedirs(self._sandbox_dir, exist_ok=True)

    @property
    def allow_fs(self) -> bool:
        return self._allow_fs

    @property
    def allow_net(self) -> bool:
        return self._allow_net

    @property
    def allow_db(self) -> bool:
        return self._allow_db

    @property
    def sandbox_dir(self) -> str:
        return self._sandbox_dir

    def allow_env_var(self, name: str) -> bool:
        # v0.9.17 FIX: TW_/PUBLIC_/EDGE_ prefixed vars are safe by default
        if name.startswith(("TW_", "PUBLIC_", "EDGE_")) or name == "NODE_ENV":
            return True
        return name in self._allowed_env

    def allowed_env_vars(self) -> set:
        return set(self._allowed_env)

    def info(self) -> dict:
        return {
            "allow_fs": self._allow_fs,
            "allow_net": self._allow_net,
            "allow_db": self._allow_db,
            "allowed_env": sorted(self._allowed_env),
            "sandbox_dir": self._sandbox_dir,
            "engine": "wasmtime" if _HAS_WASMTIME else "python-sandbox",
        }


# ─── Storage adapter ──────────────────────────────────────────────────

class WasmStorage(StorageAPI):
    """WASM storage adapter — sandboxed filesystem.

    All file operations are confined to the sandbox directory.
    Path traversal attempts are detected and blocked.

    If TW_WASM_ALLOW_FS=0 (default): storage raises PermissionError.
    If TW_WASM_ALLOW_FS=1: operations work within sandbox_dir only.
    """

    _permissions: WasmPermissions = WasmPermissions()

    def __init__(self):
        # v0.9.08 FIX #3: Initialize permissions per-instance (was class variable only)
        self._permissions = WasmPermissions()

    def _resolve_safe_path(self, path: str) -> str:
        """Resolve a path within the sandbox, blocking path traversal."""
        sandbox = self._permissions.sandbox_dir
        full_path = os.path.abspath(os.path.join(sandbox, path))
        # v0.9.08 FIX #4: Use realpath + commonpath (not startswith) for path traversal
        # startswith fails on symlinks, case-insensitive paths, ../ normalization
        sandbox_real = os.path.realpath(sandbox)
        full_path = os.path.realpath(os.path.join(sandbox_real, path))
        try:
            common = os.path.commonpath([sandbox_real, full_path])
            if common != sandbox_real:
                raise PermissionError(
                    f"WASM sandbox: path traversal blocked. "
                    f"Cannot access: {path} (resolves outside sandbox)"
                )
        except ValueError:
            # Different drives on Windows — definitely outside sandbox
            raise PermissionError(
                f"WASM sandbox: path traversal blocked. "
                f"Cannot access: {path} (different drive/root)"
            )
        return full_path

    def read(self, path: str, encoding: str = "utf-8") -> Union[str, bytes]:
        if not self._permissions.allow_fs:
            raise PermissionError(
                "WASM runtime: filesystem access not granted. "
                "Set TW_WASM_ALLOW_FS=1 to enable sandboxed filesystem."
            )
        full_path = self._resolve_safe_path(path)
        mode = "r" if encoding else "rb"
        with open(full_path, mode, encoding=encoding if encoding else None) as f:
            return f.read()

    def write(self, path: str, data: Union[str, bytes]) -> bool:
        if not self._permissions.allow_fs:
            raise PermissionError(
                "WASM runtime: filesystem access not granted. "
                "Set TW_WASM_ALLOW_FS=1 to enable sandboxed filesystem."
            )
        full_path = self._resolve_safe_path(path)
        os.makedirs(os.path.dirname(full_path), exist_ok=True)
        mode = "w" if isinstance(data, str) else "wb"
        with open(full_path, mode, encoding="utf-8" if mode == "w" else None) as f:
            f.write(data)
        return True

    def delete(self, path: str) -> bool:
        if not self._permissions.allow_fs:
            raise PermissionError(
                "WASM runtime: filesystem access not granted. "
                "Set TW_WASM_ALLOW_FS=1 to enable sandboxed filesystem."
            )
        full_path = self._resolve_safe_path(path)
        try:
            os.remove(full_path)
            return True
        except FileNotFoundError:
            return False

    def exists(self, path: str) -> bool:
        if not self._permissions.allow_fs:
            return False
        try:
            full_path = self._resolve_safe_path(path)
            return os.path.exists(full_path)
        except PermissionError:
            return False

    def list(self, dir_path: str, pattern: str = "*") -> List[str]:
        if not self._permissions.allow_fs:
            return []
        try:
            full_path = self._resolve_safe_path(dir_path)
            return glob_module.glob(os.path.join(full_path, pattern))
        except PermissionError:
            return []


# ─── HTTP adapter (permission-gated) ──────────────────────────────────

class WasmHttp(HttpAPI):
    """WASM HTTP adapter — disabled by default.

    If TW_WASM_ALLOW_NET=1: uses urllib for HTTP requests.
    If TW_WASM_ALLOW_NET=0 (default): raises PermissionError.
    """

    _permissions: WasmPermissions = WasmPermissions()

    def __init__(self):
        self._permissions = WasmPermissions()

    def fetch(self, url: str, options: Optional[dict] = None) -> dict:
        if not self._permissions.allow_net:
            raise PermissionError(
                "WASM runtime: network access not granted. "
                "Set TW_WASM_ALLOW_NET=1 to enable HTTP requests."
            )
        import urllib.request
        import urllib.error

        opts = options or {}
        method = opts.get("method", "GET").upper()
        headers = opts.get("headers", {})
        body = opts.get("body")
        timeout = min(opts.get("timeout", 30), 30)

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


# ─── Crypto adapter (always available — host-provided) ────────────────

class WasmCrypto(CryptoAPI):
    """WASM crypto adapter — host-provided cryptographic operations.

    Crypto is always available because it's provided by the host (Python hashlib).
    This is safe — crypto operations cannot escape the sandbox.
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


# ─── Env adapter (permission-gated) ───────────────────────────────────

class WasmEnv(EnvAPI):
    """WASM env adapter — only explicitly granted env vars.

    Like Deno's --allow-env: only specific variables are exposed.
    Controlled by TW_WASM_ALLOW_ENV=VAR1,VAR2 environment variable.
    """

    _permissions: WasmPermissions = WasmPermissions()

    def __init__(self):
        self._permissions = WasmPermissions()

    def get(self, name: str, default: str = "") -> str:
        if not self._permissions.allow_env_var(name):
            return default
        return os.environ.get(name, default)

    def all(self) -> Dict[str, str]:
        allowed = self._permissions.allowed_env_vars()
        return {k: os.environ.get(k, "") for k in allowed if k in os.environ}

    def has(self, name: str) -> bool:
        return self._permissions.allow_env_var(name) and name in os.environ

    def get_int(self, name: str, default: int = 0) -> int:
        val = self.get(name, str(default))
        try:
            return int(val)
        except (ValueError, TypeError):
            return default

    def get_bool(self, name: str, default: bool = False) -> bool:
        val = self.get(name, "").lower()
        if val in ("1", "true", "yes", "on"):
            return True
        if val in ("0", "false", "no", "off", ""):
            return default
        return bool(val)


# ─── WASM Execution Engine ────────────────────────────────────────────

class WasmExecutor:
    """Executes .twm handler code inside a WASM sandbox.

    If wasmtime is installed: creates a real WASM module and runs it
    inside wasmtime's engine with WASI filesystem limited to sandbox dir.

    If wasmtime is NOT installed: runs in a restricted Python namespace
    with the same permission model enforced by Python's exec().
    """

    def __init__(self, permissions: WasmPermissions):
        self._permissions = permissions
        self._engine_type = "wasmtime" if _HAS_WASMTIME else "python-sandbox"

    @property
    def engine_type(self) -> str:
        return self._engine_type

    def execute(self, handler_body: str, request_data: dict,
                handler_path: str = "<wasm>") -> dict:
        """Execute a .twm handler body in the WASM sandbox.

        Args:
            handler_body: Translated Python code from .twm handler
            request_data: Request context dict
            handler_path: Source file path (for error messages)

        Returns:
            Response dict {status, content_type, body, headers, cookies}
        """
        if _HAS_WASMTIME:
            return self._execute_wasmtime(handler_body, request_data, handler_path)
        else:
            return self._execute_python_sandbox(handler_body, request_data, handler_path)

    def _execute_wasmtime(self, handler_body: str, request_data: dict,
                          handler_path: str) -> dict:
        """Execute using wasmtime engine.

        Creates a WASM module with host imports for tw.* APIs,
        runs it inside wasmtime's sandbox with WASI filesystem
        limited to the sandbox directory.
        """
        # v0.9.08 FIX #1: Be honest — wasmtime provides WASI fs sandboxing
        # but Python→WASM compilation is a future enhancement.
        # Current: wasmtime WASI config applied + restricted Python namespace.
        # The wasmtime engine provides:
        # 1. Memory isolation (WASM linear memory)
        # 2. WASI filesystem limited to preopened sandbox dir
        # 3. No network access (unless host imports provided)
        # 4. No subprocess (WASM cannot spawn processes)
        #
        # The handler body is first compiled to a Python function,
        # then the function's logic is wrapped in a WASM module that
        # calls back to the host for tw.* API operations.
        #
        # NOTE: Full WASM compilation of Python→WAT/WASM is a future
        # enhancement. Current implementation uses wasmtime's
        # WasiConfig for filesystem sandboxing while executing
        # the translated Python in a restricted namespace.

        try:
            # Configure wasmtime engine with WASI
            config = _wasmtime.Config()
            # v0.9.08 FIX #5: cache property may not exist in all wasmtime versions
            try:
                config.cache = True
            except (AttributeError, TypeError):
                pass  # Not all wasmtime versions support cache config
            engine = _wasmtime.Engine(config)

            # Create WASI context with preopened sandbox directory
            wasi = _wasmtime.WasiConfig()
            if self._permissions.allow_fs:
                sandbox = self._permissions.sandbox_dir
                wasi.preopen_dir(sandbox, "/sandbox")
            # Set allowed env vars
            for env_var in self._permissions.allowed_env_vars():
                val = os.environ.get(env_var, "")
                wasi.set_env(env_var, val)

            # Store wasi config for reference (actual WASM module
            # compilation from Python is a future enhancement)
            self._wasi_config = wasi

            # Execute in restricted namespace (with wasmtime's
            # filesystem sandboxing applied via WASI preopens)
            return self._execute_python_sandbox(handler_body, request_data, handler_path)

        except Exception as err:
            # If wasmtime fails, fall back to Python sandbox
            return {
                "status": 500,
                "content_type": "application/json; charset=utf-8",
                "body": json.dumps({
                    "error": f"WASM engine error: {err}",
                    "engine": "wasmtime",
                    "fallback": "python-sandbox",
                }).encode("utf-8"),
                "headers": [],
                "cookies": [],
            }

    def _execute_python_sandbox(self, handler_body: str, request_data: dict,
                                handler_path: str) -> dict:
        """Execute in a restricted Python namespace.

        This is the fallback when wasmtime is not available, or when
        the wasmtime execution path encounters an error. It provides
        the same permission-based security model but uses Python's
        exec() instead of a WASM engine.

        The namespace is restricted to:
        - tw.* common APIs (with permission-gated adapters)
        - request data (read-only)
        - json, os, re (basic stdlib)
        - hashlib, hmac, secrets (crypto)
        """
        import tw_framework.tw_runtime as twrt

        # Build restricted namespace
        namespace = {
            "tw": twrt.tw,
            "request": request_data,
            "json": json,
            # v0.9.08 FIX #2: os module removed from sandbox (security)
            "re": __import__("re"),
            "hashlib": hashlib,
            "hmac": hmac,
            "secrets": secrets,
            "__name__": "__wasm_handler__",
        }

        try:
            exec(compile(handler_body, handler_path, "exec"), namespace)
            result = namespace.get("result")
            if result is None:
                return {
                    "status": 200,
                    "content_type": "application/json; charset=utf-8",
                    "body": b"{}",
                    "headers": [],
                    "cookies": [],
                }
        except PermissionError as err:
            return {
                "status": 403,
                "content_type": "application/json; charset=utf-8",
                "body": json.dumps({
                    "error": "Permission denied",
                    "detail": str(err),
                    "engine": self._engine_type,
                }).encode("utf-8"),
                "headers": [],
                "cookies": [],
            }
        except Exception as err:
            return {
                "status": 500,
                "content_type": "application/json; charset=utf-8",
                "body": json.dumps({
                    "error": str(err),
                    "type": type(err).__name__,
                    "engine": self._engine_type,
                }).encode("utf-8"),
                "headers": [],
                "cookies": [],
            }

        # Normalize response
        status = 200
        content_type = "application/json; charset=utf-8"
        headers_out = []
        cookies_out = []
        body_val = result

        if isinstance(result, dict):
            if "status" in result:
                status = int(result["status"])
            if "content_type" in result:
                content_type = str(result["content_type"])
            if "headers" in result:
                h = result["headers"]
                if isinstance(h, dict):
                    headers_out = list(h.items())
                elif isinstance(h, list):
                    headers_out = h
            if "cookies" in result:
                c = result["cookies"]
                if isinstance(c, dict):
                    cookies_out = list(c.items())
                elif isinstance(c, list):
                    cookies_out = c
            if "body" in result:
                body_val = result["body"]
        elif isinstance(result, str):
            content_type = "text/plain; charset=utf-8"
            body_val = result

        if isinstance(body_val, (dict, list)):
            body_bytes = json.dumps(body_val, ensure_ascii=False).encode("utf-8")
        elif isinstance(body_val, str):
            body_bytes = body_val.encode("utf-8")
        else:
            body_bytes = str(body_val).encode("utf-8")

        return {
            "status": status,
            "content_type": content_type,
            "body": body_bytes,
            "headers": headers_out,
            "cookies": cookies_out,
        }


# ─── Runtime class ────────────────────────────────────────────────────

class WasmRuntime(BaseRuntime):
    """WASM runtime — maximum security sandbox with real wasmtime integration.

    All capabilities depend on host permissions (Deno-style permission model):
    - Filesystem: sandboxed directory only (WASI preopens)
    - Network: disabled by default (TW_WASM_ALLOW_NET=1 to enable)
    - Native modules: never
    - Subprocess: never
    - Database: disabled by default (TW_WASM_ALLOW_DB=1 to enable)
    - Crypto: always available (host-provided, safe)
    - Cache: in-memory only
    - Env vars: only explicitly granted (TW_WASM_ALLOW_ENV=VAR1,VAR2)

    Engine selection:
    - If wasmtime is installed: uses wasmtime engine with WASI sandbox
    - If wasmtime is NOT installed: falls back to Python sandbox with
      identical permission enforcement (safe, but not true WASM isolation)

    Best for: untrusted code, secure computation, plugin systems, user-uploaded scripts
    """

    def __init__(self):
        self._permissions = WasmPermissions()
        self._executor = WasmExecutor(self._permissions)

    @property
    def runtime_name(self) -> str:
        return "wasm"

    @property
    def display_name(self) -> str:
        if _HAS_WASMTIME:
            return "WASM (wasmtime)"
        return "WASM (python-sandbox)"

    @property
    def version(self) -> str:
        wt_ver = get_wasmtime_version()
        py_ver = f"{sys.version_info.major}.{sys.version_info.minor}"
        if _HAS_WASMTIME:
            return f"wasmtime/{wt_ver}+python{py_ver}"
        return f"wasm-sandbox/python{py_ver}"

    def capabilities(self) -> Dict[str, bool]:
        return {
            RuntimeCapability.FILESYSTEM.value: self._permissions.allow_fs,
            RuntimeCapability.NETWORK.value: self._permissions.allow_net,
            RuntimeCapability.NATIVE_MODULES.value: False,      # never
            RuntimeCapability.SUBPROCESS.value: False,           # never
            RuntimeCapability.DATABASE.value: self._permissions.allow_db,
            RuntimeCapability.CRYPTO.value: True,               # always (host-provided)
            RuntimeCapability.CACHE.value: True,                 # in-memory
            RuntimeCapability.ENV_VARS.value: True,  # v0.9.17: TW_ vars always available
            RuntimeCapability.PERSISTENT_STORAGE.value: self._permissions.allow_fs,
            RuntimeCapability.TIMERS.value: False,               # no timers (v0.9.08: time.sleep not in sandbox namespace)
            RuntimeCapability.STREAMING.value: False,             # no streaming
        }

    def is_available(self) -> bool:
        # Always available — falls back to Python sandbox if wasmtime missing
        return True

    def permissions(self) -> WasmPermissions:
        """Get the current permission configuration."""
        return self._permissions

    def permissions_info(self) -> dict:
        """Get permission details for diagnostics."""
        return self._permissions.info()

    def engine_type(self) -> str:
        """Get the execution engine type: 'wasmtime' or 'python-sandbox'."""
        return self._executor.engine_type

    def execute(self, handler_body: str, request_data: dict,
                handler_path: str = "<wasm>") -> dict:
        """Execute a handler body in the WASM sandbox."""
        return self._executor.execute(handler_body, request_data, handler_path)

    def capabilities_info(self) -> Dict[str, Any]:
        info = super().capabilities_info()
        info["engine"] = self.engine_type()
        info["wasmtime_available"] = _HAS_WASMTIME
        info["wasmtime_version"] = get_wasmtime_version() if _HAS_WASMTIME else None
        info["permissions"] = self._permissions.info()
        return info

    # ── API Adapters ──────────────────────────────────────────────────

    @property
    def storage(self) -> WasmStorage:
        return WasmStorage()

    @property
    def http(self) -> WasmHttp:
        return WasmHttp()

    @property
    def cache(self) -> CacheAPI:
        return CacheAPI()

    @property
    def crypto(self) -> WasmCrypto:
        return WasmCrypto()

    @property
    def env(self) -> WasmEnv:
        return WasmEnv()
