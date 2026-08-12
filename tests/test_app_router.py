"""
Tests for the TW App Router system (v0.7.0).

Tests:
1. Route discovery — static, dynamic, route groups, catch-all
2. Layout resolution — nested layouts, root layout
3. {children} slot — parsing and rendering
4. URL building — route groups excluded, dynamic segments
5. compose_nested_layouts — layout composition
"""

import os
import sys
import tempfile
import shutil
import pytest

# Add framework to path
sys.path.insert(0, os.path.join(os.path.dirname(__file__), ".."))

from tw_framework.app_router import (
    classify_segment,
    build_url_path,
    find_layouts_for_dir,
    discover_routes,
    match_route,
    route_to_output_path,
    has_app_router_structure,
    has_legacy_structure,
    RouteSegment,
    RouteInfo,
    LayoutInfo,
    ROUTE_GROUP_RE,
    DYNAMIC_SEGMENT_RE,
    CATCH_ALL_RE,
)


class TestClassifySegment:
    """Test segment classification from folder names."""

    def test_static_segment(self):
        seg = classify_segment("blog")
        assert seg.type == "static"
        assert seg.raw == "blog"
        assert seg.param_name == ""
        assert seg.is_url_segment is True

    def test_route_group(self):
        seg = classify_segment("(main)")
        assert seg.type == "route_group"
        assert seg.param_name == "main"
        assert seg.is_url_segment is False

    def test_route_group_auth(self):
        seg = classify_segment("(auth)")
        assert seg.type == "route_group"
        assert seg.param_name == "auth"

    def test_dynamic_segment(self):
        seg = classify_segment("[slug]")
        assert seg.type == "dynamic"
        assert seg.param_name == "slug"
        assert seg.is_url_segment is True

    def test_dynamic_segment_id(self):
        seg = classify_segment("[id]")
        assert seg.type == "dynamic"
        assert seg.param_name == "id"

    def test_catch_all(self):
        seg = classify_segment("[...slug]")
        assert seg.type == "catch_all"
        assert seg.param_name == "slug"

    def test_catch_all_path(self):
        seg = classify_segment("[...path]")
        assert seg.type == "catch_all"
        assert seg.param_name == "path"


class TestBuildUrlPath:
    """Test URL path building from segments."""

    def test_root(self):
        assert build_url_path([]) == "/"

    def test_static_only(self):
        segs = [classify_segment("blog")]
        assert build_url_path(segs) == "/blog"

    def test_nested_static(self):
        segs = [classify_segment("blog"), classify_segment("post")]
        assert build_url_path(segs) == "/blog/post"

    def test_route_group_excluded(self):
        segs = [classify_segment("(main)"), classify_segment("blog")]
        assert build_url_path(segs) == "/blog"

    def test_dynamic_segment(self):
        segs = [classify_segment("blog"), classify_segment("[slug]")]
        assert build_url_path(segs) == "/blog/:slug"

    def test_catch_all(self):
        segs = [classify_segment("[...path]")]
        assert build_url_path(segs) == "/*path"

    def test_route_group_with_dynamic(self):
        segs = [classify_segment("(main)"), classify_segment("app"), classify_segment("[slug]")]
        assert build_url_path(segs) == "/app/:slug"


class TestFindLayoutsForDir:
    """Test layout discovery by walking up directory tree."""

    def test_finds_layouts(self, tmp_path):
        # Create structure: home/layout.tw, home/(main)/layout.tw, home/(main)/blog/page.tw
        home = tmp_path / "[home]"
        main = home / "(main)"
        blog = main / "blog"
        blog.mkdir(parents=True)

        (home / "layout.tw").write_text("body { children }")
        (main / "layout.tw").write_text("body { children }")

        layouts = find_layouts_for_dir(str(blog), str(home))
        assert len(layouts) == 2
        # Root layout first (outermost)
        assert layouts[0].is_root is True
        assert layouts[1].is_root is False

    def test_no_layouts(self, tmp_path):
        home = tmp_path / "[home]"
        blog = home / "blog"
        blog.mkdir(parents=True)

        layouts = find_layouts_for_dir(str(blog), str(home))
        assert len(layouts) == 0

    def test_three_levels(self, tmp_path):
        home = tmp_path / "[home]"
        main = home / "(main)"
        slug = main / "blog" / "[slug]"
        slug.mkdir(parents=True)

        (home / "layout.tw").write_text("body { children }")
        (main / "layout.tw").write_text("body { children }")
        (slug / "layout.tw").write_text("body { children }")

        layouts = find_layouts_for_dir(str(slug), str(home))
        assert len(layouts) == 3
        assert layouts[0].is_root is True
        assert layouts[2].depth >= layouts[1].depth >= layouts[0].depth


class TestDiscoverRoutes:
    """Test full route discovery."""

    def test_discovers_page_tw(self, tmp_path):
        home = tmp_path / "[home]"
        home.mkdir()
        (home / "page.tw").write_text("body { h1 \"Home\" }")

        routes = discover_routes(str(home))
        assert len(routes) == 1
        assert routes[0].url_path == "/"
        assert not routes[0].is_api

    def test_discovers_nested_pages(self, tmp_path):
        home = tmp_path / "[home]"
        (home / "blog").mkdir(parents=True)
        (home / "blog" / "page.tw").write_text("body { h1 \"Blog\" }")

        routes = discover_routes(str(home))
        assert len(routes) == 1
        assert routes[0].url_path == "/blog"

    def test_route_group_excluded_from_url(self, tmp_path):
        home = tmp_path / "[home]"
        (home / "(main)" / "about").mkdir(parents=True)
        (home / "(main)" / "about" / "page.tw").write_text("body { h1 \"About\" }")

        routes = discover_routes(str(home))
        assert len(routes) == 1
        assert routes[0].url_path == "/about"

    def test_dynamic_route(self, tmp_path):
        home = tmp_path / "[home]"
        (home / "blog" / "[slug]").mkdir(parents=True)
        (home / "blog" / "[slug]" / "page.tw").write_text("body { h1 \"Post\" }")

        routes = discover_routes(str(home))
        assert len(routes) == 1
        assert routes[0].url_path == "/blog/:slug"

    def test_collects_layouts(self, tmp_path):
        home = tmp_path / "[home]"
        (home / "(main)" / "blog").mkdir(parents=True)
        (home / "page.tw").write_text("body { children }")
        (home / "layout.tw").write_text("body { children }")
        (home / "(main)" / "layout.tw").write_text("body { children }")
        (home / "(main)" / "blog" / "page.tw").write_text("body { h1 \"Blog\" }")

        routes = discover_routes(str(home))
        # Find the blog route
        blog_route = [r for r in routes if r.url_path == "/blog"][0]
        assert len(blog_route.layout_files) == 2

    def test_api_route(self, tmp_path):
        home = tmp_path / "[home]"
        (home / "api" / "apps").mkdir(parents=True)
        (home / "api" / "apps" / "route.tw").write_text("# API route")

        routes = discover_routes(str(home))
        api_routes = [r for r in routes if r.is_api]
        assert len(api_routes) == 1


class TestMatchRoute:
    """Test URL matching against routes."""

    def test_static_match(self):
        route = RouteInfo(
            file_path="/test/page.tw",
            url_path="/blog",
            segments=[classify_segment("blog")],
        )
        match, params = match_route([route], "/blog")
        assert match is not None
        assert params == {}

    def test_dynamic_match(self):
        route = RouteInfo(
            file_path="/test/[slug]/page.tw",
            url_path="/blog/:slug",
            segments=[classify_segment("blog"), classify_segment("[slug]")],
        )
        match, params = match_route([route], "/blog/my-post")
        assert match is not None
        assert params == {"slug": "my-post"}

    def test_no_match(self):
        route = RouteInfo(
            file_path="/test/page.tw",
            url_path="/blog",
            segments=[classify_segment("blog")],
        )
        match, params = match_route([route], "/about")
        assert match is None
        assert params is None

    def test_root_match(self):
        route = RouteInfo(
            file_path="/test/page.tw",
            url_path="/",
            segments=[],
        )
        match, params = match_route([route], "/")
        assert match is not None

    def test_static_preferred_over_dynamic(self):
        static_route = RouteInfo(
            file_path="/test/about/page.tw",
            url_path="/about",
            segments=[classify_segment("about")],
        )
        dynamic_route = RouteInfo(
            file_path="/test/[slug]/page.tw",
            url_path="/:slug",
            segments=[classify_segment("[slug]")],
        )
        match, params = match_route([static_route, dynamic_route], "/about")
        assert match is static_route


class TestRouteToOutputPath:
    """Test URL to output path conversion."""

    def test_root(self):
        assert route_to_output_path("/") == "index.html"

    def test_simple(self):
        assert route_to_output_path("/about") == "about/index.html"

    def test_nested(self):
        assert route_to_output_path("/blog/my-post") == "blog/my-post/index.html"


class TestHasAppRouterStructure:
    """Test detection of App Router vs legacy structure."""

    def test_app_router_with_page(self, tmp_path):
        home = tmp_path / "[home]"
        home.mkdir()
        (home / "page.tw").write_text("body { }")
        assert has_app_router_structure(str(home)) is True

    def test_app_router_with_layout(self, tmp_path):
        home = tmp_path / "[home]"
        home.mkdir()
        (home / "layout.tw").write_text("body { }")
        assert has_app_router_structure(str(home)) is True

    def test_no_structure(self, tmp_path):
        home = tmp_path / "[home]"
        home.mkdir()
        assert has_app_router_structure(str(home)) is False

    def test_legacy_structure(self, tmp_path):
        home = tmp_path / "[home]"
        (home / "pages").mkdir(parents=True)
        (home / "layouts").mkdir(parents=True)
        assert has_legacy_structure(str(home)) is True

    def test_not_legacy(self, tmp_path):
        home = tmp_path / "[home]"
        home.mkdir()
        assert has_legacy_structure(str(home)) is False


class TestChildrenKeywordParsing:
    """Test that `children` keyword is parsed correctly in .tw files."""

    def test_children_in_body(self):
        """children keyword should be parseable in body block."""
        from tw_framework.compiler import tokenize_tw, build_tw_ast, ElementNode

        source = "body { children }"
        tokens = tokenize_tw(source)
        page = build_tw_ast(tokens, ".", "test.tw", source)
        assert len(page.body) == 1
        assert isinstance(page.body[0], ElementNode)
        assert page.body[0].tag == "children"

    def test_children_inside_element(self):
        """children keyword should be parseable inside an element block."""
        from tw_framework.compiler import tokenize_tw, build_tw_ast, ElementNode

        source = "body { div { class \"wrapper\" children } }"
        tokens = tokenize_tw(source)
        page = build_tw_ast(tokens, ".", "test.tw", source)
        assert len(page.body) == 1
        div = page.body[0]
        assert div.tag == "div"
        # children should be a child of div
        children_nodes = [c for c in div.children if isinstance(c, ElementNode) and c.tag == "children"]
        assert len(children_nodes) == 1


class TestComposeNestedLayouts:
    """Test nested layout composition."""

    def test_single_layout(self, tmp_path):
        """A single root layout should wrap page content."""
        from tw_framework.compiler import (
            compose_nested_layouts,
            load_layout_ast,
            render_elements_html,
            load_page_ast_from_file,
        )

        # Create layout
        layout_path = tmp_path / "layout.tw"
        layout_path.write_text("body { div { class \"wrapper\" children } }")

        # Call compose_nested_layouts
        html = compose_nested_layouts(
            layout_files=[str(layout_path)],
            page_body_html="<p>Page content</p>",
            page_title="Test",
            page_head_extras="",
            page_style_blocks="",
            page_runtime_scripts="",
            context={},
            page=None,
            zero_js=True,
        )

        assert "<!DOCTYPE" in html
        assert "wrapper" in html
        assert "Page content" in html
        assert "{children}" not in html

    def test_nested_layouts(self, tmp_path):
        """Two nested layouts should compose correctly."""
        from tw_framework.compiler import compose_nested_layouts

        root_layout = tmp_path / "root.tw"
        root_layout.write_text("body { div { class \"root\" children } }")

        main_layout = tmp_path / "main.tw"
        main_layout.write_text("body { nav { class \"navbar\" } div { class \"content\" children } }")

        html = compose_nested_layouts(
            layout_files=[str(root_layout), str(main_layout)],
            page_body_html="<p>Page content</p>",
            page_title="Test",
            page_head_extras="",
            page_style_blocks="",
            page_runtime_scripts="",
            context={},
            page=None,
            zero_js=True,
        )

        assert "<!DOCTYPE" in html
        assert "root" in html
        assert "navbar" in html
        assert "content" in html
        assert "Page content" in html
        assert "{children}" not in html


if __name__ == "__main__":
    pytest.main([__file__, "-v"])
