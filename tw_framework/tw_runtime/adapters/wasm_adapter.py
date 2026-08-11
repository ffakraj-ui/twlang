"""
TW Framework — WASM Runtime Adapter (v0.9.0)

WebAssembly runtime: maximum security sandbox. All capabilities depend
on the host (wasmtime). By default, nothing is allowed unless explicitly
granted (like Deno's permission system).

This is the most restricted runtime — ideal for running untrusted code,
processing user-uploaded scripts, or computing in a secure sandbox.

Future: .twm handlers compiled to WASM for sub-millisecond cold start.
Current: falls back to Python execution with restricted capabilities.
"""

from __future__ import annotations
import os
import sys
import hashlib
import hmac
import secrets
import json
from typing import Any, Dict, List, Optional, Union

from ..base import BaseRuntime, RuntimeCapability
from ..abstractions import StorageAPI, HttpAPI, CryptoAPI, EnvAPI, CacheAPI


class WasmStorage(StorageAPI):
    """WASM storage adapter — uses host-provided storage (restricted).

    Like Deno's --allow-read: only specific directories are accessible.
    Defaults to a sandboxed temp directory.
    """

    _sandbox_dir: str = ""

    def _get_sandbox(self) -> str:
        if not self._sandbox_dir:
            self._sandbox_dir = os.path.join(
                os.environ.get("TW_WASM_SANDBOX", os.path.join(os.path.dirname(__file__), "..", "..", "..", ".tw", "wasm_sandbox")),
            )
            os.makedirs(self._sandbox_dir, exist_ok=True)
        return self._sandbox_dir

    def read(self, path: str, encoding: str = "utf-8") -> Union[str, bytes]:
        sandbox = self._get_sandbox()
        # Only allow reads within the sandbox
        full_path = os.path.abspath(os.path.join(sandbox, path))
        if not full_path.startswith(sandbox):
            raise PermissionError(f"WASM sandbox: cannot read outside sandbox: {path}")
        mode = "r" if encoding else "rb"
        with open(full_path, mode, encoding=encoding if encoding else None) as f:
            return f.read()

    def write(self, path: str, data: Union[str, bytes]) -> bool:
        sandbox = self._get_sandbox()
        full_path = os.path.abspath(os.path.join(sandbox, path))
        if not full_path.startswith(sandbox):
            raise PermissionError(f"WASM sandbox: cannot write outside sandbox: {path}")
        os.makedirs(os.path.dirname(full_path), exist_ok=True)
        mode = "w" if isinstance(data, str) else "wb"
        with open(full_path, mode, encoding="utf-8" if mode == "w" else None) as f:
            f.write(data)
        return True

    def delete(self, path: str) -> bool:
        sandbox = self._get_sandbox()
        full_path = os.path.abspath(os.path.join(sandbox, path))
        if not full_path.startswith(sandbox):
            raise PermissionError(f"WASM sandbox: cannot delete outside sandbox: {path}")
        try:
            os.remove(full_path)
            return True
        except FileNotFoundError:
            return False

    def exists(self, path: str) -> bool:
        sandbox = self._get_sandbox()
        full_path = os.path.abspath(os.path.join(sandbox, path))
        if not full_path.startswith(sandbox):
            return False
        return os.path.exists(full_path)

    def list(self, dir_path: str, pattern: str = "*") -> List[str]:
        import glob
        sandbox = self._get_sandbox()
        full_path = os.path.abspath(os.path.join(sandbox, dir_path))
        if not full_path.startswith(sandbox):
            return []
        return glob.glob(os.path.join(full_path, pattern))


class WasmCrypto(CryptoAPI):
    """WASM crypto adapter — uses Python hashlib (host-provided)."""

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


class WasmEnv(EnvAPI):
    """WASM env adapter — only explicitly granted env vars.

    Like Deno's --allow-env: only specific variables are exposed.
    """

    _allowed: set = set()

    def allow(self, name: str) -> None:
        """Grant access to a specific env var."""
        self._allowed.add(name)

    def get(self, name: str, default: str = "") -> str:
        if name not in self._allowed and "*" not in self._allowed:
            return default
        return os.environ.get(name, default)

    def all(self) -> Dict[str, str]:
        if "*" in self._allowed:
            return dict(os.environ)
        return {k: os.environ.get(k, "") for k in self._allowed if k in os.environ}


class WasmRuntime(BaseRuntime):
    """WASM runtime — maximum security sandbox.

    All capabilities depend on host permissions (like Deno):
    - Filesystem: only sandboxed directory
    - Network: disabled by default
    - Native modules: never
    - Subprocess: never
    - Crypto: host-provided
    - Cache: in-memory only

    Best for: untrusted code, secure computation, plugin systems
    """

    @property
    def runtime_name(self) -> str:
        return "wasm"

    @property
    def display_name(self) -> str:
        return "WASM"

    @property
    def version(self) -> str:
        # Check if wasmtime is available
        try:
            import wasmtime
            return f"wasmtime/{wasmtime.__version__}"
        except (ImportError, AttributeError):
            return "wasm-host/python"

    def capabilities(self) -> Dict[str, bool]:
        return {
            RuntimeCapability.FILESYSTEM.value: True,            # ✅ sandboxed only
            RuntimeCapability.NETWORK.value: False,              # ❌ disabled by default
            RuntimeCapability.NATIVE_MODULES.value: False,       # ❌ never
            RuntimeCapability.SUBPROCESS.value: False,           # ❌ never
            RuntimeCapability.DATABASE.value: False,             # ❌ disabled by default
            RuntimeCapability.CRYPTO.value: True,                 # ✅ host-provided
            RuntimeCapability.CACHE.value: True,                 # ✅ in-memory
            RuntimeCapability.ENV_VARS.value: True,              # ✅ granted only
            RuntimeCapability.PERSISTENT_STORAGE.value: True,    # ✅ sandbox
            RuntimeCapability.TIMERS.value: False,               # ❌ no timers
            RuntimeCapability.STREAMING.value: False,            # ❌ no streaming
        }

    def is_available(self) -> bool:
        return True  # Falls back to Python with restrictions

    # ── API Adapters ──────────────────────────────────────────────────

    @property
    def storage(self) -> WasmStorage:
        return WasmStorage()

    @property
    def http(self) -> HttpAPI:
        # WASM: no network by default
        raise NotImplementedError(
            "WASM runtime does not support network access by default. "
            "Use runtime = 'edge' or runtime = 'nodejs' for HTTP requests."
        )

    @property
    def cache(self) -> CacheAPI:
        return CacheAPI()

    @property
    def crypto(self) -> WasmCrypto:
        return WasmCrypto()

    @property
    def env(self) -> WasmEnv:
        return WasmEnv()
