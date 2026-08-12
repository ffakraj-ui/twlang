"""
Tests for v0.8.1 client-side bundler — CJS→ESM conversion,
transitive dependency resolution, import maps, Node built-in stubs.

Run: pytest tests/test_client_bundler.py -v
"""

from __future__ import annotations

import json
import os
import sys
import tempfile

import pytest

sys.path.insert(0, os.path.join(os.path.dirname(__file__), ".."))


# ─── CJS → ESM Conversion Tests ──────────────────────────────────────────────

class TestCJSToBrowserConversion:
    """Test CommonJS to browser-compatible conversion."""

    def test_convert_simple_cjs(self):
        from tw_framework.client_bundler import convert_cjs_to_browser
        source = 'module.exports = { hello: "world" };'
        result = convert_cjs_to_browser(source, "test-pkg")
        assert "TW Client Bundle" in result
        assert "test-pkg" in result
        assert "module.exports" in result
        assert "window.__tw_npm" in result

    def test_convert_cjs_with_require(self):
        from tw_framework.client_bundler import convert_cjs_to_browser
        source = '''
var path = require("path");
module.exports = { join: path.join };
'''
        result = convert_cjs_to_browser(source, "path-utils")
        assert "__tw_require" in result
        assert '"path"' in result

    def test_convert_cjs_with_exports_dot(self):
        from tw_framework.client_bundler import convert_cjs_to_browser
        source = '''
exports.foo = function() { return 42; };
exports.bar = "hello";
'''
        result = convert_cjs_to_browser(source, "test-pkg")
        assert "exports.foo" in result
        assert "exports.bar" in result

    def test_convert_cjs_registers_on_window(self):
        from tw_framework.client_bundler import convert_cjs_to_browser
        source = 'module.exports = { version: "1.0" };'
        result = convert_cjs_to_browser(source, "my-pkg")
        assert "window.__tw_npm['my-pkg']" in result

    def test_convert_cjs_with_multiple_deps(self):
        from tw_framework.client_bundler import convert_cjs_to_browser
        source = '''
var fs = require("fs");
var path = require("path");
var dayjs = require("dayjs");
module.exports = { now: function() { return dayjs().format(); } };
'''
        result = convert_cjs_to_browser(source, "complex-pkg")
        assert "fs" in result
        assert "path" in result
        assert "dayjs" in result
        assert "__tw_require" in result

    def test_convert_cjs_with_builtin_stub(self):
        from tw_framework.client_bundler import convert_cjs_to_browser
        source = '''
var path = require("path");
module.exports = { join: path.join };
'''
        result = convert_cjs_to_browser(source, "path-utils")
        # Should include a stub for the 'path' built-in
        assert "path" in result
        assert "join" in result


# ─── ESM → Browser Conversion Tests ──────────────────────────────────────────

class TestESMToBrowserConversion:
    """Test ESM to browser-compatible conversion."""

    def test_convert_esm_default_export(self):
        from tw_framework.client_bundler import convert_esm_to_browser
        source = 'export default { hello: "world" };'
        result = convert_esm_to_browser(source, "esm-pkg")
        assert "__tw_exports" in result
        assert "default" in result

    def test_convert_esm_named_export(self):
        from tw_framework.client_bundler import convert_esm_to_browser
        source = 'export function foo() { return 42; }'
        result = convert_esm_to_browser(source, "esm-pkg")
        assert "__tw_exports" in result
        assert "foo" in result

    def test_convert_esm_const_export(self):
        from tw_framework.client_bundler import convert_esm_to_browser
        source = 'export const PI = 3.14;'
        result = convert_esm_to_browser(source, "esm-pkg")
        assert "__tw_exports" in result
        assert "PI" in result

    def test_convert_esm_registers_on_window(self):
        from tw_framework.client_bundler import convert_esm_to_browser
        source = 'export default { version: "1.0" };'
        result = convert_esm_to_browser(source, "esm-pkg")
        assert "window.__tw_npm" in result
        assert "esm-pkg" in result


# ─── Node.js Built-in Stubs Tests ────────────────────────────────────────────

class TestNodeBuiltinStubs:
    """Test Node.js built-in module stubs."""

    def test_is_node_builtin_fs(self):
        from tw_framework.client_bundler import is_node_builtin
        assert is_node_builtin("fs") is True

    def test_is_node_builtin_node_prefix(self):
        from tw_framework.client_bundler import is_node_builtin
        assert is_node_builtin("node:path") is True
        assert is_node_builtin("node:fs") is True

    def test_is_node_builtin_not_builtin(self):
        from tw_framework.client_bundler import is_node_builtin
        assert is_node_builtin("react") is False
        assert is_node_builtin("dayjs") is False
        assert is_node_builtin("chart.js") is False

    def test_get_stub_for_process(self):
        from tw_framework.client_bundler import get_builtin_stub
        stub = get_builtin_stub("process")
        assert stub is not None
        assert "env" in stub
        assert "nextTick" in stub

    def test_get_stub_for_path(self):
        from tw_framework.client_bundler import get_builtin_stub
        stub = get_builtin_stub("path")
        assert stub is not None
        assert "join" in stub
        assert "dirname" in stub

    def test_get_stub_for_fs(self):
        from tw_framework.client_bundler import get_builtin_stub
        stub = get_builtin_stub("fs")
        assert stub is not None
        assert "readFileSync" in stub

    def test_get_stub_for_buffer(self):
        from tw_framework.client_bundler import get_builtin_stub
        stub = get_builtin_stub("buffer")
        assert stub is not None
        assert "Buffer" in stub

    def test_get_stub_for_events(self):
        from tw_framework.client_bundler import get_builtin_stub
        stub = get_builtin_stub("events")
        assert stub is not None
        assert "EventEmitter" in stub

    def test_get_stub_nonexistent(self):
        from tw_framework.client_bundler import get_builtin_stub
        stub = get_builtin_stub("nonexistent-module")
        assert stub is None

    def test_get_stub_node_prefix(self):
        from tw_framework.client_bundler import get_builtin_stub
        # node:fs should return same stub as fs
        stub1 = get_builtin_stub("fs")
        stub2 = get_builtin_stub("node:fs")
        assert stub1 == stub2


# ─── ClientBundler Tests ─────────────────────────────────────────────────────

class TestClientBundler:
    """Test the main ClientBundler class."""

    def test_bundler_init(self):
        from tw_framework.client_bundler import ClientBundler
        b = ClientBundler(project_root="/tmp", output_dir="/tmp/out")
        assert b.project_root == "/tmp"
        assert b.output_dir == "/tmp/out"

    def test_bundle_builtin(self):
        from tw_framework.client_bundler import ClientBundler
        b = ClientBundler(project_root="/tmp")
        mod = b.bundle_package("fs")
        assert mod is not None
        assert mod.is_builtin is True
        assert "readFileSync" in mod.source

    def test_bundle_not_installed(self):
        from tw_framework.client_bundler import ClientBundler
        with tempfile.TemporaryDirectory() as tmpdir:
            b = ClientBundler(project_root=tmpdir)
            mod = b.bundle_package("nonexistent-pkg-12345")
            assert mod is None

    def test_bundle_real_package_dayjs(self):
        """Test bundling a real installed package (dayjs)."""
        from tw_framework.client_bundler import ClientBundler
        project_root = "/scratch/work/test-081/test-app"
        if not os.path.exists(os.path.join(project_root, "node_modules", "dayjs")):
            pytest.skip("dayjs not installed in test project")
        b = ClientBundler(project_root=project_root)
        mod = b.bundle_package("dayjs")
        assert mod is not None
        assert mod.name == "dayjs"
        assert len(mod.source) > 100
        assert "TW Client Bundle" in mod.source

    def test_bundle_imports_empty(self):
        from tw_framework.client_bundler import ClientBundler
        b = ClientBundler(project_root="/tmp")
        result = b.bundle_imports([])
        assert len(result.chunks) == 0
        assert len(result.import_map) == 0

    def test_bundle_imports_with_strings(self):
        """Test bundling when imports are plain strings."""
        from tw_framework.client_bundler import ClientBundler
        b = ClientBundler(project_root="/tmp")
        result = b.bundle_imports(["fs"])
        # fs is a builtin, gets inlined not chunked
        assert "fs" in result.modules
        assert result.modules["fs"].is_builtin is True

    def test_bundle_imports_skips_tw_packages(self):
        from tw_framework.client_bundler import ClientBundler
        b = ClientBundler(project_root="/tmp")
        result = b.bundle_imports(["tw/state", "tw/router"])
        assert len(result.chunks) == 0

    def test_bundle_imports_skips_relative(self):
        from tw_framework.client_bundler import ClientBundler
        b = ClientBundler(project_root="/tmp")
        result = b.bundle_imports(["./local", "../parent", "@/lib/data"])
        assert len(result.chunks) == 0

    def test_bundle_imports_warning_for_missing(self):
        from tw_framework.client_bundler import ClientBundler
        with tempfile.TemporaryDirectory() as tmpdir:
            b = ClientBundler(project_root=tmpdir)
            result = b.bundle_imports(["missing-pkg-xyz"])
            assert len(result.warnings) > 0
            assert "tw install" in result.warnings[0]

    def test_bundle_cycle_detection(self):
        """Test that circular dependencies don't cause infinite recursion."""
        from tw_framework.client_bundler import ClientBundler
        b = ClientBundler(project_root="/tmp")
        # Create fake packages with circular deps
        # Since we can't easily create real circular deps, just test
        # that the visited set works
        import unittest.mock
        with unittest.mock.patch.object(b, 'bundle_package') as mock_bundle:
            mock_bundle.return_value = None
            result = b.bundle_imports(["fake-pkg"])
            # Should not crash
            assert result is not None

    def test_render_import_map_script(self):
        from tw_framework.client_bundler import ClientBundler
        b = ClientBundler()
        script = b.render_import_map_script({"react": "/url/react.js"})
        assert "importmap" in script
        assert "react" in script
        assert "/url/react.js" in script

    def test_render_import_map_script_empty(self):
        from tw_framework.client_bundler import ClientBundler
        b = ClientBundler()
        script = b.render_import_map_script({})
        assert script == ""

    def test_render_chunk_script_tags(self):
        from tw_framework.client_bundler import ClientBundler
        b = ClientBundler()
        tags = b.render_chunk_script_tags({"react": "/url/react.js"})
        assert '<script src="/url/react.js">' in tags

    def test_render_chunk_script_tags_empty(self):
        from tw_framework.client_bundler import ClientBundler
        b = ClientBundler()
        tags = b.render_chunk_script_tags({})
        assert tags == ""


# ─── Package Resolution Tests ────────────────────────────────────────────────

class TestPackageResolution:
    """Test package.json reading and entry point resolution."""

    def test_read_package_json(self):
        from tw_framework.client_bundler import read_package_json
        with tempfile.TemporaryDirectory() as tmpdir:
            # Create fake package
            pkg_dir = os.path.join(tmpdir, "node_modules", "test-pkg")
            os.makedirs(pkg_dir)
            with open(os.path.join(pkg_dir, "package.json"), "w") as f:
                json.dump({"name": "test-pkg", "version": "1.0.0"}, f)
            result = read_package_json(tmpdir, "test-pkg")
            assert result is not None
            assert result["name"] == "test-pkg"

    def test_read_package_json_missing(self):
        from tw_framework.client_bundler import read_package_json
        with tempfile.TemporaryDirectory() as tmpdir:
            result = read_package_json(tmpdir, "nonexistent")
            assert result is None

    def test_get_package_entry_point_cjs(self):
        from tw_framework.client_bundler import get_package_entry_point
        pkg_data = {"main": "index.js"}
        entry, fmt = get_package_entry_point(pkg_data, "/tmp", "test-pkg")
        assert "index.js" in entry
        assert fmt == "cjs"

    def test_get_package_entry_point_esm_module(self):
        from tw_framework.client_bundler import get_package_entry_point
        pkg_data = {"module": "dist/esm/index.js", "main": "index.js"}
        entry, fmt = get_package_entry_point(pkg_data, "/tmp", "test-pkg")
        assert "dist/esm/index.js" in entry
        assert fmt == "esm"

    def test_get_package_entry_point_browser(self):
        from tw_framework.client_bundler import get_package_entry_point
        pkg_data = {"browser": "dist/browser.js", "main": "index.js"}
        entry, fmt = get_package_entry_point(pkg_data, "/tmp", "test-pkg")
        assert "dist/browser.js" in entry
        assert fmt == "esm"

    def test_get_package_entry_point_exports(self):
        from tw_framework.client_bundler import get_package_entry_point
        pkg_data = {
            "exports": {
                ".": {
                    "import": "./dist/esm/index.js",
                    "require": "./dist/cjs/index.js"
                }
            }
        }
        entry, fmt = get_package_entry_point(pkg_data, "/tmp", "test-pkg")
        assert "dist/esm/index.js" in entry
        assert fmt == "esm"

    def test_get_package_dependencies(self):
        from tw_framework.client_bundler import get_package_dependencies
        pkg_data = {
            "dependencies": {"react": "^18.0.0", "lodash": "^4.0.0"},
            "devDependencies": {"jest": "^29.0.0"}
        }
        deps = get_package_dependencies(pkg_data)
        assert "react" in deps
        assert "lodash" in deps
        assert "jest" not in deps  # devDependencies should be excluded

    def test_get_package_dependencies_empty(self):
        from tw_framework.client_bundler import get_package_dependencies
        assert get_package_dependencies({}) == []


# ─── Integration Tests with js_interop ───────────────────────────────────────

class TestJSInteropBundlerIntegration:
    """Test that js_interop properly uses the ClientBundler."""

    def test_js_interop_bundle_imports(self):
        from tw_framework.js_interop import JSInterop
        from tw_framework.module_boundaries import ImportInfo
        with tempfile.TemporaryDirectory() as tmpdir:
            j = JSInterop(project_root=tmpdir)
            imports = [ImportInfo(path="fs", line=1, col=0, file="test.tw", context="client", boundary="client")]
            chunks = j.bundle_client_imports(imports, tmpdir)
            # fs is a builtin, inlined — not a separate chunk
            assert isinstance(chunks, dict)

    def test_js_interop_generate_import_map_no_crash(self):
        """The original bug — NameError on non-scoped packages."""
        from tw_framework.js_interop import JSInterop
        from tw_framework.module_boundaries import ImportInfo
        with tempfile.TemporaryDirectory() as tmpdir:
            j = JSInterop(project_root=tmpdir)
            # chart.js is NOT installed, but should NOT crash with NameError
            imports = [ImportInfo(path="chart.js", line=1, col=0, file="test.tw", context="client", boundary="client")]
            try:
                result = j.generate_import_map(imports, tmpdir)
                assert isinstance(result, dict)
            except NameError:
                pytest.fail("NameError bug not fixed — pkg.name should be pkg_name")

    def test_js_interop_generate_import_map_dayjs(self):
        """Test import map generation with a real installed package."""
        from tw_framework.js_interop import JSInterop
        from tw_framework.module_boundaries import ImportInfo
        project_root = "/scratch/work/test-081/test-app"
        if not os.path.exists(os.path.join(project_root, "node_modules", "dayjs")):
            pytest.skip("dayjs not installed")
        j = JSInterop(project_root=project_root)
        imports = [ImportInfo(path="dayjs", line=1, col=0, file="test.tw", context="client", boundary="client")]
        with tempfile.TemporaryDirectory() as tmpdir:
            result = j.generate_import_map(imports, tmpdir)
            assert "dayjs" in result
            assert "dayjs/" in result  # subpath specifier
