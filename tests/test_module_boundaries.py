"""Tests for the module boundary system."""
import pytest
import sys
import os

sys.path.insert(0, os.path.join(os.path.dirname(__file__), ".."))

from tw_framework.module_boundaries import (
    ImportClassifier, ImportInfo, BoundaryViolation,
    SERVER, CLIENT, SHARED,
    ALL_TW_PACKAGES, TW_PACKAGE_BOUNDARIES,
    is_tw_package, get_package_boundary,
)


class TestImportClassification:
    def test_tw_state_is_client(self):
        c = ImportClassifier()
        assert c.classify_import("tw/state") == CLIENT

    def test_tw_router_is_client(self):
        c = ImportClassifier()
        assert c.classify_import("tw/router") == CLIENT

    def test_tw_form_is_client(self):
        c = ImportClassifier()
        assert c.classify_import("tw/form") == CLIENT

    def test_tw_realtime_is_client(self):
        c = ImportClassifier()
        assert c.classify_import("tw/realtime") == CLIENT

    def test_tw_auth_is_shared(self):
        c = ImportClassifier()
        assert c.classify_import("tw/auth") == SHARED

    def test_tw_fetch_is_shared(self):
        c = ImportClassifier()
        assert c.classify_import("tw/fetch") == SHARED

    def test_tw_image_is_shared(self):
        c = ImportClassifier()
        assert c.classify_import("tw/image") == SHARED

    def test_tw_server_is_server(self):
        c = ImportClassifier()
        assert c.classify_import("tw/server") == SERVER

    def test_npm_package_is_client(self):
        c = ImportClassifier()
        assert c.classify_import("chart.js") == CLIENT

    def test_scoped_npm_is_client(self):
        c = ImportClassifier()
        assert c.classify_import("@tiptap/core") == CLIENT

    def test_twm_file_is_server(self):
        c = ImportClassifier()
        assert c.classify_import("api.twm") == SERVER

    def test_lib_import_is_server(self):
        c = ImportClassifier()
        assert c.classify_import("@lib/database") == SERVER

    def test_tw_component_is_shared(self):
        c = ImportClassifier()
        assert c.classify_import("Button") == SHARED


class TestBoundaryValidation:
    def test_client_importing_server_is_error(self):
        c = ImportClassifier()
        imports = [ImportInfo(path="tw/server", context="client", line=1, file="test.tw")]
        violations = c.validate_imports(imports)
        assert len(violations) == 1
        assert violations[0].code == "TW2000"

    def test_server_importing_client_is_error(self):
        c = ImportClassifier()
        imports = [ImportInfo(path="tw/state", context="server", line=1, file="test.tw")]
        violations = c.validate_imports(imports)
        assert len(violations) == 1
        assert violations[0].code == "TW2001"

    def test_valid_imports_no_violations(self):
        c = ImportClassifier()
        imports = [
            ImportInfo(path="tw/state", context="client", line=1, file="test.tw"),
            ImportInfo(path="tw/server", context="server", line=2, file="test.tw"),
        ]
        violations = c.validate_imports(imports)
        assert len(violations) == 0

    def test_get_client_imports_filters_correctly(self):
        c = ImportClassifier()
        imports = [
            ImportInfo(path="tw/state", context="client", line=1),
            ImportInfo(path="tw/server", context="server", line=2),
            ImportInfo(path="tw/fetch", context="client", line=3),
        ]
        client_imports = c.get_client_imports(imports)
        paths = [imp.path for imp in client_imports]
        assert "tw/state" in paths
        assert "tw/fetch" in paths
        assert "tw/server" not in paths


class TestSourceScanning:
    def test_scan_simple_import(self):
        c = ImportClassifier()
        source = 'import "Button"'
        imports = c.scan_source_imports(source, "test.tw")
        assert len(imports) == 1
        assert imports[0].path == "Button"

    def test_scan_named_import(self):
        c = ImportClassifier()
        source = 'import { store } from "tw/state"'
        imports = c.scan_source_imports(source, "test.tw")
        assert len(imports) == 1
        assert imports[0].path == "tw/state"

    def test_scan_default_import(self):
        c = ImportClassifier()
        source = 'import Chart from "chart.js"'
        imports = c.scan_source_imports(source, "test.tw")
        assert len(imports) == 1
        assert imports[0].path == "chart.js"

    def test_scan_multiple_imports(self):
        c = ImportClassifier()
        source = """import "Button"
import { store } from "tw/state"
import Chart from "chart.js"
"""
        imports = c.scan_source_imports(source, "test.tw")
        assert len(imports) == 3

    def test_is_tw_package(self):
        assert is_tw_package("tw/state") is True
        assert is_tw_package("tw/router") is True
        assert is_tw_package("chart.js") is False

    def test_get_package_boundary(self):
        assert get_package_boundary("tw/state") == CLIENT
        assert get_package_boundary("tw/auth") == SHARED
        assert get_package_boundary("tw/server") == SERVER


class TestModuleSourceClassification:
    def test_server_api_detected(self):
        c = ImportClassifier()
        source = "const fs = require('fs')"
        assert c.classify_module_source(source) == SERVER

    def test_client_api_detected(self):
        c = ImportClassifier()
        source = "document.getElementById('app')"
        assert c.classify_module_source(source) == CLIENT

    def test_pure_module_is_shared(self):
        c = ImportClassifier()
        source = "function add(a, b) { return a + b; }"
        assert c.classify_module_source(source) == SHARED
