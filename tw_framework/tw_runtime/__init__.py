"""
TW Framework — Multi-Runtime Abstraction Layer (v0.9.0)

Supports 4 runtimes:
  - nodejs  : Full Node.js (npm ecosystem, fs, native modules)
  - python  : Native Python (no Node.js needed, in-process)
  - edge    : TW's own (pre-warmed worker pool, limited capabilities)
  - wasm    : WebAssembly sandbox (maximum security, restricted)

Each runtime provides adapters for common APIs:
  tw.storage, tw.http, tw.db, tw.cache, tw.crypto, tw.env

Usage:
    from tw_framework.tw_runtime import get_runtime, list_runtimes
    runtime = get_runtime("edge")
    if runtime.supports("filesystem"):
        runtime.storage.read("data.json")
"""

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
]

# Register built-in adapters
from .adapters.node_adapter import NodeRuntime
from .adapters.python_adapter import PythonRuntime
from .adapters.edge_adapter import EdgeRuntime
from .adapters.wasm_adapter import WasmRuntime

RuntimeRegistry.register("nodejs", NodeRuntime)
RuntimeRegistry.register("node", NodeRuntime)       # alias
RuntimeRegistry.register("python", PythonRuntime)
RuntimeRegistry.register("edge", EdgeRuntime)
RuntimeRegistry.register("wasm", WasmRuntime)
