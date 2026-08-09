"""Tests for error boundaries."""
import pytest
import sys
import os

sys.path.insert(0, os.path.join(os.path.dirname(__file__), ".."))

from tw_framework.error_boundaries import (
    ErrorInfo, render_error_page, render_404, render_500,
    render_error_from_exception, render_loading, get_error_boundary_js,
)


class TestErrorPages:
    def test_render_404(self):
        html = render_404("/nonexistent")
        assert "404" in html
        assert "Not Found" in html

    def test_render_500(self):
        html = render_500("Something broke")
        assert "500" in html
        assert "Server Error" in html

    def test_render_404_production_safe(self):
        html = render_404("/path", is_dev=False)
        assert "does not exist" in html
        assert "Stack Trace" not in html

    def test_render_error_with_dev_details(self):
        error = ErrorInfo(
            code=500,
            title="Test Error",
            message="Something went wrong",
            stack="Error: at line 1\n    at test()",
            is_dev=True,
        )
        html = render_error_page(error)
        assert "Stack Trace" in html
        assert "Error: at line 1" in html

    def test_render_error_production_no_stack(self):
        error = ErrorInfo(
            code=500,
            title="Test Error",
            message="Internal error",
            stack="secret stack trace",
            is_dev=False,
        )
        html = render_error_page(error)
        assert "secret stack trace" not in html

    def test_render_error_from_exception(self):
        try:
            raise ValueError("Test error")
        except ValueError as e:
            html = render_error_from_exception(e, is_dev=True)
            assert "ValueError" in html
            assert "Test error" in html

    def test_render_loading(self):
        html = render_loading()
        assert "tw-loading" in html

    def test_get_error_boundary_js(self):
        js = get_error_boundary_js()
        assert "__tw.errorBoundary" in js
        assert "catch" in js


class TestErrorInfo:
    def test_error_info_defaults(self):
        info = ErrorInfo()
        assert info.code == 500
        assert info.is_dev is False
