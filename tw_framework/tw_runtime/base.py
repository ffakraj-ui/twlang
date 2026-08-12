"""
TW Framework — Base Runtime & Capability System (v0.9.0)

Every runtime adapter inherits from BaseRuntime and declares its capabilities.
The capability system drives build-time validation: if a .twm route uses
an API that requires a capability the selected runtime doesn't have, TW
raises a clear build-time error instead of crashing at runtime.
"""

from __future__ import annotations
from abc import ABC, abstractmethod
from enum import Enum
from typing import Any, Dict, List, Optional


class RuntimeCapability(str, Enum):
    """Capabilities a runtime may or may not support."""
    FILESYSTEM = "filesystem"
    NETWORK = "network"
    NATIVE_MODULES = "native_modules"
    SUBPROCESS = "subprocess"
    DATABASE = "database"
    CRYPTO = "crypto"
    CACHE = "cache"
    ENV_VARS = "env_vars"
    PERSISTENT_STORAGE = "persistent_storage"
    TIMERS = "timers"
    STREAMING = "streaming"


# Human-readable descriptions for error messages
CAPABILITIES = {
    RuntimeCapability.FILESYSTEM: "File system access (read/write files)",
    RuntimeCapability.NETWORK: "Network access (HTTP requests, fetch)",
    RuntimeCapability.NATIVE_MODULES: "Native addon / npm package support",
    RuntimeCapability.SUBPROCESS: "Spawn child processes",
    RuntimeCapability.DATABASE: "Direct database connections",
    RuntimeCapability.CRYPTO: "Cryptographic operations (hash, encrypt, random)",
    RuntimeCapability.CACHE: "In-memory or external caching",
    RuntimeCapability.ENV_VARS: "Environment variable access",
    RuntimeCapability.PERSISTENT_STORAGE: "Persistent key-value storage",
    RuntimeCapability.TIMERS: "setTimeout / setInterval / scheduling",
    RuntimeCapability.STREAMING: "Streaming responses (SSE, chunked transfer)",
}


class BaseRuntime(ABC):
    """Abstract base class for all runtime adapters.

    Subclasses MUST override:
      - name()
      - capabilities()
      - The storage/http/db/cache/crypto/env properties (or accept defaults)

    Subclasses MAY override:
      - version()  (default: "unknown")
      - execute()   (default: raise NotImplementedError)
    """

    @property
    def runtime_name(self) -> str:
        """Short name: 'nodejs', 'python', 'edge', 'wasm'."""
        raise NotImplementedError

    @property
    def display_name(self) -> str:
        """Human-friendly name: 'Node.js', 'Python', etc."""
        return self.runtime_name

    @property
    def version(self) -> str:
        """Runtime version string, or 'unknown'."""
        return "unknown"

    def capabilities(self) -> Dict[str, bool]:
        """Return a dict of capability → True/False.

        Example:
            {"filesystem": True, "network": True, "native_modules": True, ...}
        """
        return {cap.value: False for cap in RuntimeCapability}

    def supports(self, capability: str) -> bool:
        """Check if this runtime supports a given capability.

        Args:
            capability: A RuntimeCapability value or string (e.g. "filesystem")
        Returns:
            True if the capability is supported
        """
        caps = self.capabilities()
        return caps.get(capability, False)

    def capabilities_list(self) -> List[str]:
        """Return list of supported capability names."""
        return [k for k, v in self.capabilities().items() if v]

    def capabilities_info(self) -> Dict[str, Any]:
        """Return detailed info dict for tw info / diagnostics."""
        caps = self.capabilities()
        return {
            "runtime": self.runtime_name,
            "version": self.version,
            "capabilities": caps,
            "supported": [k for k, v in caps.items() if v],
            "unsupported": [k for k, v in caps.items() if not v],
        }

    # ── API adapter properties (subclasses override) ──────────────────

    @property
    def storage(self):
        """tw.storage adapter — read(), write(), delete(), list()."""
        raise NotImplementedError(f"{self.runtime_name} does not implement tw.storage")

    @property
    def http(self):
        """tw.http adapter — fetch(), get(), post(), etc."""
        raise NotImplementedError(f"{self.runtime_name} does not implement tw.http")

    @property
    def db(self):
        """tw.db adapter — query(), transaction()."""
        raise NotImplementedError(f"{self.runtime_name} does not implement tw.db")

    @property
    def cache(self):
        """tw.cache adapter — get(), set(), delete()."""
        raise NotImplementedError(f"{self.runtime_name} does not implement tw.cache")

    @property
    def crypto(self):
        """tw.crypto adapter — hash(), random(), encrypt(), decrypt()."""
        raise NotImplementedError(f"{self.runtime_name} does not implement tw.crypto")

    @property
    def env(self):
        """tw.env adapter — get(), all()."""
        raise NotImplementedError(f"{self.runtime_name} does not implement tw.env")

    # ── Execution ──────────────────────────────────────────────────────

    def execute(self, handler_path: str, method: str, url_path: str,
                headers: dict, body: Any, request_data: dict) -> Optional[dict]:
        """Execute a .twm handler on this runtime.

        Returns a response dict {status, body, content_type, headers, cookies}
        or None if this runtime cannot handle the request.

        v0.9.17 FIX: Was @abstractmethod — prevented instantiation of NodeRuntime,
        PythonRuntime, EdgeRuntime, EdgeV8Runtime. Now has a default impl that
        raises NotImplementedError. Runtimes that support direct execution
        (EdgeV8, WASM) override this.
        """
        raise NotImplementedError(
            f"{self.runtime_name} runtime does not implement direct execution. "
            f"Use the framework's execute_api_route() dispatcher instead."
        )

    def is_available(self) -> bool:
        """Check if this runtime's dependencies are installed and ready."""
        return True

    def __repr__(self) -> str:
        return f"<{self.__class__.__name__} name={self.runtime_name!r} version={self.version!r}>"
