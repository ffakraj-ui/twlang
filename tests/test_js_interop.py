"""Tests for JS/NPM interop."""
import pytest
import sys
import os

sys.path.insert(0, os.path.join(os.path.dirname(__file__), ".."))

from tw_framework.js_interop import JSInterop, NPMPackage
from tw_framework.module_boundaries import CLIENT, SERVER


class TestNPMPackageResolution:
    def test_client_safe_package(self):
        interop = JSInterop()
        pkg = interop.resolve_npm_package("chart.js")
        assert pkg is not None
        assert pkg.boundary == CLIENT

    def test_server_only_package(self):
        interop = JSInterop()
        pkg = interop.resolve_npm_package("express")
        assert pkg is not None
        assert pkg.boundary == SERVER

    def test_unknown_package_defaults_to_client(self):
        interop = JSInterop()
        pkg = interop.resolve_npm_package("some-unknown-lib")
        assert pkg is not None
        assert pkg.boundary == CLIENT

    def test_scoped_package_resolution(self):
        interop = JSInterop()
        pkg = interop.resolve_npm_package("@tiptap/core")
        assert pkg is not None
        assert pkg.boundary == CLIENT


class TestDynamicImportDetection:
    def test_detect_dynamic_import(self):
        interop = JSInterop()
        source = 'const mod = import("chart.js")'
        results = interop.detect_dynamic_imports(source)
        assert len(results) == 1
        assert results[0]["path"] == "chart.js"
        assert results[0]["dynamic"] is True

    def test_no_dynamic_import(self):
        interop = JSInterop()
        source = 'import Chart from "chart.js"'
        results = interop.detect_dynamic_imports(source)
        assert len(results) == 0


class TestServerIsolation:
    def test_server_package_in_client_context_is_error(self):
        interop = JSInterop()
        from tw_framework.module_boundaries import ImportInfo
        imports = [ImportInfo(path="express", context="client", line=1, file="test.tw")]
        errors = interop.validate_server_isolation(imports)
        assert len(errors) == 1
        assert errors[0]["code"] == "TW3000"

    def test_client_package_in_client_context_is_ok(self):
        interop = JSInterop()
        from tw_framework.module_boundaries import ImportInfo
        imports = [ImportInfo(path="chart.js", context="client", line=1, file="test.tw")]
        errors = interop.validate_server_isolation(imports)
        assert len(errors) == 0
