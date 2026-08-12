"""
TW Framework — Extensions (plugin system).

Thin re-export of plugin_runtime.ExtensionManager for convenience.
Full plugin system lives in plugin_runtime.py.
"""
from .plugin_runtime import ExtensionManager, PluginManager

__all__ = ["ExtensionManager", "PluginManager"]
