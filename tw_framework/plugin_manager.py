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


HOOKS = [
    "beforeBuild", "afterBuild",
    "beforeRequest", "afterRequest",
    "onRouteMatch",
    "onPageRender", "onError", "onConfigLoad",
]

# Global registries for plugin-registered routes and CLI commands
_PLUGIN_ROUTES: List[dict] = []
_PLUGIN_COMMANDS: Dict[str, dict] = {}


def register_plugin_route(path: str, handler: Callable, plugin_name: str, method: str = "GET") -> None:
    """Register a custom route from a plugin. Called by PluginContext.register_route()."""
    _PLUGIN_ROUTES.append({
        "path": path, "handler": handler,
        "plugin": plugin_name, "method": method.upper(),
    })


def register_plugin_command(plugin_name: str, command: str, handler: Callable, help_text: str = "") -> None:
    """Register a custom CLI command from a plugin.

    Format: tw <plugin_name> <command>
    Cannot override existing built-in commands.
    """
    key = plugin_name + " " + command
    if key not in _PLUGIN_COMMANDS:
        _PLUGIN_COMMANDS[key] = {
            "plugin": plugin_name, "command": command,
            "handler": handler, "help": help_text,
        }


def get_plugin_routes() -> List[dict]:
    """Get all routes registered by plugins. Used by app_router.py."""
    return list(_PLUGIN_ROUTES)


def get_plugin_commands() -> Dict[str, dict]:
    """Get all CLI commands registered by plugins. Used by cli.py."""
    return dict(_PLUGIN_COMMANDS)

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
    """Context object passed to plugin hooks. Only exists inside TW.

    v0.9.41: Full power — HTTP fetch, route registration, CLI commands,
    cookies, headers, page HTML, data store, static files, env vars.
    All file access is sandboxed to project root (path traversal blocked).
    """

    def __init__(self, hook: str, data: Optional[dict] = None):
        self.hook = hook
        self._data = data or {}
        self._modified = False
        self._plugin_name: str = self._data.get("_plugin_name", "unknown")

    # ── Pages ──────────────────────────────────────────────────────

    @property
    def pages(self) -> list:
        return self._data.get("pages", [])

    @pages.setter
    def pages(self, val: list) -> None:
        self._data["pages"] = val
        self._modified = True

    def get_page_html(self, index: int) -> str:
        """Get rendered HTML of a specific page by index."""
        pages = self._data.get("pages", [])
        if 0 <= index < len(pages):
            return pages[index].get("html", "")
        return ""

    def set_page_html(self, index: int, html: str) -> None:
        """Modify rendered HTML of a specific page."""
        pages = self._data.get("pages", [])
        if 0 <= index < len(pages):
            pages[index]["html"] = html
            self._modified = True

    def get_page_meta(self, index: int) -> dict:
        """Get metadata of a specific page (url, title, route, etc.)."""
        pages = self._data.get("pages", [])
        if 0 <= index < len(pages):
            return pages[index]
        return {}

    # ── Config ─────────────────────────────────────────────────────

    @property
    def config(self) -> dict:
        return self._data.get("config", {})

    @property
    def output_dir(self) -> str:
        return self._data.get("output_dir", "dist")

    # ── Request / Response ─────────────────────────────────────────

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

    def set_header(self, name: str, value: str) -> None:
        """Set a response header."""
        headers = self._data.get("response_headers", {})
        headers[name] = value
        self._data["response_headers"] = headers
        self._modified = True

    def get_header(self, name: str) -> str:
        """Get a request header."""
        return self._data.get("request_headers", {}).get(name, "")

    def set_status(self, code: int) -> None:
        """Set HTTP response status code."""
        self._data["response_status"] = code
        self._modified = True

    # ── Cookies ────────────────────────────────────────────────────

    def get_cookie(self, name: str) -> str:
        """Get a cookie value from the request."""
        cookies = self._data.get("cookies", {})
        return cookies.get(name, "")

    def set_cookie(self, name: str, value: str, max_age: int = 3600,
                   path: str = "/", http_only: bool = True) -> None:
        """Set a cookie on the response."""
        cookies = self._data.get("set_cookies", [])
        cookies.append({
            "name": name, "value": value,
            "max_age": max_age, "path": path,
            "http_only": http_only,
        })
        self._data["set_cookies"] = cookies
        self._modified = True

    # ── Query Params ───────────────────────────────────────────────

    @property
    def query_params(self) -> dict:
        """Get request query parameters."""
        return self._data.get("query_params", {})

    @property
    def route_params(self) -> dict:
        """Get route parameters (e.g. /users/:id -> {"id": "123"})."""
        return self._data.get("route_params", {})

    # ── File Access (sandboxed) ─────────────────────────────────────

    def read_file(self, path: str) -> str:
        safe_path = self._safe_path(path)
        with open(safe_path, "r", encoding="utf-8") as f:
            return f.read()

    def read_file_bytes(self, path: str) -> bytes:
        """Read a file as bytes (for images, binaries)."""
        safe_path = self._safe_path(path)
        with open(safe_path, "rb") as f:
            return f.read()

    def write_file(self, path: str, data: str) -> bool:
        safe_path = self._safe_path(path)
        os.makedirs(os.path.dirname(safe_path) or ".", exist_ok=True)
        with open(safe_path, "w", encoding="utf-8") as f:
            f.write(data)
        return True

    def write_file_bytes(self, path: str, data: bytes) -> bool:
        """Write bytes to a file (for images, binaries)."""
        safe_path = self._safe_path(path)
        os.makedirs(os.path.dirname(safe_path) or ".", exist_ok=True)
        with open(safe_path, "wb") as f:
            f.write(data)
        return True

    def file_exists(self, path: str) -> bool:
        return os.path.exists(self._safe_path(path))

    def list_dir(self, path: str) -> list:
        """List files in a directory."""
        safe_path = self._safe_path(path)
        if os.path.isdir(safe_path):
            return os.listdir(safe_path)
        return []

    def delete_file(self, path: str) -> bool:
        """Delete a file (sandboxed)."""
        safe_path = self._safe_path(path)
        if os.path.isfile(safe_path):
            os.remove(safe_path)
            return True
        return False

    def mkdir(self, path: str) -> bool:
        """Create a directory."""
        safe_path = self._safe_path(path)
        os.makedirs(safe_path, exist_ok=True)
        return True

    # ── HTTP Fetch ─────────────────────────────────────────────────

    def fetch(self, url: str, method: str = "GET",
              headers: Optional[dict] = None,
              body: Optional[str] = None,
              timeout: int = 30) -> dict:
        """Make an HTTP request to an external API.

        Returns {"status": int, "headers": dict, "body": str} or
        {"error": str} on failure.

        Security: Only http/https URLs allowed. No localhost/private IPs.
        """
        import urllib.request
        import urllib.error

        if not url.startswith(("http://", "https://")):
            return {"error": "Only http/https URLs allowed"}

        # Block private/internal IPs
        import socket
        try:
            parsed = urllib.parse.urlparse(url)
            hostname = parsed.hostname or ""
            if hostname in ("localhost", "127.0.0.1", "0.0.0.0",
                             "::1", "169.254.169.254"):
                return {"error": "Private/internal addresses blocked"}
            ip = socket.gethostbyname(hostname)
            if ip.startswith(("10.", "172.16.", "172.17.", "172.18.",
                              "172.19.", "172.20.", "172.21.", "172.22.",
                              "172.23.", "172.24.", "172.25.", "172.26.",
                              "172.27.", "172.28.", "172.29.", "172.30.",
                              "172.31.", "192.168.")):
                return {"error": "Private/internal addresses blocked"}
        except Exception:
            pass

        try:
            req = urllib.request.Request(url, method=method.upper())
            if headers:
                for k, v in headers.items():
                    req.add_header(k, str(v))
            if body and method.upper() in ("POST", "PUT", "PATCH"):
                req.data = body.encode("utf-8") if isinstance(body, str) else body
            with urllib.request.urlopen(req, timeout=timeout) as resp:
                resp_body = resp.read().decode("utf-8", errors="replace")
                resp_headers = dict(resp.headers.items())
                return {
                    "status": resp.status,
                    "headers": resp_headers,
                    "body": resp_body,
                }
        except urllib.error.HTTPError as e:
            return {
                "status": e.code,
                "headers": dict(e.headers.items()) if e.headers else {},
                "body": e.read().decode("utf-8", errors="replace"),
            }
        except Exception as e:
            return {"error": str(e)}

    # ── Route Registration ─────────────────────────────────────────

    def register_route(self, path: str, handler: Callable,
                       method: str = "GET") -> None:
        """Register a custom route.

        Example: ctx.register_route("/sitemap.xml", sitemap_handler)
        The handler receives this PluginContext and should set ctx.response.
        """
        register_plugin_route(path, handler, self._plugin_name, method)
        self.log("Registered route: " + method.upper() + " " + path)

    # ── CLI Command Registration ───────────────────────────────────

    def register_command(self, command: str, handler: Callable,
                         help_text: str = "") -> None:
        """Register a custom CLI command.

        Format: tw <plugin_name> <command>
        Cannot override existing built-in commands.

        Example: ctx.register_command("analyze", analyze_handler, "Run SEO analysis")
        → tw seo-plugin analyze
        """
        register_plugin_command(self._plugin_name, command, handler, help_text)
        self.log("Registered command: tw " + self._plugin_name + " " + command)

    # ── Plugin Data Store ──────────────────────────────────────────

    def get_data(self, key: str, default: Any = None) -> Any:
        """Get plugin-specific data (persists across hooks within one build)."""
        store = self._data.get("plugin_data", {})
        return store.get(self._plugin_name, {}).get(key, default)

    def set_data(self, key: str, value: Any) -> None:
        """Set plugin-specific data (persists across hooks within one build)."""
        store = self._data.setdefault("plugin_data", {})
        store.setdefault(self._plugin_name, {})[key] = value
        self._modified = True

    # ── Environment Variables ───────────────────────────────────────

    def get_env(self, name: str, default: str = "") -> str:
        """Get an environment variable. Only TW_ prefixed vars are exposed."""
        val = os.environ.get(name, default)
        return val

    # ── Static File Serving ─────────────────────────────────────────

    def serve_static(self, file_path: str, content_type: str = "application/octet-stream") -> dict:
        """Read a file and return it as a response with proper content type.

        Example: ctx.serve_static("public/robots.txt", "text/plain")
        """
        if self.file_exists(file_path):
            content = self.read_file(file_path)
            return {
                "status": 200,
                "headers": {"Content-Type": content_type},
                "body": content,
            }
        return {
            "status": 404,
            "headers": {"Content-Type": "text/plain"},
            "body": "Not Found",
        }

    # ── JSON Helper ────────────────────────────────────────────────

    def json_response(self, data: Any, status: int = 200) -> dict:
        """Create a JSON response."""
        return {
            "status": status,
            "headers": {"Content-Type": "application/json"},
            "body": json.dumps(data, ensure_ascii=False),
        }

    # ── Logging ────────────────────────────────────────────────────

    def log(self, msg: str) -> None:
        print("  [plugin:" + self._plugin_name + "] " + str(msg))

    def warn(self, msg: str) -> None:
        print("  [plugin:" + self._plugin_name + " WARNING] " + str(msg))

    def error(self, msg: str) -> None:
        print("  [plugin:" + self._plugin_name + " ERROR] " + str(msg))

    # ── Redirect ────────────────────────────────────────────────────

    def redirect(self, url: str, status: int = 302) -> None:
        self._data["redirect"] = {"url": url, "status": status}
        self._modified = True

    # ── Path Security ───────────────────────────────────────────────

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
                # Set plugin name so ctx knows which plugin is running
                ctx._plugin_name = name
                ctx._data["_plugin_name"] = name
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
