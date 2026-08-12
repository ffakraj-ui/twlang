"""Tests for tw/router client-side routing."""
import pytest
import sys
import os

sys.path.insert(0, os.path.join(os.path.dirname(__file__), ".."))

from tw_framework.tw_router.router import (
    Router, Route, LinkRenderer,
    parse_route_pattern, match_route,
)


class TestRouteMatching:
    def test_static_route_match(self):
        assert match_route("/about", "/about") == {}

    def test_static_route_no_match(self):
        assert match_route("/about", "/blog") is None

    def test_dynamic_route_match(self):
        result = match_route("/blog/[slug]", "/blog/hello-world")
        assert result == {"slug": "hello-world"}

    def test_dynamic_route_no_match(self):
        assert match_route("/blog/[slug]", "/about") is None

    def test_nested_dynamic_route(self):
        result = match_route("/shop/[category]/[id]", "/shop/electronics/123")
        assert result == {"category": "electronics", "id": "123"}

    def test_route_length_mismatch(self):
        assert match_route("/blog/[slug]", "/blog/a/b") is None


class TestRouter:
    def test_add_and_resolve_static(self):
        router = Router()
        router.add(Route(path="/about", page="about"))
        result = router.resolve("/about")
        assert result is not None
        route, params = result
        assert route.path == "/about"
        assert params == {}

    def test_add_and_resolve_dynamic(self):
        router = Router()
        router.add(Route(path="/blog/[slug]", page="blog", dynamic=True))
        result = router.resolve("/blog/hello")
        assert result is not None
        route, params = result
        assert params == {"slug": "hello"}

    def test_resolve_not_found(self):
        router = Router()
        router.add(Route(path="/about", page="about"))
        assert router.resolve("/nonexistent") is None


class TestLinkRenderer:
    def test_render_link(self):
        html = LinkRenderer.render_link("/dashboard", "Dashboard")
        assert 'href="/dashboard"' in html
        assert 'data-tw-link="/dashboard"' in html
        assert "Dashboard" in html

    def test_render_link_with_class(self):
        html = LinkRenderer.render_link("/about", "About", "nav-link")
        assert 'class="nav-link"' in html

    def test_render_link_with_attrs(self):
        html = LinkRenderer.render_link_with_attrs("/home", "Home", 'id="logo"')
        assert 'id="logo"' in html
        assert 'data-tw-link="/home"' in html


class TestParseRoutePattern:
    def test_static_pattern(self):
        result = parse_route_pattern("/about")
        assert result["is_dynamic"] is False
        assert len(result["segments"]) == 1

    def test_dynamic_pattern(self):
        result = parse_route_pattern("/blog/[slug]")
        assert result["is_dynamic"] is True
        assert "slug" in result["param_names"]

    def test_nested_dynamic_pattern(self):
        result = parse_route_pattern("/shop/[category]/[id]")
        assert result["is_dynamic"] is True
        assert "category" in result["param_names"]
        assert "id" in result["param_names"]


class TestRouterRuntime:
    def test_get_router_runtime_js(self):
        from tw_framework.tw_router.runtime import get_router_runtime_js
        js = get_router_runtime_js()
        assert "__tw.router" in js
        assert "goto" in js
        assert "prefetch" in js
