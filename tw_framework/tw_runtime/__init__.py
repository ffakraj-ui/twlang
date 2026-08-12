"""
TW Framework — Multi-Runtime Abstraction Layer (v0.9.27)

Supports 5 runtimes:
  - nodejs  : Full Node.js (npm ecosystem, fs, native modules)
  - python  : Native Python (no Node.js needed, in-process)
  - edge    : V8 JS sandbox (real JavaScript via py_mini_racer)
  - edge-py : Legacy Python in-process edge (fallback)
  - wasm    : WebAssembly sandbox (maximum security, restricted)

Each runtime provides adapters for common APIs:
  tw.storage, tw.http, tw.db, tw.cache, tw.crypto, tw.env

Usage:
    from tw_framework.tw_runtime import get_runtime, list_runtimes
    runtime = get_runtime("edge")
    if runtime.supports("filesystem"):
        runtime.storage.read("data.json")
"""

# FIX #699: Add module version
__version__ = "0.9.27"

from .base import BaseRuntime, RuntimeCapability, CAPABILITIES
from .abstractions import tw
from .registry import get_runtime, list_runtimes, DEFAULT_RUNTIME, RuntimeRegistry
from .validator import validate_runtime_compatibility, RuntimeValidationError

__all__ = [
    "BaseRuntime",
    "RuntimeCapability",
    "CAPABILITIES",
    "tw",
    "get_runtime",
    "list_runtimes",
    "DEFAULT_RUNTIME",
    "RuntimeRegistry",
    "validate_runtime_compatibility",
    "RuntimeValidationError",
    "register_runtimes",
    "__version__",
]

# v0.9.08 FIX #18: Registration moved to register_runtimes() to avoid
# import side effects (circular imports, eager loading). Call explicitly:
#   from tw_framework.tw_runtime import register_runtimes
#   register_runtimes()
# Or it's auto-called on first get_runtime() call.
_REGISTERED = False
# FIX #695: Use a threading lock for thread-safe registration
import threading as _threading
_REGISTER_LOCK = _threading.Lock()


def register_runtimes():
    """Register all built-in runtime adapters.

    v0.9.08 FIX #18: Called lazily to avoid import-time side effects.
    Safe to call multiple times (idempotent).
    FIX #695: Thread-safe via lock.
    """
    global _REGISTERED
    if _REGISTERED:
        return
    with _REGISTER_LOCK:
        if _REGISTERED:  # Double-check after acquiring lock
            return
    from .adapters.node_adapter import NodeRuntime
    from .adapters.python_adapter import PythonRuntime
    from .adapters.edge_adapter import EdgeRuntime
    from .adapters.edge_v8_adapter import EdgeV8Runtime
    from .adapters.wasm_adapter import WasmRuntime

    RuntimeRegistry.register("nodejs", NodeRuntime)
    RuntimeRegistry.register("node", NodeRuntime)       # alias
    RuntimeRegistry.register("python", PythonRuntime)
    RuntimeRegistry.register("edge", EdgeV8Runtime)
    RuntimeRegistry.register("edge-v8", EdgeV8Runtime)  # alias
    RuntimeRegistry.register("edge-py", EdgeRuntime)    # legacy Python edge
    RuntimeRegistry.register("wasm", WasmRuntime)
    _REGISTERED = True


# FIX #692: Auto-register on import (backward compatibility).
# Note: register_runtimes() is idempotent, so calling it here is safe
# even if something else calls it later. The _REGISTERED flag prevents
# double-registration.
register_runtimes()
