"""
Tests for v0.7.2 features:
1. Built-in Icons (SVG rendering, no JS)
2. App Router scaffold (tw create generates App Router structure)
"""
import os
import sys
import shutil
import tempfile
import unittest

PROJECT_ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
sys.path.insert(0, PROJECT_ROOT)

from tw_framework import compiler
from tw_framework.icons import get_icon_svg, ICONS, list_icons


class TestIcons(unittest.TestCase):
    """Test built-in SVG icons."""

    def test_icons_dict_has_entries(self):
        """ICONS dict should have 50+ icons."""
        self.assertGreater(len(ICONS), 50)

    def test_get_icon_svg_known_icon(self):
        """get_icon_svg should return SVG for a known icon."""
        svg = get_icon_svg("home")
        self.assertIn("<svg", svg)
        self.assertIn("</svg>", svg)
        self.assertIn("path", svg)

    def test_get_icon_svg_unknown_icon(self):
        """get_icon_svg should return comment for unknown icon."""
        svg = get_icon_svg("nonexistent-icon-xyz")
        self.assertIn("Unknown icon", svg)

    def test_get_icon_svg_with_size(self):
        """get_icon_svg should respect size parameter."""
        svg = get_icon_svg("search", size=32)
        self.assertIn('width="32"', svg)
        self.assertIn('height="32"', svg)

    def test_get_icon_svg_default_size(self):
        """get_icon_svg should default to 24px."""
        svg = get_icon_svg("menu")
        self.assertIn('width="24"', svg)
        self.assertIn('height="24"', svg)

    def test_get_icon_svg_with_class(self):
        """get_icon_svg should include class attribute."""
        svg = get_icon_svg("user", class_name="my-icon")
        self.assertIn('class="my-icon"', svg)

    def test_get_icon_svg_no_class_when_empty(self):
        """get_icon_svg should not include class when empty."""
        svg = get_icon_svg("check", class_name="")
        self.assertNotIn("class=", svg)

    def test_get_icon_svg_has_svg_namespace(self):
        """SVG should have xmlns attribute."""
        svg = get_icon_svg("star")
        self.assertIn("xmlns", svg)
        self.assertIn("http://www.w3.org/2000/svg", svg)

    def test_get_icon_svg_has_stroke(self):
        """SVG should use stroke-based rendering."""
        svg = get_icon_svg("heart")
        self.assertIn("stroke", svg)

    def test_list_icons_returns_sorted(self):
        """list_icons should return sorted list."""
        icons = list_icons()
        self.assertIsInstance(icons, list)
        self.assertEqual(icons, sorted(icons))
        self.assertIn("home", icons)
        self.assertIn("search", icons)

    def test_popular_icons_exist(self):
        """Popular icons should be available."""
        popular = ["home", "search", "menu", "close", "arrow-right", "arrow-left",
                   "check", "chevron-down", "user", "settings", "heart", "star",
                   "github", "twitter", "mail", "phone", "download", "upload",
                   "plus", "minus", "edit", "trash", "sun", "moon", "code",
                   "globe", "image", "link", "bell", "play", "pause"]
        for name in popular:
            self.assertIn(name, ICONS, f"Missing popular icon: {name}")


class TestIconComponentRendering(unittest.TestCase):
    """Test Icon component rendering through the compiler."""

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

    def _make_ast(self, source, tw_path):
        tokens = compiler.tokenize_tw(source)
        base_dir = os.path.dirname(tw_path)
        return compiler.build_tw_ast(tokens, base_dir, tw_path, source)

    def test_icon_component_renders_svg(self):
        """Icon component should render inline SVG."""
        source = 'page {\n    title "Test"\n    render static\n}\n\nbody {\n    Icon { name "home" }\n}'
        tw_path = os.path.join(compiler.HOME_DIR, "page.tw")
        with open(tw_path, "w") as f:
            f.write(source)
        page_ast = self._make_ast(source, tw_path)
        context = compiler.create_base_context(page_ast, tw_path)
        html, _, _ = compiler.render_elements_html(page_ast.body, context)
        self.assertIn("<svg", html)
        self.assertIn("</svg>", html)

    def test_icon_component_with_size(self):
        """Icon component should respect size prop."""
        source = 'page {\n    title "Test"\n    render static\n}\n\nbody {\n    Icon { name "search", size 32 }\n}'
        tw_path = os.path.join(compiler.HOME_DIR, "page.tw")
        with open(tw_path, "w") as f:
            f.write(source)
        page_ast = self._make_ast(source, tw_path)
        context = compiler.create_base_context(page_ast, tw_path)
        html, _, _ = compiler.render_elements_html(page_ast.body, context)
        self.assertIn('width="32"', html)
        self.assertIn('height="32"', html)

    def test_icon_component_with_class(self):
        """Icon component should pass class prop."""
        source = 'page {\n    title "Test"\n    render static\n}\n\nbody {\n    Icon { name "user", class "nav-icon" }\n}'
        tw_path = os.path.join(compiler.HOME_DIR, "page.tw")
        with open(tw_path, "w") as f:
            f.write(source)
        page_ast = self._make_ast(source, tw_path)
        context = compiler.create_base_context(page_ast, tw_path)
        html, _, _ = compiler.render_elements_html(page_ast.body, context)
        self.assertIn('class="nav-icon"', html)

    def test_icon_component_zero_js(self):
        """Page with only Icon should be Zero-JS."""
        source = 'page {\n    title "Test"\n    render static\n}\n\nbody {\n    div {\n        Icon { name "home" }\n        Icon { name "search" }\n    }\n}'
        tw_path = os.path.join(compiler.HOME_DIR, "page.tw")
        with open(tw_path, "w") as f:
            f.write(source)
        page_ast = self._make_ast(source, tw_path)
        context = compiler.create_base_context(page_ast, tw_path)
        html, needs_router, _ = compiler.render_elements_html(page_ast.body, context)
        # Icons don't need router runtime
        self.assertFalse(needs_router)

    def test_multiple_icons_in_page(self):
        """Multiple icons should all render."""
        source = 'page {\n    title "Test"\n    render static\n}\n\nbody {\n    nav {\n        Icon { name "home" }\n        Icon { name "search" }\n        Icon { name "menu" }\n        Icon { name "user" }\n    }\n}'
        tw_path = os.path.join(compiler.HOME_DIR, "page.tw")
        with open(tw_path, "w") as f:
            f.write(source)
        page_ast = self._make_ast(source, tw_path)
        context = compiler.create_base_context(page_ast, tw_path)
        html, _, _ = compiler.render_elements_html(page_ast.body, context)
        svg_count = html.count("<svg")
        self.assertEqual(svg_count, 4)


class TestAppRouterScaffold(unittest.TestCase):
    """Test that tw create generates App Router structure."""

    def setUp(self):
        self.tmpdir = tempfile.mkdtemp()

    def tearDown(self):
        shutil.rmtree(self.tmpdir, ignore_errors=True)

    def test_create_generates_app_router_files(self):
        """tw create should generate App Router files (page.tw, layout.tw, etc.)."""
        from tw_framework.cli import create_project
        create_project("test-site", parent_dir=self.tmpdir)

        site = os.path.join(self.tmpdir, "test-site")
        home = os.path.join(site, "[home]")

        # App Router files
        self.assertTrue(os.path.exists(os.path.join(home, "layout.tw")), "layout.tw missing")
        self.assertTrue(os.path.exists(os.path.join(home, "page.tw")), "page.tw missing")
        self.assertTrue(os.path.exists(os.path.join(home, "not-found.tw")), "not-found.tw missing")
        self.assertTrue(os.path.exists(os.path.join(home, "style.tss")), "style.tss missing")

    def test_no_legacy_files(self):
        """tw create should NOT generate legacy files."""
        from tw_framework.cli import create_project
        create_project("test-site2", parent_dir=self.tmpdir)

        site = os.path.join(self.tmpdir, "test-site2")
        home = os.path.join(site, "[home]")

        # Legacy files should NOT exist
        self.assertFalse(os.path.exists(os.path.join(home, "index.tw")), "legacy index.tw should not exist")
        self.assertFalse(os.path.exists(os.path.join(home, "pages")), "legacy pages/ dir should not exist")
        self.assertFalse(os.path.exists(os.path.join(home, "layouts")), "legacy layouts/ dir should not exist")

    def test_scaffold_has_children_keyword(self):
        """layout.tw should use children keyword."""
        from tw_framework.cli import create_project
        create_project("test-site3", parent_dir=self.tmpdir)

        site = os.path.join(self.tmpdir, "test-site3")
        layout_path = os.path.join(site, "[home]", "layout.tw")
        with open(layout_path) as f:
            layout = f.read()
        self.assertIn("children", layout)

    def test_scaffold_has_route_tw(self):
        """Scaffold should include route.tw API files."""
        from tw_framework.cli import create_project
        create_project("test-site4", parent_dir=self.tmpdir)

        site = os.path.join(self.tmpdir, "test-site4")
        home = os.path.join(site, "[home]")

        # API route files
        self.assertTrue(os.path.exists(os.path.join(home, "api", "contact", "route.tw")))
        self.assertTrue(os.path.exists(os.path.join(home, "api", "users", "route.tw")))

    def test_scaffold_has_nested_pages(self):
        """Scaffold should have nested page.tw files."""
        from tw_framework.cli import create_project
        create_project("test-site5", parent_dir=self.tmpdir)

        site = os.path.join(self.tmpdir, "test-site5")
        home = os.path.join(site, "[home]")

        self.assertTrue(os.path.exists(os.path.join(home, "about", "page.tw")))
        self.assertTrue(os.path.exists(os.path.join(home, "counter", "page.tw")))
        self.assertTrue(os.path.exists(os.path.join(home, "contact", "page.tw")))

    def test_scaffold_layout_is_tw_component(self):
        """layout.tw should be a TW component, not HTML template."""
        from tw_framework.cli import create_project
        create_project("test-site6", parent_dir=self.tmpdir)

        site = os.path.join(self.tmpdir, "test-site6")
        layout_path = os.path.join(site, "[home]", "layout.tw")
        with open(layout_path) as f:
            layout = f.read()

        # Should have page { } block (TW syntax, not HTML)
        self.assertIn("page {", layout)
        # Should have body { } block
        self.assertIn("body {", layout)
        # Should NOT have {slot} (legacy placeholder)
        self.assertNotIn("{slot}", layout)
        # Should NOT have {head} (legacy placeholder)
        self.assertNotIn("{head}", layout)

    def test_scaffold_counter_page_has_state(self):
        """Counter page should have state block."""
        from tw_framework.cli import create_project
        create_project("test-site7", parent_dir=self.tmpdir)

        site = os.path.join(self.tmpdir, "test-site7")
        counter_path = os.path.join(site, "[home]", "counter", "page.tw")
        with open(counter_path) as f:
            counter = f.read()
        self.assertIn("state {", counter)


if __name__ == "__main__":
    unittest.main()
