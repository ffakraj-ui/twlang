"""
Test suite for v0.9.41 plugin powers — full PluginContext capabilities.

Tests:
- HTTP fetch (with private IP blocking)
- Route registration
- CLI command registration
- Cookies (get/set)
- Headers (set/get)
- Response status
- Page HTML access (get/set)
- Plugin data store (get/set)
- File operations (read bytes, write bytes, list dir, delete, mkdir)
- Static file serving
- JSON response helper
- Query params and route params
- Environment variables
- New hooks (onPageRender, onError, onConfigLoad)
- Plugin command dispatch (tw <plugin> <command>)
"""

import os
import sys
import json
import shutil
import tempfile
import hashlib
import unittest

# Ensure we can import the framework
sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from tw_framework.plugin_manager import (
    PluginContext,
    Plugin,
    PluginManager,
    HOOKS,
    _PLUGIN_ROUTES,
    _PLUGIN_COMMANDS,
    register_plugin_route,
    register_plugin_command,
    get_plugin_routes,
    get_plugin_commands,
    _save_plugin_with_hash,
    _load_plugin_with_hash,
)


class TestPluginContextPowers(unittest.TestCase):

    def setUp(self):
        self.tmpdir = tempfile.mkdtemp()
        self.ctx = PluginContext("afterBuild", {
            "project_root": self.tmpdir,
            "output_dir": os.path.join(self.tmpdir, "dist"),
            "_plugin_name": "test-plugin",
            "pages": [
                {"url": "/", "html": "<html><body>Home</body></html>", "title": "Home"},
                {"url": "/about", "html": "<html><body>About</body></html>", "title": "About"},
            ],
            "config": {"site_name": "Test Site"},
            "request": {"method": "GET", "path": "/"},
            "response": {},
            "request_headers": {"Authorization": "Bearer token123"},
            "cookies": {"session": "abc123"},
            "query_params": {"q": "hello", "page": "2"},
            "route_params": {"id": "42"},
        })

    def tearDown(self):
        shutil.rmtree(self.tmpdir, ignore_errors=True)
        # Clear global registries
        _PLUGIN_ROUTES.clear()
        _PLUGIN_COMMANDS.clear()

    # ── Page HTML Access ────────────────────────────────────────────

    def test_get_page_html(self):
        html = self.ctx.get_page_html(0)
        self.assertIn("Home", html)

    def test_get_page_html_invalid_index(self):
        html = self.ctx.get_page_html(99)
        self.assertEqual(html, "")

    def test_set_page_html(self):
        self.ctx.set_page_html(0, "<html><body>Modified</body></html>")
        html = self.ctx.get_page_html(0)
        self.assertIn("Modified", html)
        self.assertTrue(self.ctx.modified)

    def test_get_page_meta(self):
        meta = self.ctx.get_page_meta(1)
        self.assertEqual(meta["url"], "/about")
        self.assertEqual(meta["title"], "About")

    def test_get_page_meta_invalid(self):
        meta = self.ctx.get_page_meta(99)
        self.assertEqual(meta, {})

    # ── Headers ────────────────────────────────────────────────────

    def test_set_header(self):
        self.ctx.set_header("X-Custom", "value123")
        self.assertTrue(self.ctx.modified)
        headers = self.ctx._data.get("response_headers", {})
        self.assertEqual(headers.get("X-Custom"), "value123")

    def test_get_header(self):
        val = self.ctx.get_header("Authorization")
        self.assertEqual(val, "Bearer token123")

    def test_get_header_missing(self):
        val = self.ctx.get_header("X-Nonexistent")
        self.assertEqual(val, "")

    # ── Response Status ────────────────────────────────────────────

    def test_set_status(self):
        self.ctx.set_status(404)
        self.assertTrue(self.ctx.modified)
        self.assertEqual(self.ctx._data.get("response_status"), 404)

    # ── Cookies ────────────────────────────────────────────────────

    def test_get_cookie(self):
        val = self.ctx.get_cookie("session")
        self.assertEqual(val, "abc123")

    def test_get_cookie_missing(self):
        val = self.ctx.get_cookie("nonexistent")
        self.assertEqual(val, "")

    def test_set_cookie(self):
        self.ctx.set_cookie("token", "xyz789", max_age=7200)
        cookies = self.ctx._data.get("set_cookies", [])
        self.assertEqual(len(cookies), 1)
        self.assertEqual(cookies[0]["name"], "token")
        self.assertEqual(cookies[0]["value"], "xyz789")
        self.assertEqual(cookies[0]["max_age"], 7200)
        self.assertTrue(self.ctx.modified)

    def test_set_multiple_cookies(self):
        self.ctx.set_cookie("token", "xyz789")
        self.ctx.set_cookie("refresh", "abc456")
        cookies = self.ctx._data.get("set_cookies", [])
        self.assertEqual(len(cookies), 2)

    # ── Query Params & Route Params ────────────────────────────────

    def test_query_params(self):
        params = self.ctx.query_params
        self.assertEqual(params.get("q"), "hello")
        self.assertEqual(params.get("page"), "2")

    def test_route_params(self):
        params = self.ctx.route_params
        self.assertEqual(params.get("id"), "42")

    # ── File Operations ────────────────────────────────────────────

    def test_write_and_read_file(self):
        self.ctx.write_file("test.txt", "hello world")
        content = self.ctx.read_file("test.txt")
        self.assertEqual(content, "hello world")

    def test_write_file_bytes(self):
        self.ctx.write_file_bytes("binary.dat", b"\x00\x01\x02\x03")
        data = self.ctx.read_file_bytes("binary.dat")
        self.assertEqual(data, b"\x00\x01\x02\x03")

    def test_read_file_bytes(self):
        self.ctx.write_file_bytes("data.bin", b"\xff\xfe")
        data = self.ctx.read_file_bytes("data.bin")
        self.assertEqual(data, b"\xff\xfe")

    def test_file_exists(self):
        self.ctx.write_file("exists.txt", "yes")
        self.assertTrue(self.ctx.file_exists("exists.txt"))
        self.assertFalse(self.ctx.file_exists("nope.txt"))

    def test_list_dir(self):
        self.ctx.write_file("a.txt", "a")
        self.ctx.write_file("b.txt", "b")
        self.ctx.mkdir("subdir")
        entries = self.ctx.list_dir(".")
        self.assertIn("a.txt", entries)
        self.assertIn("b.txt", entries)

    def test_list_dir_nonexistent(self):
        entries = self.ctx.list_dir("nonexistent_dir")
        self.assertEqual(entries, [])

    def test_delete_file(self):
        self.ctx.write_file("delete_me.txt", "bye")
        self.assertTrue(self.ctx.delete_file("delete_me.txt"))
        self.assertFalse(self.ctx.file_exists("delete_me.txt"))

    def test_delete_file_nonexistent(self):
        result = self.ctx.delete_file("nope.txt")
        self.assertFalse(result)

    def test_mkdir(self):
        self.ctx.mkdir("new_dir/sub_dir")
        self.assertTrue(os.path.isdir(os.path.join(self.tmpdir, "new_dir", "sub_dir")))

    # ── Path Traversal Security ────────────────────────────────────

    def test_path_traversal_blocked_read(self):
        with self.assertRaises(PermissionError):
            self.ctx.read_file("../../../etc/passwd")

    def test_path_traversal_blocked_write(self):
        with self.assertRaises(PermissionError):
            self.ctx.write_file("../../../etc/malicious.txt", "hacked")

    def test_path_traversal_blocked_delete(self):
        with self.assertRaises(PermissionError):
            self.ctx.delete_file("../../../etc/passwd")

    # ── Plugin Data Store ─────────────────────────────────────────

    def test_set_and_get_data(self):
        self.ctx.set_data("counter", 42)
        val = self.ctx.get_data("counter")
        self.assertEqual(val, 42)

    def test_get_data_default(self):
        val = self.ctx.get_data("nonexistent", default="default_val")
        self.assertEqual(val, "default_val")

    def test_data_isolated_per_plugin(self):
        self.ctx.set_data("key1", "plugin_a_value")
        # Create another context with different plugin name
        ctx2 = PluginContext("afterBuild", {
            "project_root": self.tmpdir,
            "_plugin_name": "other-plugin",
        })
        val = ctx2.get_data("key1")
        self.assertIsNone(val)

    # ── Environment Variables ──────────────────────────────────────

    def test_get_env(self):
        os.environ["TW_TEST_VAR"] = "test_value_123"
        val = self.ctx.get_env("TW_TEST_VAR")
        self.assertEqual(val, "test_value_123")
        del os.environ["TW_TEST_VAR"]

    def test_get_env_default(self):
        val = self.ctx.get_env("TW_NONEXISTENT_VAR", default="fallback")
        self.assertEqual(val, "fallback")

    # ── Static File Serving ────────────────────────────────────────

    def test_serve_static_existing(self):
        self.ctx.write_file("robots.txt", "User-agent: *\nDisallow: /admin")
        result = self.ctx.serve_static("robots.txt", "text/plain")
        self.assertEqual(result["status"], 200)
        self.assertIn("User-agent", result["body"])
        self.assertEqual(result["headers"]["Content-Type"], "text/plain")

    def test_serve_static_missing(self):
        result = self.ctx.serve_static("nonexistent.txt", "text/plain")
        self.assertEqual(result["status"], 404)

    # ── JSON Response ─────────────────────────────────────────────

    def test_json_response(self):
        result = self.ctx.json_response({"status": "ok", "count": 5})
        self.assertEqual(result["status"], 200)
        self.assertEqual(result["headers"]["Content-Type"], "application/json")
        parsed = json.loads(result["body"])
        self.assertEqual(parsed["status"], "ok")
        self.assertEqual(parsed["count"], 5)

    def test_json_response_custom_status(self):
        result = self.ctx.json_response({"error": "Not found"}, status=404)
        self.assertEqual(result["status"], 404)

    # ── Route Registration ────────────────────────────────────────

    def test_register_route(self):
        def handler(ctx):
            pass
        self.ctx.register_route("/sitemap.xml", handler)
        routes = get_plugin_routes()
        self.assertEqual(len(routes), 1)
        self.assertEqual(routes[0]["path"], "/sitemap.xml")
        self.assertEqual(routes[0]["plugin"], "test-plugin")
        self.assertEqual(routes[0]["method"], "GET")

    def test_register_route_with_method(self):
        def handler(ctx):
            pass
        self.ctx.register_route("/api/data", handler, method="POST")
        routes = get_plugin_routes()
        self.assertEqual(routes[0]["method"], "POST")

    def test_register_multiple_routes(self):
        def h1(ctx): pass
        def h2(ctx): pass
        self.ctx.register_route("/sitemap.xml", h1)
        self.ctx.register_route("/rss.xml", h2)
        routes = get_plugin_routes()
        self.assertEqual(len(routes), 2)

    # ── CLI Command Registration ─────────────────────────────────

    def test_register_command(self):
        def handler(args):
            return 0
        self.ctx.register_command("analyze", handler, "Run SEO analysis")
        commands = get_plugin_commands()
        key = "test-plugin analyze"
        self.assertIn(key, commands)
        self.assertEqual(commands[key]["handler"], handler)
        self.assertEqual(commands[key]["help"], "Run SEO analysis")

    def test_register_multiple_commands(self):
        def h1(args): pass
        def h2(args): pass
        self.ctx.register_command("analyze", h1)
        self.ctx.register_command("report", h2)
        commands = get_plugin_commands()
        self.assertIn("test-plugin analyze", commands)
        self.assertIn("test-plugin report", commands)

    def test_command_cannot_duplicate(self):
        def h1(args): return 0
        def h2(args): return 1
        self.ctx.register_command("sync", h1, "First")
        self.ctx.register_command("sync", h2, "Second")
        commands = get_plugin_commands()
        # First registration wins
        self.assertEqual(commands["test-plugin sync"]["help"], "First")

    # ── HTTP Fetch ────────────────────────────────────────────────

    def test_fetch_blocks_non_http(self):
        result = self.ctx.fetch("ftp://example.com/file")
        self.assertIn("error", result)
        self.assertIn("http", result["error"].lower())

    def test_fetch_blocks_localhost(self):
        result = self.ctx.fetch("http://localhost:8080/api")
        self.assertIn("error", result)
        self.assertIn("blocked", result["error"].lower())

    def test_fetch_blocks_127(self):
        result = self.ctx.fetch("http://127.0.0.1:8080/api")
        self.assertIn("error", result)

    def test_fetch_blocks_169_254(self):
        result = self.ctx.fetch("http://169.254.169.254/latest/meta-data/")
        self.assertIn("error", result)

    # ── New Hooks ─────────────────────────────────────────────────

    def test_new_hooks_exist(self):
        self.assertIn("onPageRender", HOOKS)
        self.assertIn("onError", HOOKS)
        self.assertIn("onConfigLoad", HOOKS)

    def test_all_hooks_count(self):
        self.assertEqual(len(HOOKS), 8)

    # ── Redirect ─────────────────────────────────────────────────

    def test_redirect(self):
        self.ctx.redirect("/new-page", status=301)
        redirect_data = self.ctx._data.get("redirect")
        self.assertEqual(redirect_data["url"], "/new-page")
        self.assertEqual(redirect_data["status"], 301)
        self.assertTrue(self.ctx.modified)

    # ── Plugin Name in Logs ──────────────────────────────────────

    def test_plugin_name_in_context(self):
        self.assertEqual(self.ctx._plugin_name, "test-plugin")


class TestPluginRouteMatching(unittest.TestCase):
    """Test that plugin routes are checked by match_route."""

    def setUp(self):
        _PLUGIN_ROUTES.clear()
        self.tmpdir = tempfile.mkdtemp()

    def tearDown(self):
        _PLUGIN_ROUTES.clear()
        shutil.rmtree(self.tmpdir, ignore_errors=True)

    def test_plugin_route_match(self):
        from tw_framework.app_router import match_route
        register_plugin_route("/sitemap.xml", lambda ctx: None, "seo-plugin")
        match, params = match_route([], "/sitemap.xml")
        # Should return a plugin route marker
        self.assertIsNotNone(match)
        if isinstance(match, str):
            self.assertIn("__plugin__", match)
            self.assertIn("seo-plugin", match)

    def test_plugin_route_no_match(self):
        from tw_framework.app_router import match_route
        register_plugin_route("/sitemap.xml", lambda ctx: None, "seo-plugin")
        match, params = match_route([], "/nonexistent")
        self.assertIsNone(match)


class TestPluginCLICommands(unittest.TestCase):
    """Test plugin CLI command registration and dispatch."""

    def setUp(self):
        _PLUGIN_COMMANDS.clear()

    def tearDown(self):
        _PLUGIN_COMMANDS.clear()

    def test_command_format(self):
        register_plugin_command("seo-plugin", "analyze", lambda args: 0, "Analyze SEO")
        commands = get_plugin_commands()
        key = "seo-plugin analyze"
        self.assertIn(key, commands)
        self.assertEqual(commands[key]["plugin"], "seo-plugin")
        self.assertEqual(commands[key]["command"], "analyze")

    def test_command_handler_callable(self):
        def my_handler(args):
            return 42
        register_plugin_command("my-plugin", "run", my_handler)
        commands = get_plugin_commands()
        handler = commands["my-plugin run"]["handler"]
        result = handler([])
        self.assertEqual(result, 42)

    def test_commands_isolated_per_plugin(self):
        register_plugin_command("plugin-a", "sync", lambda a: 0)
        register_plugin_command("plugin-b", "sync", lambda a: 0)
        commands = get_plugin_commands()
        self.assertIn("plugin-a sync", commands)
        self.assertIn("plugin-b sync", commands)
        self.assertNotEqual(
            commands["plugin-a sync"]["handler"],
            commands["plugin-b sync"]["handler"],
        )


class TestPluginContextWithRealPlugin(unittest.TestCase):
    """Test PluginContext with a real PluginManager instance."""

    def setUp(self):
        self.tmpdir = tempfile.mkdtemp()
        _PLUGIN_ROUTES.clear()
        _PLUGIN_COMMANDS.clear()

    def tearDown(self):
        shutil.rmtree(self.tmpdir, ignore_errors=True)
        _PLUGIN_ROUTES.clear()
        _PLUGIN_COMMANDS.clear()

    def _make_valid_plugin(self, plugins_dir, name):
        """Create a valid TWP1 plugin."""
        pdir = os.path.join(plugins_dir, name)
        os.makedirs(pdir, exist_ok=True)
        meta = json.dumps({"name": name, "version": "1.0.0"})
        code = 'plugin.register("afterBuild", function(ctx) { ctx.log("hello from ' + name + '"); });'
        _save_plugin_with_hash(meta.encode(), os.path.join(pdir, "plugin.json"), name)
        _save_plugin_with_hash(code.encode(), os.path.join(pdir, "plugin.twp"), name)

    def test_plugin_loads_and_triggers(self):
        self._make_valid_plugin(self.tmpdir, "test-plugin")
        pm = PluginManager(plugins_dir=self.tmpdir, project_root=self.tmpdir)
        pm.load_all()
        self.assertIn("test-plugin", pm.plugins)

        ctx = pm.trigger("afterBuild", {"project_root": self.tmpdir})
        self.assertIsNotNone(ctx)

    def test_plugin_context_has_plugin_name(self):
        self._make_valid_plugin(self.tmpdir, "named-plugin")
        pm = PluginManager(plugins_dir=self.tmpdir, project_root=self.tmpdir)
        pm.load_all()
        ctx = pm.trigger("afterBuild", {"project_root": self.tmpdir})
        self.assertEqual(ctx._plugin_name, "named-plugin")


if __name__ == "__main__":
    unittest.main()
