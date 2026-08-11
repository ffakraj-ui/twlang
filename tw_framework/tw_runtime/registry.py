"""
TW Framework — Runtime Registry (v0.9.0)

Central registry for all runtime adapters. `get_runtime("edge")` returns
the EdgeRuntime adapter instance, etc.
"""

from __future__ import annotations
import threading
from typing import Dict, List, Optional, Type


DEFAULT_RUNTIME = "nodejs"


class RuntimeRegistry:
    """Registry of available runtime adapters."""

    _registry: Dict[str, type] = {}
    _instances: Dict[str, object] = {}
    _lock = threading.Lock()  # v0.9.08 FIX #6: Thread safety

    @classmethod
    def register(cls, name: str, runtime_class: type) -> None:
        """Register a runtime adapter class by name."""
        with cls._lock:  # v0.9.08 FIX #6: Thread-safe
            cls._registry[name] = runtime_class
            # Clear cached instance so next get() creates a fresh one
            cls._instances.pop(name, None)

    @classmethod
    def get(cls, name: str) -> Optional[object]:
        """Get a runtime instance by name. Returns None if not registered."""
        name = name.lower().strip()
        with cls._lock:  # v0.9.08 FIX #6: Thread-safe
            # Check cache
            if name in cls._instances:
                return cls._instances[name]
            # Create new instance
            runtime_class = cls._registry.get(name)
            if runtime_class is None:
                return None
            instance = runtime_class()
            cls._instances[name] = instance
            return instance

    @classmethod
    def list_names(cls) -> List[str]:
        """List all registered runtime names."""
        return sorted(cls._registry.keys())

    @classmethod
    def list_available(cls) -> List[str]:
        """List runtimes that are available (dependencies installed)."""
        available = []
        for name in cls._registry:
            instance = cls.get(name)
            if instance and instance.is_available():
                available.append(name)
        return available

    @classmethod
    def clear_cache(cls) -> None:
        """Clear cached instances (used on hot-reload)."""
        with cls._lock:
            cls._instances.clear()


def get_runtime(name: str = DEFAULT_RUNTIME):
    """Get a runtime adapter instance by name.

    Args:
        name: Runtime name ("nodejs", "python", "edge", "wasm")
    Returns:
        Runtime adapter instance, or None if not found

    v0.9.08 FIX #20: Use get_runtime_or_raise() if you want an error on unknown runtime.
    """
    return RuntimeRegistry.get(name)


def get_runtime_or_raise(name: str = DEFAULT_RUNTIME):
    """Get a runtime adapter instance by name, raising ValueError if not found.

    v0.9.08 FIX #20: Unlike get_runtime(), this raises instead of returning None.
    """
    instance = RuntimeRegistry.get(name)
    if instance is None:
        available = RuntimeRegistry.list_names()
        raise ValueError(
            f"Unknown runtime: {name!r}. "
            f"Available runtimes: {', '.join(available) if available else 'none registered'}"
        )
    return instance


def list_runtimes() -> List[str]:
    """List all registered runtime names."""
    return RuntimeRegistry.list_names()
