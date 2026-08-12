"""
TW Framework — Common API Abstractions (v0.9.0)

These are the `tw.*` APIs that developers use in .twm route handlers.
They delegate to the active runtime's adapter, so the same code works
across all runtimes:

    tw.storage.read("data.json")     # → fs on Node, os on Python, KV on Edge
    tw.http.fetch("https://api.com")  # → fetch on Node/Edge, requests on Python
    tw.crypto.hash("sha256", data)   # → crypto on Node, hashlib on Python
    tw.env.get("DATABASE_URL")       # → process.env / os.environ / platform
    tw.cache.get("key")              # → Memory/Redis/KV depending on runtime
    tw.db.query("SELECT * FROM users")  # → driver per runtime

Usage in .twm handlers:
    runtime = "python"

    fn get(request) {
        data = tw.storage.read("config.json")
        return { config: data }
    }

The `tw` object is a module-level singleton that auto-detects the active
runtime and delegates to its adapters.
"""

from __future__ import annotations
from typing import Any, Dict, List, Optional, Union
import json
import os
import time
import hashlib
import hmac
import secrets


class StorageAPI:
    """tw.storage — common file/storage operations.

    Each runtime adapter provides its own StorageAPI subclass that maps
    these methods to the underlying runtime's storage mechanism.
    """

    def read(self, path: str, encoding: str = "utf-8") -> Union[str, bytes]:
        """Read a file. Returns string if encoding is set, bytes if encoding=None."""
        raise NotImplementedError

    def write(self, path: str, data: Union[str, bytes]) -> bool:
        """Write data to a file. Returns True on success."""
        raise NotImplementedError

    def delete(self, path: str) -> bool:
        """Delete a file. Returns True on success."""
        raise NotImplementedError

    def exists(self, path: str) -> bool:
        """Check if a file exists."""
        raise NotImplementedError

    def list(self, dir_path: str, pattern: str = "*") -> List[str]:
        """List files in a directory matching a glob pattern."""
        raise NotImplementedError


class HttpAPI:
    """tw.http — common HTTP client operations."""

    def fetch(self, url: str, options: Optional[dict] = None) -> dict:
        """Fetch a URL. Returns {status, headers, text, data}.

        options: {method, headers, body, timeout}
        """
        raise NotImplementedError

    def get(self, url: str, headers: Optional[dict] = None, timeout: int = 30) -> dict:
        """GET request. Returns {status, headers, text, data}."""
        return self.fetch(url, {"method": "GET", "headers": headers or {}, "timeout": timeout})

    def post(self, url: str, body: Any = None, headers: Optional[dict] = None, timeout: int = 30) -> dict:
        """POST request. Returns {status, headers, text, data}."""
        return self.fetch(url, {"method": "POST", "headers": headers or {}, "body": body, "timeout": timeout})

    def put(self, url: str, body: Any = None, headers: Optional[dict] = None, timeout: int = 30) -> dict:
        return self.fetch(url, {"method": "PUT", "headers": headers or {}, "body": body, "timeout": timeout})

    def patch(self, url: str, body: Any = None, headers: Optional[dict] = None, timeout: int = 30) -> dict:
        return self.fetch(url, {"method": "PATCH", "headers": headers or {}, "body": body, "timeout": timeout})

    def delete(self, url: str, headers: Optional[dict] = None, timeout: int = 30) -> dict:
        return self.fetch(url, {"method": "DELETE", "headers": headers or {}, "timeout": timeout})


class DatabaseAPI:
    """tw.db — common database operations.

    Each runtime adapter maps this to its own database driver.
    """

    def query(self, sql: str, params: Optional[list] = None) -> List[dict]:
        """Execute a SQL query. Returns list of row dicts."""
        raise NotImplementedError

    def query_one(self, sql: str, params: Optional[list] = None) -> Optional[dict]:
        """Execute a SQL query, return first row or None."""
        rows = self.query(sql, params)
        return rows[0] if rows else None

    def execute(self, sql: str, params: Optional[list] = None) -> int:
        """Execute a SQL statement (INSERT/UPDATE/DELETE). Returns affected rows."""
        raise NotImplementedError

    def transaction(self, callback) -> Any:
        """Run a callback inside a database transaction."""
        raise NotImplementedError


class CacheAPI:
    """tw.cache — common caching operations.

    Node   → Memory / Redis
    Python → Memory / Redis
    Edge   → KV / Edge Cache
    WASM   → Host-provided storage
    """

    _store: Dict[str, Any] = {}  # in-memory fallback

    def get(self, key: str, default: Any = None) -> Any:
        """Get a cached value by key."""
        return self._store.get(key, default)

    def set(self, key: str, value: Any, ttl: int = 0) -> bool:
        """Set a cached value. ttl in seconds (0 = no expiry)."""
        self._store[key] = value
        return True

    def delete(self, key: str) -> bool:
        """Delete a cached value."""
        return self._store.pop(key, None) is not None

    def has(self, key: str) -> bool:
        """Check if a key exists in cache."""
        return key in self._store

    def clear(self) -> bool:
        """Clear all cached values."""
        self._store.clear()
        return True


class CryptoAPI:
    """tw.crypto — common cryptographic operations.

    Node   → Node crypto
    Python → hashlib / hmac / secrets
    Edge   → Web Crypto API
    WASM   → Host implementation
    """

    def hash(self, algorithm: str, data: Union[str, bytes]) -> str:
        """Hash data using the given algorithm (sha256, sha512, md5, etc.)."""
        if isinstance(data, str):
            data = data.encode("utf-8")
        h = hashlib.new(algorithm)
        h.update(data)
        return h.hexdigest()

    def hmac(self, algorithm: str, key: Union[str, bytes], message: Union[str, bytes]) -> str:
        """Compute HMAC."""
        if isinstance(key, str):
            key = key.encode("utf-8")
        if isinstance(message, str):
            message = message.encode("utf-8")
        return hmac.new(key, message, algorithm).hexdigest()

    def random(self, length: int = 32) -> str:
        """Generate a random hex string."""
        return secrets.token_hex(length)

    def random_bytes(self, length: int = 32) -> bytes:
        """Generate random bytes."""
        return secrets.token_bytes(length)

    def uuid(self) -> str:
        """Generate a UUID4 string."""
        import uuid
        return str(uuid.uuid4())

    def encrypt(self, algorithm: str, key: bytes, data: bytes) -> bytes:
        """Encrypt data. (Runtime-specific implementations may vary.)"""
        raise NotImplementedError(f"encrypt() not implemented for algorithm {algorithm}")

    def decrypt(self, algorithm: str, key: bytes, data: bytes) -> bytes:
        """Decrypt data."""
        raise NotImplementedError(f"decrypt() not implemented for algorithm {algorithm}")


class EnvAPI:
    """tw.env — common environment variable access.

    Node   → process.env
    Python → os.environ
    Edge   → platform environment (limited)
    WASM   → host-provided values
    """

    def get(self, name: str, default: str = "") -> str:
        """Get an environment variable."""
        return os.environ.get(name, default)

    def all(self) -> Dict[str, str]:
        """Get all environment variables."""
        return dict(os.environ)

    def has(self, name: str) -> bool:
        """Check if an environment variable exists."""
        return name in os.environ

    def get_int(self, name: str, default: int = 0) -> int:
        """Get an environment variable as int."""
        try:
            return int(os.environ.get(name, str(default)))
        except (ValueError, TypeError):
            return default

    def get_bool(self, name: str, default: bool = False) -> bool:
        """Get an environment variable as bool."""
        val = os.environ.get(name, "").lower()
        if val in ("1", "true", "yes", "on"):
            return True
        if val in ("0", "false", "no", "off", ""):
            return default
        return bool(val)


class RuntimeInfoAPI:
    """tw.runtime — runtime introspection.

    tw.runtime.name()         → "edge", "nodejs", "python", "wasm"
    tw.runtime.version()      → "18.17.0", "3.12.0", etc.
    tw.runtime.capabilities() → {"filesystem": False, "network": True, ...}
    tw.runtime.supports("filesystem")  → True/False
    """

    _runtime = None  # Set by the `tw` singleton

    def name(self) -> str:
        if self._runtime:
            return self._runtime.runtime_name
        return "unknown"

    def version(self) -> str:
        if self._runtime:
            return self._runtime.version
        return "unknown"

    def capabilities(self) -> Dict[str, bool]:
        if self._runtime:
            return self._runtime.capabilities()
        return {}

    def supports(self, capability: str) -> bool:
        if self._runtime:
            return self._runtime.supports(capability)
        return False

    def info(self) -> Dict[str, Any]:
        if self._runtime:
            return self._runtime.capabilities_info()
        return {"runtime": "unknown"}


class TWAPI:
    """The `tw` singleton — provides access to all common APIs.

    Usage in .twm handlers:
        tw.storage.read("config.json")
        tw.http.fetch("https://api.example.com")
        tw.crypto.hash("sha256", "hello")
        tw.env.get("DATABASE_URL")
        tw.cache.get("user:123")
        tw.runtime.name()
    """

    def __init__(self):
        self._runtime = None
        self._storage = StorageAPI()
        self._http = HttpAPI()
        self._db = DatabaseAPI()
        self._cache = CacheAPI()
        self._crypto = CryptoAPI()
        self._env = EnvAPI()
        self._runtime_info = RuntimeInfoAPI()

    def set_runtime(self, runtime) -> None:
        """Set the runtime and bind all API implementations.
        v0.9.08 FIX: Uses loop instead of 6 copy-paste try/except blocks.
        """
        for attr in ("storage", "http", "db", "cache", "crypto", "env"):
            if hasattr(runtime, attr) and getattr(runtime, attr) is not None:
                try:
                    setattr(self, "_" + attr, getattr(runtime, attr))
                except NotImplementedError:
                    pass

    def storage(self) -> StorageAPI:
        return self._storage

    @property
    def http(self) -> HttpAPI:
        return self._http

    @property
    def db(self) -> DatabaseAPI:
        return self._db

    @property
    def cache(self) -> CacheAPI:
        return self._cache

    @property
    def crypto(self) -> CryptoAPI:
        return self._crypto

    @property
    def env(self) -> EnvAPI:
        return self._env

    @property
    def runtime(self) -> RuntimeInfoAPI:
        return self._runtime_info


# Module-level singleton
tw = TWAPI()
