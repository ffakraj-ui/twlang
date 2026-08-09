"""
Tests for esbuild integration — detection, bundling, fallback.

Run: pytest tests/test_esbuild_integration.py -v
"""

from __future__ import annotations

import json
import os
import sys
import tempfile

import pytest

sys.path.insert(0, os.path.join(os.path.dirname(__file__), ".."))


# ─── esbuild Detection Tests ─────────────────────────────────────────────────

class TestEsbuildDetection:
    """Test esbuild detection utilities."""

    def test_find_esbuild_returns_string_or_none(self):
        from tw_framework.esbuild_integration import find_esbuild
        result = find_esbuild()
        assert result is None or isinstance(result, str)

    def test_is_esbuild_available_returns_bool(self):
        from tw_framework.esbuild_integration import is_esbuild_available
        result = is_esbuild_available()
        assert isinstance(result, bool)

    def test_get_esbuild_version_returns_str_or_none(self):
        from tw_framework.esbuild_integration import get_esbuild_version
        version = get_esbuild_version()
        assert version is None or isinstance(version, str)

    def test_esbuild_available_in_test_env(self):
        """esbuild should be available via npx in the test sandbox."""
        from tw_framework.esbuild_integration import is_esbuild_available
        # In the sandbox, esbuild is available via npx
        assert is_esbuild_available() is True

    def test_esbuild_version_format(self):
        """If esbuild is available, version should look like a semver."""
        from tw_framework.esbuild_integration import is_esbuild_available, get_esbuild_version
        if is_esbuild_available():
            version = get_esbuild_version()
            assert version is not None
            # Should contain digits and dots (e.g. "0.28.2")
            assert any(c.isdigit() for c in version)


# ─── esbuild Bundling Tests ───────────────────────────────────────────────────

class TestEsbuildBundling:
    """Test esbuild bundling functionality."""

    def test_bundle_with_esbuild_missing_binary(self):
        """If esbuild is not found, should return (False, error)."""
        from tw_framework.esbuild_integration import bundle_with_esbuild
        # Temporarily disable esbuild by monkeypatching
        import tw_framework.esbuild_integration as mod
        original = mod.find_esbuild
        mod.find_esbuild = lambda: None
        try:
            success, msg = bundle_with_esbuild(
                entry_point="/nonexistent.js",
                output_path="/tmp/out.js",
                project_root="/tmp",
            )
            assert success is False
            assert "not found" in msg.lower() or "esbuild" in msg.lower()
        finally:
            mod.find_esbuild = original

    def test_bundle_with_esbuild_nonexistent_entry(self):
        """If entry point doesn't exist, esbuild should fail gracefully."""
        from tw_framework.esbuild_integration import is_esbuild_available, bundle_with_esbuild
        if not is_esbuild_available():
            pytest.skip("esbuild not available")
        with tempfile.TemporaryDirectory() as tmpdir:
            success, msg = bundle_with_esbuild(
                entry_point="/nonexistent/file.js",
                output_path=os.path.join(tmpdir, "out.js"),
                project_root=tmpdir,
            )
            assert success is False

    def test_bundle_real_package_dayjs(self):
        """Test bundling a real installed package (dayjs) with esbuild."""
        from tw_framework.esbuild_integration import is_esbuild_available, bundle_package_with_esbuild
        if not is_esbuild_available():
            pytest.skip("esbuild not available")
        project_root = "/scratch/work/test-081/test-app"
        if not os.path.exists(os.path.join(project_root, "node_modules", "dayjs")):
            pytest.skip("dayjs not installed")
        with tempfile.TemporaryDirectory() as tmpdir:
            chunk_url, message = bundle_package_with_esbuild(
                project_root=project_root,
                pkg_name="dayjs",
                output_dir=tmpdir,
                minify=False,
            )
            assert chunk_url is not None, f"Bundle failed: {message}"
            assert "dayjs" in chunk_url
            # Verify chunk file exists
            chunk_path = os.path.join(tmpdir, chunk_url.lstrip("/"))
            assert os.path.exists(chunk_path)
            # Verify content is browser-compatible JS
            with open(chunk_path, "r") as f:
                content = f.read()
            assert len(content) > 100
            assert "TW Client Bundle" in content

    def test_bundle_package_not_installed(self):
        """Bundling a non-existent package should return None."""
        from tw_framework.esbuild_integration import bundle_package_with_esbuild
        with tempfile.TemporaryDirectory() as tmpdir:
            chunk_url, message = bundle_package_with_esbuild(
                project_root=tmpdir,
                pkg_name="nonexistent-pkg-xyz",
                output_dir=tmpdir,
            )
            assert chunk_url is None
            assert "not found" in message.lower()


# ─── ClientBundler esbuild Integration Tests ────────────────────────────────

class TestClientBundlerEsbuildIntegration:
    """Test that ClientBundler uses esbuild when available."""

    def test_bundler_uses_esbuild_when_available(self):
        """When esbuild is available, bundle_package should use it."""
        from tw_framework.client_bundler import ClientBundler
        project_root = "/scratch/work/test-081/test-app"
        if not os.path.exists(os.path.join(project_root, "node_modules", "dayjs")):
            pytest.skip("dayjs not installed")
        with tempfile.TemporaryDirectory() as tmpdir:
            b = ClientBundler(project_root=project_root, output_dir=tmpdir)
            mod = b.bundle_package("dayjs", use_esbuild=True)
            assert mod is not None
            assert mod.name == "dayjs"
            assert len(mod.source) > 100
            # esbuild output should contain IIFE wrapper
            assert "var" in mod.source or "function" in mod.source

    def test_bundler_fallback_when_esbuild_disabled(self):
        """When use_esbuild=False, should use IIFE wrapper fallback."""
        from tw_framework.client_bundler import ClientBundler
        project_root = "/scratch/work/test-081/test-app"
        if not os.path.exists(os.path.join(project_root, "node_modules", "dayjs")):
            pytest.skip("dayjs not installed")
        with tempfile.TemporaryDirectory() as tmpdir:
            b = ClientBundler(project_root=project_root, output_dir=tmpdir)
            mod = b.bundle_package("dayjs", use_esbuild=False)
            assert mod is not None
            assert mod.name == "dayjs"
            # IIFE wrapper should have these markers
            assert "TW Client Bundle" in mod.source
            assert "module.exports" in mod.source or "exports" in mod.source

    def test_bundler_auto_detects_esbuild(self):
        """When use_esbuild=None, should auto-detect esbuild."""
        from tw_framework.client_bundler import ClientBundler
        from tw_framework.esbuild_integration import is_esbuild_available
        if not is_esbuild_available():
            pytest.skip("esbuild not available")
        project_root = "/scratch/work/test-081/test-app"
        if not os.path.exists(os.path.join(project_root, "node_modules", "dayjs")):
            pytest.skip("dayjs not installed")
        with tempfile.TemporaryDirectory() as tmpdir:
            b = ClientBundler(project_root=project_root, output_dir=tmpdir)
            mod = b.bundle_package("dayjs")  # use_esbuild=None → auto-detect
            assert mod is not None
            assert len(mod.source) > 100

    def test_bundle_imports_with_esbuild(self):
        """Test full import bundling with esbuild integration."""
        from tw_framework.client_bundler import ClientBundler
        from tw_framework.module_boundaries import ImportInfo
        from tw_framework.esbuild_integration import is_esbuild_available
        if not is_esbuild_available():
            pytest.skip("esbuild not available")
        project_root = "/scratch/work/test-081/test-app"
        if not os.path.exists(os.path.join(project_root, "node_modules", "dayjs")):
            pytest.skip("dayjs not installed")
        with tempfile.TemporaryDirectory() as tmpdir:
            b = ClientBundler(project_root=project_root, output_dir=tmpdir)
            imports = [
                ImportInfo(path="dayjs", line=1, col=0, file="test.tw",
                           context="client", boundary="client")
            ]
            result = b.bundle_imports(imports, output_dir=tmpdir)
            assert "dayjs" in result.chunks
            assert "dayjs" in result.import_map
            # Verify chunk file exists
            for name, url in result.chunks.items():
                chunk_path = os.path.join(tmpdir, url.lstrip("/"))
                assert os.path.exists(chunk_path)


# ─── Comparison: esbuild vs IIFE Fallback ───────────────────────────────────

class TestEsbuildVsFallback:
    """Compare esbuild output with IIFE fallback output."""

    def test_esbuild_output_differs_from_fallback(self):
        """esbuild output should be different (better) than IIFE wrapper."""
        from tw_framework.client_bundler import ClientBundler
        from tw_framework.esbuild_integration import is_esbuild_available
        if not is_esbuild_available():
            pytest.skip("esbuild not available")
        project_root = "/scratch/work/test-081/test-app"
        if not os.path.exists(os.path.join(project_root, "node_modules", "dayjs")):
            pytest.skip("dayjs not installed")
        with tempfile.TemporaryDirectory() as tmpdir:
            # Bundle with esbuild
            b1 = ClientBundler(project_root=project_root, output_dir=tmpdir)
            mod_esbuild = b1.bundle_package("dayjs", use_esbuild=True)

            # Bundle with IIFE fallback
            b2 = ClientBundler(project_root=project_root, output_dir=tmpdir)
            mod_fallback = b2.bundle_package("dayjs", use_esbuild=False)

            assert mod_esbuild is not None
            assert mod_fallback is not None
            # Sources should be different
            assert mod_esbuild.source != mod_fallback.source
            # esbuild format should be "esbuild", fallback should be "cjs"
            assert mod_esbuild.format == "esbuild"
            assert mod_fallback.format in ("cjs", "esm")

    def test_esbuild_output_is_valid_js(self):
        """esbuild output should be valid JavaScript."""
        from tw_framework.client_bundler import ClientBundler
        from tw_framework.esbuild_integration import is_esbuild_available
        if not is_esbuild_available():
            pytest.skip("esbuild not available")
        project_root = "/scratch/work/test-081/test-app"
        if not os.path.exists(os.path.join(project_root, "node_modules", "dayjs")):
            pytest.skip("dayjs not installed")
        with tempfile.TemporaryDirectory() as tmpdir:
            b = ClientBundler(project_root=project_root, output_dir=tmpdir)
            mod = b.bundle_package("dayjs", use_esbuild=True)
            assert mod is not None
            # Write to a file and check with node --check
            test_path = os.path.join(tmpdir, "test_bundle.js")
            with open(test_path, "w") as f:
                f.write(mod.source)
            import subprocess
            result = subprocess.run(
                ["node", "--check", test_path],
                capture_output=True, text=True, timeout=15,
            )
            assert result.returncode == 0, f"Invalid JS: {result.stderr}"
