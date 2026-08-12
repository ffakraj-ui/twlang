"""Tests for the runtime loader."""
import pytest
import sys
import os

sys.path.insert(0, os.path.join(os.path.dirname(__file__), ".."))

from tw_framework.runtime_loader import PageCapability, RuntimeLoader


class TestPageCapability:
    def test_default_is_zero_js(self):
        cap = PageCapability()
        assert cap.is_zero_js is True

    def test_needs_state_disables_zero_js(self):
        cap = PageCapability(needs_state=True)
        assert cap.is_zero_js is False

    def test_needs_router_disables_zero_js(self):
        cap = PageCapability(needs_router=True)
        assert cap.is_zero_js is False

    def test_needs_npm_packages_disables_zero_js(self):
        cap = PageCapability(needs_npm_packages=["chart.js"])
        assert cap.is_zero_js is False


class TestRuntimeLoader:
    def test_analyze_static_page(self):
        loader = RuntimeLoader()
        cap = loader.analyze_page_capabilities(
            source="<h1>Hello</h1>",
            page_ast=None,
        )
        assert cap.is_zero_js is True

    def test_analyze_state_page(self):
        loader = RuntimeLoader()
        cap = loader.analyze_page_capabilities(
            source="state { count 0 }",
            page_ast=None,
        )
        assert cap.is_zero_js is False
        assert cap.needs_state is True

    def test_analyze_router_page(self):
        loader = RuntimeLoader()
        cap = loader.analyze_page_capabilities(
            source='Link { href "/dashboard" } { "Dashboard" }',
            page_ast=None,
        )
        assert cap.needs_router is True

    def test_analyze_realtime_page(self):
        loader = RuntimeLoader()
        cap = loader.analyze_page_capabilities(
            source="socket('/api/events')",
            page_ast=None,
        )
        assert cap.needs_realtime is True

    def test_analyze_form_page(self):
        loader = RuntimeLoader()
        cap = loader.analyze_page_capabilities(
            source='Form { action "/api/contact" } { }',
            page_ast=None,
        )
        assert cap.needs_forms is True

    def test_generate_runtime_tags_zero_js(self):
        loader = RuntimeLoader()
        cap = PageCapability()
        tags = loader.generate_runtime_tags(cap)
        assert tags == ""

    def test_generate_runtime_tags_with_state(self):
        loader = RuntimeLoader()
        cap = PageCapability(needs_state=True)
        tags = loader.generate_runtime_tags(cap)
        assert "state" in tags
        assert "base" in tags

    def test_get_required_runtimes_zero_js(self):
        loader = RuntimeLoader()
        cap = PageCapability()
        runtimes = loader.get_required_runtimes(cap)
        assert len(runtimes) == 0

    def test_get_required_runtimes_interactive(self):
        loader = RuntimeLoader()
        cap = PageCapability(needs_state=True, needs_router=True)
        runtimes = loader.get_required_runtimes(cap)
        assert "base" in runtimes
        assert "state" in runtimes
        assert "router" in runtimes
