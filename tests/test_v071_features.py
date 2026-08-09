"""
Tests for v0.7.1 features:
1. Client-side navigation (router runtime JS with SPA navigation)
2. generateStaticParams (page directive + dynamic route pre-rendering)
3. route.tw (App Router API route discovery)
"""
import os
import sys
import json
import tempfile
import shutil
import unittest

PROJECT_ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
sys.path.insert(0, PROJECT_ROOT)

from tw_framework import compiler
from tw_framework import app_router
from tw_framework import framework


def make_ast(source, tw_path):
    """Helper: build a PageNode from source string."""
    tokens = compiler.tokenize_tw(source)
    base_dir = os.path.dirname(tw_path)
    return compiler.build_tw_ast(tokens, base_dir, tw_path, source)


class TestClientSideNavigation(unittest.TestCase):
    """Test that the router runtime JS includes SPA-style navigation."""

    def setUp(self):
        self.tmpdir = tempfile.mkdtemp()
        compiler.PROJECT_ROOT = self.tmpdir
        compiler.HOME_DIR = os.path.join(self.tmpdir, "[home]")
        compiler.BUILD_DIR = os.path.join(self.tmpdir, "dist")
        compiler.CACHE_DIR = os.path.join(self.tmpdir, ".tw", "cache")
        compiler.CHUNKS_DIR = os.path.join(self.tmpdir, "dist", "_tw", "static", "chunks")
        compiler.CHUNKS_URL_PREFIX = "/_tw/static/chunks/"
        compiler.MANIFEST_DIR = os.path.join(self.tmpdir, "dist", "_tw")
        os.makedirs(compiler.HOME_DIR, exist_ok=True)
        os.makedirs(compiler.CACHE_DIR, exist_ok=True)
        os.makedirs(compiler.CHUNKS_DIR, exist_ok=True)

    def tearDown(self):
        shutil.rmtree(self.tmpdir, ignore_errors=True)

    def _get_router_js(self):
        """Helper: get the router runtime JS content."""
        # Clear chunk cache so file is written to our tmpdir
        if hasattr(compiler, '_CHUNK_CACHE'):
            compiler._CHUNK_CACHE.clear()
        url = compiler.get_router_runtime_url()
        chunk_path = os.path.join(compiler.BUILD_DIR, url.lstrip("/"))
        if os.path.exists(chunk_path):
            with open(chunk_path) as f:
                return f.read()
        # Fallback: try CHUNKS_DIR directly
        if hasattr(compiler, 'CHUNKS_DIR'):
            for fname in os.listdir(compiler.CHUNKS_DIR):
                fpath = os.path.join(compiler.CHUNKS_DIR, fname)
                if os.path.isfile(fpath):
                    with open(fpath) as f:
                        return f.read()
        return ""

    def test_router_runtime_has_spa_navigation(self):
        """Router runtime JS should include fetch-based SPA navigation."""
        js = self._get_router_js()
        self.assertTrue(len(js) > 0, "Router runtime JS should not be empty")
        self.assertIn("navigate", js)
        self.assertIn("fetch", js)

    def test_router_runtime_contains_navigate_function(self):
        """Router runtime JS should have a navigate function."""
        js = self._get_router_js()
        self.assertIn("navigate", js)
        self.assertIn("fetch", js)

    def test_router_runtime_has_popstate_handler(self):
        """Router runtime JS should handle browser back/forward."""
        js = self._get_router_js()
        self.assertIn("popstate", js)

    def test_router_runtime_has_click_intercept(self):
        """Router runtime JS should intercept clicks on data-tw-link anchors."""
        js = self._get_router_js()
        self.assertIn("data-tw-link", js)
        self.assertIn("click", js)

    def test_router_runtime_has_page_cache(self):
        """Router runtime JS should cache fetched pages."""
        js = self._get_router_js()
        self.assertIn("pageCache", js)

    def test_router_runtime_exposes_tw_navigate(self):
        """Router runtime JS should expose __twNavigate for programmatic use."""
        js = self._get_router_js()
        self.assertIn("__twNavigate", js)
        self.assertIn("__twRouterGoto", js)

    def test_router_runtime_has_swap_body(self):
        """Router runtime JS should have body swap logic."""
        js = self._get_router_js()
        self.assertIn("swapBody", js)

    def test_router_runtime_has_dom_parser(self):
        """Router runtime JS should use DOMParser for parsing fetched HTML."""
        js = self._get_router_js()
        self.assertIn("DOMParser", js)

    def test_router_runtime_has_loading_callback(self):
        """Router runtime JS should support __twOnLoading callback."""
        js = self._get_router_js()
        self.assertIn("__twOnLoading", js)

    def test_link_keyword_still_wraps_in_anchor(self):
        """The 'link' router key should still produce <a data-tw-link> wrapper."""
        source = 'page { title "Test" render static }\nbody {\n    div {\n        link "/about"\n    }\n}'
        tw_path = os.path.join(compiler.HOME_DIR, "index.tw")
        with open(tw_path, "w") as f:
            f.write(source)
        page_ast = make_ast(source, tw_path)
        context = compiler.create_base_context(page_ast, tw_path)
        html, needs_router, _ = compiler.render_elements_html(page_ast.body, context)
        self.assertIn("data-tw-link", html)
        self.assertIn("/about", html)
        self.assertTrue(needs_router)


class TestGenerateStaticParams(unittest.TestCase):
    """Test generateStaticParams page directive."""

    def setUp(self):
        self.tmpdir = tempfile.mkdtemp()
        compiler.PROJECT_ROOT = self.tmpdir
        compiler.HOME_DIR = os.path.join(self.tmpdir, "[home]")
        compiler.BUILD_DIR = os.path.join(self.tmpdir, "dist")
        compiler.CACHE_DIR = os.path.join(self.tmpdir, ".tw", "cache")
        compiler.CHUNKS_DIR = os.path.join(self.tmpdir, "dist", "_tw", "static", "chunks")
        compiler.CHUNKS_URL_PREFIX = "/_tw/static/chunks/"
        compiler.MANIFEST_DIR = os.path.join(self.tmpdir, "dist", "_tw")
        os.makedirs(compiler.HOME_DIR, exist_ok=True)
        os.makedirs(compiler.CACHE_DIR, exist_ok=True)
        os.makedirs(compiler.CHUNKS_DIR, exist_ok=True)

    def tearDown(self):
        shutil.rmtree(self.tmpdir, ignore_errors=True)

    def test_page_node_has_generate_static_params_field(self):
        """PageNode should have generate_static_params attribute."""
        page = compiler.PageNode()
        self.assertTrue(hasattr(page, "generate_static_params"))
        self.assertIsNone(page.generate_static_params)

    def test_parse_generate_static_params_directive(self):
        """Parser should recognize generateStaticParams in page block."""
        source = 'page {\n    title "Blog"\n    render static\n    generateStaticParams "./data/posts.json"\n}\nbody {\n    h1 "Blog"\n}'
        tw_path = os.path.join(compiler.HOME_DIR, "index.tw")
        with open(tw_path, "w") as f:
            f.write(source)
        page_ast = make_ast(source, tw_path)
        self.assertEqual(page_ast.generate_static_params, "./data/posts.json")

    def test_load_generate_static_params_list(self):
        """load_generate_static_params should load JSON list."""
        source = 'page {\n    title "Blog"\n    render static\n    generateStaticParams "./posts.json"\n}\nbody {\n    h1 "Blog Post: {slug}"\n}'
        tw_path = os.path.join(compiler.HOME_DIR, "index.tw")
        with open(tw_path, "w") as f:
            f.write(source)

        posts_json = os.path.join(compiler.HOME_DIR, "posts.json")
        with open(posts_json, "w") as f:
            json.dump([{"slug": "my-first-post"}, {"slug": "another-post"}], f)

        page_ast = make_ast(source, tw_path)
        items = compiler.load_generate_static_params(page_ast, tw_path)
        self.assertIsNotNone(items)
        self.assertEqual(len(items), 2)
        self.assertEqual(items[0]["slug"], "my-first-post")
        self.assertEqual(items[1]["slug"], "another-post")

    def test_load_generate_static_params_object_with_items(self):
        """load_generate_static_params should handle {"items": [...]} format."""
        source = 'page {\n    title "Blog"\n    render static\n    generateStaticParams "./posts.json"\n}\nbody { h1 "Blog" }'
        tw_path = os.path.join(compiler.HOME_DIR, "index.tw")
        with open(tw_path, "w") as f:
            f.write(source)

        posts_json = os.path.join(compiler.HOME_DIR, "posts.json")
        with open(posts_json, "w") as f:
            json.dump({"items": [{"id": "1"}, {"id": "2"}, {"id": "3"}]}, f)

        page_ast = make_ast(source, tw_path)
        items = compiler.load_generate_static_params(page_ast, tw_path)
        self.assertIsNotNone(items)
        self.assertEqual(len(items), 3)

    def test_load_generate_static_params_returns_none_when_not_set(self):
        """load_generate_static_params should return None when directive not set."""
        source = 'page { title "Blog" render static }\nbody { h1 "Blog" }'
        tw_path = os.path.join(compiler.HOME_DIR, "index.tw")
        with open(tw_path, "w") as f:
            f.write(source)
        page_ast = make_ast(source, tw_path)
        items = compiler.load_generate_static_params(page_ast, tw_path)
        self.assertIsNone(items)

    def test_load_generate_static_params_returns_empty_when_file_missing(self):
        """load_generate_static_params should return [] when file not found."""
        source = 'page {\n    title "Blog"\n    render static\n    generateStaticParams "./missing.json"\n}\nbody { h1 "Blog" }'
        tw_path = os.path.join(compiler.HOME_DIR, "index.tw")
        with open(tw_path, "w") as f:
            f.write(source)
        page_ast = make_ast(source, tw_path)
        items = compiler.load_generate_static_params(page_ast, tw_path)
        self.assertEqual(items, [])

    def test_load_generate_static_params_resolves_relative_path(self):
        """load_generate_static_params should resolve paths relative to page dir."""
        blog_dir = os.path.join(compiler.HOME_DIR, "blog", "[slug]")
        os.makedirs(blog_dir, exist_ok=True)

        source = 'page {\n    title "Post"\n    render static\n    generateStaticParams "./posts.json"\n}\nbody { h1 "Post: {slug}" }'
        tw_path = os.path.join(blog_dir, "page.tw")
        with open(tw_path, "w") as f:
            f.write(source)

        posts_json = os.path.join(blog_dir, "posts.json")
        with open(posts_json, "w") as f:
            json.dump([{"slug": "test-post"}], f)

        page_ast = make_ast(source, tw_path)
        items = compiler.load_generate_static_params(page_ast, tw_path)
        self.assertIsNotNone(items)
        self.assertEqual(len(items), 1)
        self.assertEqual(items[0]["slug"], "test-post")

    def test_unknown_page_key_still_errors(self):
        """Unknown page keys should still raise CompilerError."""
        source = 'page { title "Test" unknownKey "value" }\nbody { h1 "Test" }'
        tw_path = os.path.join(compiler.HOME_DIR, "index.tw")
        with open(tw_path, "w") as f:
            f.write(source)
        with self.assertRaises(Exception):
            make_ast(source, tw_path)

    def test_generate_static_params_with_absolute_path(self):
        """generateStaticParams should work with absolute paths."""
        source = 'page {\n    title "Blog"\n    render static\n    generateStaticParams "ABS_PATH"\n}\nbody { h1 "Blog" }'
        tw_path = os.path.join(compiler.HOME_DIR, "index.tw")

        posts_json = os.path.join(compiler.HOME_DIR, "external_posts.json")
        with open(posts_json, "w") as f:
            json.dump([{"slug": "abs-post"}], f)

        source = source.replace("ABS_PATH", posts_json.replace("\\", "/"))
        with open(tw_path, "w") as f:
            f.write(source)
        page_ast = make_ast(source, tw_path)
        items = compiler.load_generate_static_params(page_ast, tw_path)
        self.assertIsNotNone(items)
        self.assertEqual(len(items), 1)


class TestRouteTWDiscovery(unittest.TestCase):
    """Test route.tw API route discovery in App Router mode."""

    def setUp(self):
        self.tmpdir = tempfile.mkdtemp()
        compiler.PROJECT_ROOT = self.tmpdir
        compiler.HOME_DIR = os.path.join(self.tmpdir, "[home]")
        compiler.BUILD_DIR = os.path.join(self.tmpdir, "dist")
        compiler.CACHE_DIR = os.path.join(self.tmpdir, ".tw", "cache")
        compiler.API_DIR = os.path.join(self.tmpdir, "[home]", "api")
        os.makedirs(compiler.HOME_DIR, exist_ok=True)

    def tearDown(self):
        shutil.rmtree(self.tmpdir, ignore_errors=True)

    def test_discover_app_router_api_routes_finds_route_tw(self):
        """discover_app_router_api_routes should find route.tw files."""
        api_dir = os.path.join(compiler.HOME_DIR, "api", "apps")
        os.makedirs(api_dir, exist_ok=True)

        with open(os.path.join(compiler.HOME_DIR, "page.tw"), "w") as f:
            f.write('page { title "Home" render static }\nbody { h1 "Home" }')

        route_tw = os.path.join(api_dir, "route.tw")
        with open(route_tw, "w") as f:
            f.write('export function get(request) {\n    return { status: 200, json: { apps: [] } };\n}\n')

        routes = framework.discover_app_router_api_routes()
        self.assertTrue(len(routes) > 0)
        found = False
        for r in routes:
            if r["route"] == "/api/apps":
                found = True
                self.assertEqual(r["lang"], "twm")
                break
        self.assertTrue(found, f"Route /api/apps not found in {routes}")

    def test_discover_api_routes_includes_app_router_routes(self):
        """discover_api_routes should include both legacy and App Router routes."""
        api_dir = os.path.join(compiler.HOME_DIR, "api", "users")
        os.makedirs(api_dir, exist_ok=True)

        with open(os.path.join(compiler.HOME_DIR, "page.tw"), "w") as f:
            f.write('page { title "Home" render static }\nbody { h1 "Home" }')

        route_tw = os.path.join(api_dir, "route.tw")
        with open(route_tw, "w") as f:
            f.write('export function get(request) { return { status: 200, json: {} }; }\n')

        routes = framework.discover_api_routes()
        found = any(r["route"] == "/api/users" for r in routes)
        self.assertTrue(found, f"Route /api/users not found in {routes}")

    def test_route_tw_in_nested_dynamic_dir(self):
        """route.tw should be discovered in dynamic route directories."""
        api_dir = os.path.join(compiler.HOME_DIR, "api", "apps", "[id]")
        os.makedirs(api_dir, exist_ok=True)

        with open(os.path.join(compiler.HOME_DIR, "page.tw"), "w") as f:
            f.write('page { title "Home" render static }\nbody { h1 "Home" }')

        route_tw = os.path.join(api_dir, "route.tw")
        with open(route_tw, "w") as f:
            f.write('export function get(request) { return { status: 200, json: {} }; }\n')

        routes = framework.discover_app_router_api_routes()
        found = any(":id" in r["route"] for r in routes)
        self.assertTrue(found, f"Dynamic API route not found in {routes}")

    def test_no_app_router_routes_when_legacy_mode(self):
        """discover_app_router_api_routes should return [] in legacy mode."""
        pages_dir = os.path.join(compiler.HOME_DIR, "pages")
        os.makedirs(pages_dir, exist_ok=True)

        routes = framework.discover_app_router_api_routes()
        self.assertEqual(len(routes), 0)

    def test_route_tw_with_different_http_methods(self):
        """route.tw files should support different HTTP method exports."""
        api_dir = os.path.join(compiler.HOME_DIR, "api", "submit")
        os.makedirs(api_dir, exist_ok=True)

        with open(os.path.join(compiler.HOME_DIR, "page.tw"), "w") as f:
            f.write('page { title "Home" render static }\nbody { h1 "Home" }')

        route_tw = os.path.join(api_dir, "route.tw")
        with open(route_tw, "w") as f:
            f.write('export function get(request) {\n    return { status: 200, json: { method: "GET" } };\n}\nexport function post(request) {\n    return { status: 201, json: { method: "POST" } };\n}\n')

        routes = framework.discover_app_router_api_routes()
        found = any(r["route"] == "/api/submit" for r in routes)
        self.assertTrue(found, f"Route /api/submit not found in {routes}")

    def test_route_tw_is_twm_syntax(self):
        """route.tw files should use the same .twm module syntax."""
        api_dir = os.path.join(compiler.HOME_DIR, "api", "health")
        os.makedirs(api_dir, exist_ok=True)

        with open(os.path.join(compiler.HOME_DIR, "page.tw"), "w") as f:
            f.write('page { title "Home" render static }\nbody { h1 "Home" }')

        route_tw = os.path.join(api_dir, "route.tw")
        route_content = 'export function get(request) {\n    return { status: 200, json: { healthy: true } };\n}'
        with open(route_tw, "w") as f:
            f.write(route_content)

        routes = framework.discover_app_router_api_routes()
        health_route = next((r for r in routes if r["route"] == "/api/health"), None)
        self.assertIsNotNone(health_route)
        self.assertEqual(health_route["lang"], "twm")

        from tw_framework.twm_parser import compile_twm_module_to_cjs
        js = compile_twm_module_to_cjs(route_content, module_id=route_tw)
        self.assertIn("get", js)
        self.assertIn("healthy", js)

    def test_multiple_route_tw_files(self):
        """Multiple route.tw files should all be discovered."""
        for name in ["apps", "users", "posts", "comments"]:
            d = os.path.join(compiler.HOME_DIR, "api", name)
            os.makedirs(d, exist_ok=True)
            with open(os.path.join(d, "route.tw"), "w") as f:
                f.write('export function get(request) { return { status: 200, json: {} }; }\n')

        with open(os.path.join(compiler.HOME_DIR, "page.tw"), "w") as f:
            f.write('page { title "Home" render static }\nbody { h1 "Home" }')

        routes = framework.discover_app_router_api_routes()
        route_names = {r["route"] for r in routes}
        self.assertIn("/api/apps", route_names)
        self.assertIn("/api/users", route_names)
        self.assertIn("/api/posts", route_names)
        self.assertIn("/api/comments", route_names)


if __name__ == "__main__":
    unittest.main()
