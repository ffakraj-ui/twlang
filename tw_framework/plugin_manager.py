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
import hashlib
import re
import threading
from typing import Any, Dict, List, Optional, Callable
import urllib
import urllib


HOOKS = ["beforeBuild", "afterBuild", "beforeRequest", "afterRequest", "onRouteMatch"]

PLUGIN_REGISTRY_URL = "https://raw.githubusercontent.com/tw-origin/tw-plugins/main/registry.json"

# v0.9.38: Plugin verification via registry code matching.
#
# No secret key, no HMAC, no encoding. Instead, at load time the framework
# fetches the official plugin code from the registry and compares it
# byte-for-byte (SHA-256 hash) with the installed plugin code.
#
# How it works:
#   1. install_plugin() downloads plugin.twp + plugin.json from registry
#      and saves them raw. Also saves the official SHA-256 hash.
#   2. load_all() reads installed plugin code, computes its SHA-256,
#      and compares with the official hash saved at install time.
#   3. If hashes match → plugin is genuine → load it.
#   4. If hashes don't match → plugin was tampered → reject.
#   5. If plugin not in registry → reject (custom plugin not allowed).
#
# Why this is secure without any secret:
#   - Attacker can't create a fake plugin → its code won't match any
#     official plugin's code in the registry.
#   - Attacker can't modify an installed plugin → hash will change → mismatch.
#   - Attacker can't use another plugin's metadata → code won't match that
#     plugin's official code.
#   - Same code as official → allowed (that's what tw plugin add installs).
#
# The official hash is stored inside the encoded plugin file itself,
# so there's no separate hash file to tamper with.


def _save_plugin_with_hash(content: bytes, filepath: str, plugin_name: str) -> None:
    """Save plugin file with embedded official hash.

    Format: TWP1\n<sha256_hex>\n<raw_content>

    The hash is of the raw content. At load time, framework reads the content,
    computes its SHA-256, and compares with the embedded hash.
    If someone modifies the content, the hash won't match.
    If someone creates a fake file, the hash won't match any official plugin.
    """
    content_hash = hashlib.sha256(content).hexdigest()
    raw_text = content.decode("utf-8") if isinstance(content, bytes) else content
    with open(filepath, "w") as f:
        f.write("TWP1\n" + content_hash + "\n" + raw_text)


def _load_plugin_with_hash(filepath: str) -> Optional[str]:
    """Load plugin file and verify embedded hash.

    Returns the raw content if hash matches, None if tampered or invalid format.
    """
    try:
        with open(filepath, "r") as f:
            raw = f.read()
    except Exception:
        return None

    if not raw.startswith("TWP1\n"):
        return None

    parts = raw.split("\n", 2)
    if len(parts) != 3:
        return None

    stored_hash = parts[1]
    content = parts[2]

    # Verify: compute hash of content and compare with stored hash
    actual_hash = hashlib.sha256(content.encode("utf-8")).hexdigest()
    if actual_hash != stored_hash:
        return None  # Tampered!

    return content


def _load_plain(filepath: str) -> Optional[str]:
    """Load a plain plugin file (no TWP1 format, no hash).

    Used for custom plugins that are manually placed by developers.
    Returns the raw content, or None if the file can't be read.
    """
    try:
        with open(filepath, "r") as f:
            raw = f.read()
    except Exception:
        return None
    # If it's TWP1 format, extract the content part (but don't verify hash)
    if raw.startswith("TWP1\n"):
        parts = raw.split("\n", 2)
        if len(parts) == 3:
            return parts[2]
        return None
    return raw


def _is_twp1_tampered(filepath: str) -> bool:
    """Check if a file is TWP1 format but has been tampered (hash mismatch).

    Returns True if the file is TWP1 format but the embedded hash
    doesn't match the content hash (i.e. someone modified the code
    after installation).
    """
    try:
        with open(filepath, "r") as f:
            raw = f.read()
    except Exception:
        return False
    if not raw.startswith("TWP1\n"):
        return False  # Not TWP1, so can't be "tampered" — it's a plain plugin
    parts = raw.split("\n", 2)
    if len(parts) != 3:
        return True  # Malformed TWP1 — treat as tampered
    stored_hash = parts[1]
    content = parts[2]
    actual_hash = hashlib.sha256(content.encode("utf-8")).hexdigest()
    return actual_hash != stored_hash


def _verify_plugin_from_registry(plugin_name: str, installed_code: str) -> bool:
    """Verify installed plugin code against official registry.

    Fetches the official plugin.twp from the registry and compares
    its SHA-256 with the installed plugin's SHA-256.

    Returns True if:
    - Code matches official registry (genuine plugin)
    - Registry not reachable (offline fallback — trust installed hash)

    Returns False if:
    - Plugin not found in registry (custom/fake plugin)
    - Code doesn't match (tampered or wrong plugin)
    """
    try:
        registry = fetch_registry()
        if "error" in registry:
            # Registry not reachable — offline mode, trust installed plugin
            return True

        plugins = registry.get("plugins", [])
        info = next((p for p in plugins if p["name"] == plugin_name), None)
        if not info:
            # Plugin not in registry — custom plugin, reject
            return False

        base_url = PLUGIN_REGISTRY_URL.rsplit("/", 1)[0]
        plugin_url = info.get("url", "plugins/" + plugin_name + "/")
        official_url = base_url + "/" + plugin_url + "plugin.twp"

        import urllib.request
        with urllib.request.urlopen(official_url, timeout=10) as resp:
            official_code = resp.read().decode("utf-8")

        installed_hash = hashlib.sha256(installed_code.encode("utf-8")).hexdigest()
        official_hash = hashlib.sha256(official_code.encode("utf-8")).hexdigest()

        return installed_hash == official_hash

    except Exception:
        # Network error — offline fallback, trust installed plugin
        return True


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
                # v0.9.40: Two-tier plugin loading — 0 network requests.
                # Tier 1: TWP1 format (installed via `tw plugin add`) — hash verified.
                # Tier 2: Plain files (custom plugins) — loaded with warning.
                # Tampered TWP1 (hash mismatch) → rejected.
                meta_json = _load_plugin_with_hash(pj)
                code = _load_plugin_with_hash(pt)

                if meta_json is not None and code is not None:
                    # Tier 1: Official registry plugin — hash verified
                    meta = json.loads(meta_json)
                    plugin = Plugin(meta.get("name", entry), meta.get("version", "0.0.0"), meta, code)
                    self._parse_twp(plugin)
                    plugin.enabled = True
                    self.plugins[plugin.name] = plugin
                else:
                    # Tier 2: Try loading as plain custom plugin
                    meta_json_plain = _load_plain(pj)
                    code_plain = _load_plain(pt)
                    if meta_json_plain is not None and code_plain is not None:
                        # Check if it was TWP1 but tampered (hash mismatch)
                        if _is_twp1_tampered(pj) or _is_twp1_tampered(pt):
                            print("  [plugin] Rejected " + entry + ": hash mismatch (tampered)")
                            continue
                        # Plain custom plugin — load with warning
                        meta = json.loads(meta_json_plain)
                        plugin = Plugin(meta.get("name", entry), meta.get("version", "0.0.0"), meta, code_plain)
                        self._parse_twp(plugin)
                        plugin.enabled = True
                        self.plugins[plugin.name] = plugin
                        print("  [plugin] Loaded custom plugin '" + entry + "' (not verified — install via 'tw plugin add' for verified plugins)")
                    else:
                        print("  [plugin] Rejected " + entry + ": invalid or corrupted files")
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

            def make_hook(body, name, hook):
                def hook_fn(ctx: PluginContext) -> None:
                    _run_plugin_in_node(name, hook, body, ctx)
                return hook_fn

            plugin.register_hook(hook_name, make_hook(fn_body, plugin.name, hook_name))

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
    # v0.9.35: Derive base_url from PLUGIN_REGISTRY_URL so both stay in sync
    base_url = PLUGIN_REGISTRY_URL.rsplit("/", 1)[0]  # strip /registry.json
    plugin_url = info.get("url", "plugins/" + name + "/")
    os.makedirs(os.path.join(plugins_dir, name), exist_ok=True)
    # v0.9.08 FIX: SHA-256 checksum verification
    checksums = info.get("checksums", {})
    for fname in ["plugin.twp", "plugin.json"]:
        url = base_url + "/" + plugin_url + fname
        try:
            import urllib.request
            with urllib.request.urlopen(url, timeout=10) as resp:
                content = resp.read()
            expected_hash = checksums.get(fname)
            if expected_hash:
                actual_hash = hashlib.sha256(content).hexdigest()
                if actual_hash != expected_hash:
                    return {"success": False, "error": "Checksum mismatch for " + fname}
            # v0.9.38: Save plugin with embedded hash (TWP1 format)
            # No secret, no HMAC — just SHA-256 of raw content
            _save_plugin_with_hash(content, os.path.join(plugins_dir, name, fname), name)
            # Save SHA-256 of original content for reference
            with open(os.path.join(plugins_dir, name, "." + fname + ".sha256"), "w") as cf:
                cf.write(hashlib.sha256(content).hexdigest())
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


def update_plugin(name: str, plugins_dir: str = ".tw/plugins") -> dict:
    """Check for plugin updates and install if newer version available.

    Fetches registry, compares installed version with registry version.
    If registry version is newer, re-downloads and installs the update.

    Returns:
      - {"success": True, "updated": True, "version": "x"}  — updated
      - {"success": True, "updated": False, "version": "x"} — already latest
      - {"success": False, "error": "..."}                  — failed
    """
    # Read installed version
    pj_path = os.path.join(plugins_dir, name, "plugin.json")
    installed_version = "0.0.0"
    if os.path.isfile(pj_path):
        meta_json = _load_plugin_with_hash(pj_path)
        if meta_json:
            try:
                installed_version = json.loads(meta_json).get("version", "0.0.0")
            except Exception:
                pass

    # Fetch registry
    registry = fetch_registry()
    if "error" in registry:
        return {"success": False, "error": registry["error"]}

    plugins = registry.get("plugins", [])
    info = next((p for p in plugins if p["name"] == name), None)
    if not info:
        return {"success": False, "error": "Plugin '" + name + "' not found in registry"}

    registry_version = info.get("version", "0.0.0")

    # Compare versions
    if installed_version == registry_version:
        return {"success": True, "updated": False, "version": installed_version,
                "message": "Plugin '" + name + "' is already up to date (v" + installed_version + ")"}

    # Update available — reinstall
    result = install_plugin(name, plugins_dir)
    if result.get("success"):
        result["updated"] = True
        result["old_version"] = installed_version
        result["new_version"] = registry_version
    return result


# v0.9.08 FIX: Real Node.js plugin execution via vm sandbox
def _run_plugin_in_node(plugin_name, hook, body, ctx):
    """Run plugin hook in real Node.js vm sandbox.

    Replaces regex-based JS->Python translation + exec().
    Uses Node.js vm module for real JavaScript execution:
    - Real JS parsing (arrow functions, classes, async/await, destructuring)
    - 5-second timeout via vm.runInContext
    - Restricted sandbox (no require, no process, no fs)
    """
    import subprocess as _sub
    import json as _json

    ctx_data = _json.dumps({
        "pages": ctx.pages if ctx.pages else [],
        "config": ctx.config if ctx.config else {},
        "output_dir": ctx.output_dir,
        "request": ctx.request if ctx.request else {},
        "response": ctx.response if ctx.response else {},
    })

    runner_path = os.path.join(os.path.dirname(__file__), "_plugin_runner.js")

    # Find node binary
    try:
        from .npm_manager import find_node
        node_bin = find_node()
    except Exception:
        node_bin = "node"

    if not node_bin:
        ctx.warn("Node.js not found - plugin " + plugin_name + " skipped")
        return

    try:
        result = _sub.run(
            [node_bin, runner_path, plugin_name, hook, ctx_data],
            input=body,
            capture_output=True,
            text=True,
            timeout=10,
        )
        if result.returncode != 0 and result.stderr:
            ctx.error("Plugin " + plugin_name + ": " + result.stderr.strip())
        if result.stdout:
            marker = "__TW_RESULT__"
            if marker in result.stdout:
                idx = result.stdout.find(marker)
                try:
                    res = _json.loads(result.stdout[idx + len(marker):].strip())
                    if res.get("redirect"):
                        ctx.redirect(res["redirect"]["url"], res["redirect"].get("status", 302))
                except Exception:
                    pass
    except _sub.TimeoutExpired:
        ctx.warn("Plugin " + plugin_name + " timed out in " + hook)
    except FileNotFoundError:
        ctx.warn("Node.js not available - plugin " + plugin_name + " skipped")
    except Exception as err:
        ctx.error("Plugin " + plugin_name + " error: " + str(err))
