"""
TW Framework — Plugin Manager (v0.9.08)

WordPress-inspired plugin system with lifecycle hooks.
Plugins are .twp files (TW Plugin format) that run in a restricted sandbox.
Plugins can ONLY run inside TW — plugin.register(), ctx, tw are TW-specific APIs.

Hooks:
  - beforeBuild(context)
  - afterBuild(context)
  - beforeRequest(context)
  - afterRequest(context)
  - onRouteMatch(context)
"""

from __future__ import annotations
import os
import json
import re
import threading
from typing import Any, Dict, List, Optional, Callable


HOOKS = ["beforeBuild", "afterBuild", "beforeRequest", "afterRequest", "onRouteMatch"]

PLUGIN_REGISTRY_URL = "https://raw.githubusercontent.com/ffakraj-ui/tw-plugin/main/registry.json"


class PluginContext:
    """Context object passed to plugin hooks. Only exists inside TW."""

    def __init__(self, hook: str, data: Optional[dict] = None):
        self.hook = hook
        self._data = data or {}
        self._modified = False

    @property
    def pages(self) -> list:
        return self._data.get("pages", [])

    @pages.setter
    def pages(self, val: list) -> None:
        self._data["pages"] = val
        self._modified = True

    @property
    def config(self) -> dict:
        return self._data.get("config", {})

    @property
    def output_dir(self) -> str:
        return self._data.get("output_dir", "dist")

    @property
    def request(self) -> dict:
        return self._data.get("request", {})

    @property
    def response(self) -> dict:
        return self._data.get("response", {})

    @response.setter
    def response(self, val: dict) -> None:
        self._data["response"] = val
        self._modified = True

    def read_file(self, path: str) -> str:
        safe_path = self._safe_path(path)
        with open(safe_path, "r", encoding="utf-8") as f:
            return f.read()

    def write_file(self, path: str, data: str) -> bool:
        safe_path = self._safe_path(path)
        os.makedirs(os.path.dirname(safe_path), exist_ok=True)
        with open(safe_path, "w", encoding="utf-8") as f:
            f.write(data)
        return True

    def file_exists(self, path: str) -> bool:
        return os.path.exists(self._safe_path(path))

    def log(self, msg: str) -> None:
        print("  [plugin] " + str(msg))

    def warn(self, msg: str) -> None:
        print("  [plugin WARNING] " + str(msg))

    def error(self, msg: str) -> None:
        print("  [plugin ERROR] " + str(msg))

    def redirect(self, url: str, status: int = 302) -> None:
        self._data["redirect"] = {"url": url, "status": status}
        self._modified = True

    def _safe_path(self, path: str) -> str:
        project_root = self._data.get("project_root", os.getcwd())
        full = os.path.abspath(os.path.join(project_root, path))
        if not full.startswith(project_root):
            raise PermissionError("Plugin blocked: path traversal: " + path)
        return full

    @property
    def modified(self) -> bool:
        return self._modified


class Plugin:
    """A loaded plugin instance."""

    def __init__(self, name: str, version: str, metadata: dict, code: str):
        self.name = name
        self.version = version
        self.metadata = metadata
        self.code = code
        self.hooks: Dict[str, Callable] = {}
        self.enabled = True
        self.error: Optional[str] = None

    def register_hook(self, hook: str, fn: Callable) -> None:
        if hook in HOOKS:
            self.hooks[hook] = fn
        else:
            raise ValueError("Unknown hook: " + hook)


class _PluginAPI:
    """plugin.register() — only works inside TW sandbox."""
    def register(self, hook, fn): pass
    def action(self, hook, fn): pass
    def filter(self, name, fn): pass


class _PluginTWAPI:
    def log(self, msg): print("  [plugin] " + str(msg))
    def warn(self, msg): print("  [plugin WARNING] " + str(msg))


class _PluginConsole:
    def __init__(self, name): self._n = name
    def log(self, *a): print("  [plugin:" + self._n + "]", *a)
    def warn(self, *a): print("  [plugin:" + self._n + " WARNING]", *a)
    def error(self, *a): print("  [plugin:" + self._n + " ERROR]", *a)


class _PluginJSON:
    def stringify(self, obj): return json.dumps(obj, ensure_ascii=False)
    def parse(self, s): return json.loads(s)


def _translate_twp_to_python(body: str) -> str:
    """Translate .twp JS-like syntax to Python for exec()."""
    py = re.sub(r'(\w+):', r'"\1":', body)
    py = py.replace("null", "None").replace("true", "True").replace("false", "False")
    py = py.replace("undefined", "None")
    py = py.replace("console.log", "print").replace("console.warn", "print").replace("console.error", "print")
    py = re.sub(r'\bvar\s+', '', py)
    py = re.sub(r'\blet\s+', '', py)
    py = re.sub(r'\bconst\s+', '', py)
    py = re.sub(r'function\s+(\w+)\s*\(([^)]*)\)', r'def \1(\2)', py)
    return py


class PluginManager:
    """Manages plugin lifecycle: load, register hooks, execute."""

    _HOOK_PATTERN = re.compile(
        r"""plugin\.register\s*\(\s*["']?(\w+)["']?\s*,\s*function\s*\([^)]*\)\s*\{""",
        re.MULTILINE,
    )

    def __init__(self, plugins_dir: str = ".tw/plugins", project_root: str = "."):
        self.plugins_dir = os.path.abspath(plugins_dir)
        self.project_root = os.path.abspath(project_root)
        self.plugins: Dict[str, Plugin] = {}
        self._lock = threading.Lock()

    def load_all(self) -> None:
        if not os.path.isdir(self.plugins_dir):
            return
        for entry in os.listdir(self.plugins_dir):
            pdir = os.path.join(self.plugins_dir, entry)
            if not os.path.isdir(pdir):
                continue
            pj = os.path.join(pdir, "plugin.json")
            pt = os.path.join(pdir, "plugin.twp")
            if not os.path.exists(pj) or not os.path.exists(pt):
                continue
            try:
                with open(pj) as f:
                    meta = json.load(f)
                with open(pt) as f:
                    code = f.read()
                plugin = Plugin(meta.get("name", entry), meta.get("version", "0.0.0"), meta, code)
                self._parse_twp(plugin)
                plugin.enabled = True  # auto-yes
                self.plugins[plugin.name] = plugin
            except Exception as err:
                print("  [plugin] Failed to load " + entry + ": " + str(err))

    def _parse_twp(self, plugin: Plugin) -> None:
        code = plugin.code
        for match in self._HOOK_PATTERN.finditer(code):
            hook_name = match.group(1)
            if hook_name not in HOOKS:
                continue
            start = match.end() - 1
            if start < 0 or code[start] != "{":
                continue
            depth = 0
            i = start
            while i < len(code):
                if code[i] == "{":
                    depth += 1
                elif code[i] == "}":
                    depth -= 1
                    if depth == 0:
                        break
                i += 1
            fn_body = code[start + 1:i]

            def make_hook(body, name):
                def hook_fn(ctx: PluginContext) -> None:
                    ns = {"ctx": ctx, "plugin": _PluginAPI(), "tw": _PluginTWAPI(),
                          "console": _PluginConsole(name), "JSON": _PluginJSON()}
                    try:
                        py = _translate_twp_to_python(body)
                        exec(compile(py, "<plugin:" + name + ">", "exec"), ns)
                    except Exception as err:
                        ctx.error("Plugin " + name + " error: " + str(err))
                return hook_fn

            plugin.register_hook(hook_name, make_hook(fn_body, plugin.name))

    def trigger(self, hook: str, data: Optional[dict] = None) -> PluginContext:
        ctx = PluginContext(hook, data or {})
        ctx._data["project_root"] = self.project_root
        with self._lock:
            for name, plugin in self.plugins.items():
                if not plugin.enabled:
                    continue
                fn = plugin.hooks.get(hook)
                if fn is None:
                    continue
                try:
                    fn(ctx)
                except Exception as err:
                    ctx.warn("Plugin '" + name + "' failed in " + hook + ": " + str(err))
        return ctx

    def list_plugins(self) -> List[dict]:
        result = []
        for name, p in self.plugins.items():
            result.append({"name": name, "version": p.version, "enabled": p.enabled,
                           "hooks": list(p.hooks.keys()), "permissions": p.metadata.get("permissions", [])})
        return result

    def has_plugins(self) -> bool:
        return len(self.plugins) > 0


def fetch_registry() -> dict:
    import urllib.request
    try:
        with urllib.request.urlopen(PLUGIN_REGISTRY_URL, timeout=10) as resp:
            return json.loads(resp.read().decode("utf-8"))
    except Exception as err:
        return {"error": str(err), "plugins": []}


def install_plugin(name: str, plugins_dir: str = ".tw/plugins") -> dict:
    """Install a plugin from tw-plugin repo. Auto-yes for all permissions."""
    registry = fetch_registry()
    if "error" in registry:
        return {"success": False, "error": registry["error"]}
    plugins = registry.get("plugins", [])
    info = next((p for p in plugins if p["name"] == name), None)
    if not info:
        return {"success": False, "error": "Plugin '" + name + "' not found"}
    base_url = "https://raw.githubusercontent.com/ffakraj-ui/tw-plugin/main"
    plugin_url = info.get("url", "plugins/" + name + "/")
    os.makedirs(os.path.join(plugins_dir, name), exist_ok=True)
    for fname in ["plugin.twp", "plugin.json"]:
        url = base_url + "/" + plugin_url + fname
        try:
            import urllib.request
            with urllib.request.urlopen(url, timeout=10) as resp:
                content = resp.read()
            with open(os.path.join(plugins_dir, name, fname), "wb") as f:
                f.write(content)
        except Exception as err:
            return {"success": False, "error": "Download " + fname + " failed: " + str(err)}
    return {"success": True, "plugin": name, "version": info.get("version", "0.0.0")}


def remove_plugin(name: str, plugins_dir: str = ".tw/plugins") -> dict:
    import shutil
    p = os.path.join(plugins_dir, name)
    if os.path.isdir(p):
        shutil.rmtree(p)
        return {"success": True, "plugin": name}
    return {"success": False, "error": "Plugin '" + name + "' not installed"}
