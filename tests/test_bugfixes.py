"""
Tests for v0.8.1 bug fixes:
  1. module_boundaries.py — fetch() misclassification
  2. client_bundler.py — transitive deps not written to disk
  3. esbuild fail/missing — no warning
  4. render_chunk_script_tags — alphabetical instead of dependency order

Run: pytest tests/test_bugfixes.py -v
"""

from __future__ import annotations

import json
import os
import sys
import tempfile

import pytest

sys.path.insert(0, os.path.join(os.path.dirname(__file__), ".."))


# ─── Fix #1: module_boundaries.py — fetch() classification ───────────────────

class TestFetchClassificationFix:
    """Test that fetch() is no longer treated as client-only."""

    def test_fetch_not_in_client_patterns(self):
        """fetch() should NOT be in CLIENT_API_PATTERNS."""
        from tw_framework.module_boundaries import CLIENT_API_PATTERNS
        for pattern in CLIENT_API_PATTERNS:
            # None of the patterns should match only fetch(
            assert "fetch" not in pattern.pattern, \
                f"fetch() should not be in CLIENT_API_PATTERNS: {pattern.pattern}"

    def test_classify_server_source_with_fetch(self):
        """A server module using fetch() should be SERVER, not SHARED/CLIENT."""
        from tw_framework.module_boundaries import ImportClassifier, SERVER
        classifier = ImportClassifier()
        source = '''
export async function getData() {
    const response = await fetch("https://api.example.com/data");
    return response.json();
}
'''
        result = classifier.classify_module_source(source)
        assert result != "client", "fetch() should not classify as CLIENT"
        # With no server patterns either, it'll be SHARED — but NOT client
        # That's the fix: it's no longer wrongly classified as CLIENT

    def test_classify_twm_file_with_fetch(self):
        """A .twm file using fetch() should be SERVER (.twm = server)."""
        from tw_framework.module_boundaries import ImportClassifier, SERVER
        classifier = ImportClassifier()
        source = '''
export async function proxyRequest(url) {
    const res = await fetch(url);
    return res.json();
}
'''
        result = classifier.classify_module_source(source, file_path="api/proxy/route.twm")
        assert result == SERVER, ".twm files should always be SERVER"

    def test_classify_real_dom_still_client(self):
        """Genuine DOM APIs (document, window) should still be CLIENT."""
        from tw_framework.module_boundaries import ImportClassifier, CLIENT
        classifier = ImportClassifier()
        source = '''
export function setupUI() {
    document.getElementById("app");
    window.addEventListener("resize", function() {});
}
'''
        result = classifier.classify_module_source(source)
        assert result == CLIENT, "document/window should still be CLIENT"

    def test_classify_twm_file_always_server(self):
        """Even if a .twm file mentions 'window' in a string, it should be SERVER."""
        from tw_framework.module_boundaries import ImportClassifier, SERVER
        classifier = ImportClassifier()
        source = '''
export function getWindowName() {
    return "window";  // just a string, not DOM usage
}
'''
        result = classifier.classify_module_source(source, file_path="lib/utils.twm")
        assert result == SERVER, ".twm files should always be SERVER"

    def test_classify_non_twm_with_fetch(self):
        """Non-.twm file with fetch() should NOT be CLIENT."""
        from tw_framework.module_boundaries import ImportClassifier, CLIENT
        classifier = ImportClassifier()
        source = '''
async function loadData() {
    const res = await fetch("/api/data");
    return res.json();
}
'''
        result = classifier.classify_module_source(source, file_path="lib/helper.js")
        assert result != CLIENT, "fetch() should not make a .js file CLIENT"


# ─── Fix #2: Transitive deps written to disk ────────────────────────────────

class TestTransitiveDepsFix:
    """Test that transitive dependencies are written to disk and in import map."""

    def test_transitive_deps_in_chunks(self):
        """When package A depends on B, B should appear in chunks (IIFE fallback)."""
        from tw_framework.client_bundler import ClientBundler, BundledModule
        import tw_framework.client_bundler as mod

        # Force IIFE fallback — Fix #2 is about the fallback bundler
        original_esbuild = mod._esbuild_available
        mod._esbuild_available = lambda: False
        try:
            # Create fake packages: A depends on B
            with tempfile.TemporaryDirectory() as tmpdir:
                for pkg_name, pkg_source in [
                    ("pkg-b", 'module.exports = { hello: "world" };'),
                    ("pkg-a", 'var b = require("pkg-b"); module.exports = { b: b };'),
                ]:
                    pkg_dir = os.path.join(tmpdir, "node_modules", pkg_name)
                    os.makedirs(pkg_dir)
                    with open(os.path.join(pkg_dir, "package.json"), "w") as f:
                        json.dump({
                            "name": pkg_name,
                            "version": "1.0.0",
                            "main": "index.js",
                            "dependencies": {"pkg-b": "^1.0.0"} if pkg_name == "pkg-a" else {},
                        }, f)
                    with open(os.path.join(pkg_dir, "index.js"), "w") as f:
                        f.write(pkg_source)

                out_dir = os.path.join(tmpdir, "dist")
                os.makedirs(out_dir)
                b = ClientBundler(project_root=tmpdir, output_dir=out_dir)
                result = b.bundle_imports(["pkg-a"], output_dir=out_dir)

                # pkg-a should be chunked
                assert "pkg-a" in result.chunks, "pkg-a should be in chunks"
                # pkg-b should ALSO be chunked (Fix #2)
                assert "pkg-b" in result.chunks, \
                    "pkg-b (transitive dep) should also be in chunks — this was the bug!"
                # pkg-b should be in import map
                assert "pkg-b" in result.import_map, \
                    "pkg-b should be in import_map — this was the bug!"
                # Verify chunk files exist on disk
                for name in ["pkg-a", "pkg-b"]:
                    url = result.chunks[name]
                    chunk_path = os.path.join(out_dir, url.lstrip("/"))
                    assert os.path.exists(chunk_path), \
                        f"Chunk file for {name} should exist on disk — this was the bug!"
        finally:
            mod._esbuild_available = original_esbuild

    def test_no_silent_missing_deps(self):
        """Ensure no transitive dependency is silently missing (IIFE fallback)."""
        from tw_framework.client_bundler import ClientBundler
        import tw_framework.client_bundler as mod

        # Force IIFE fallback
        original_esbuild = mod._esbuild_available
        mod._esbuild_available = lambda: False
        try:
            with tempfile.TemporaryDirectory() as tmpdir:
                for pkg_name, deps in [("dep-x", {}), ("main-x", {"dep-x": "^1.0.0"})]:
                    pkg_dir = os.path.join(tmpdir, "node_modules", pkg_name)
                    os.makedirs(pkg_dir)
                    with open(os.path.join(pkg_dir, "package.json"), "w") as f:
                        json.dump({"name": pkg_name, "version": "1.0.0", "main": "index.js", "dependencies": deps}, f)
                    with open(os.path.join(pkg_dir, "index.js"), "w") as f:
                        f.write('module.exports = {};\n')

                out_dir = os.path.join(tmpdir, "dist")
                os.makedirs(out_dir)
                b = ClientBundler(project_root=tmpdir, output_dir=out_dir)
                result = b.bundle_imports(["main-x"], output_dir=out_dir)

                # Both should be in chunks
                assert "main-x" in result.chunks
                assert "dep-x" in result.chunks, \
                    "dep-x must be chunked — silent missing deps was the bug"
        finally:
            mod._esbuild_available = original_esbuild


# ─── Fix #3: esbuild fallback warning ───────────────────────────────────────

class TestEsbuildFallbackWarning:
    """Test that esbuild fallback generates a warning."""

    def test_warning_when_esbuild_disabled(self):
        """When esbuild is not available, a warning should be generated."""
        from tw_framework.client_bundler import ClientBundler
        import tw_framework.client_bundler as mod

        # Force esbuild to be "not available"
        original = mod._esbuild_available
        mod._esbuild_available = lambda: False
        try:
            with tempfile.TemporaryDirectory() as tmpdir:
                b = ClientBundler(project_root=tmpdir, output_dir=tmpdir)
                result = b.bundle_imports([], output_dir=tmpdir)
                # Should have a warning about esbuild not being installed
                esbuild_warnings = [w for w in result.warnings if "esbuild" in w.lower()]
                assert len(esbuild_warnings) > 0, \
                    "Should warn when esbuild is not available — this was the bug!"
        finally:
            mod._esbuild_available = original

    def test_no_esbuild_warning_when_available(self):
        """When esbuild IS available, no fallback warning should appear."""
        from tw_framework.client_bundler import ClientBundler
        import tw_framework.client_bundler as mod

        original = mod._esbuild_available
        mod._esbuild_available = lambda: True
        try:
            with tempfile.TemporaryDirectory() as tmpdir:
                b = ClientBundler(project_root=tmpdir, output_dir=tmpdir)
                result = b.bundle_imports([], output_dir=tmpdir)
                esbuild_warnings = [w for w in result.warnings if "esbuild" in w.lower()]
                # Should NOT have the "not installed" warning
                not_installed = [w for w in esbuild_warnings if "not installed" in w.lower()]
                assert len(not_installed) == 0, \
                    "Should not warn 'not installed' when esbuild IS available"
        finally:
            mod._esbuild_available = original


# ─── Fix #4: Script tag ordering — topological sort ─────────────────────────

class TestScriptTagOrdering:
    """Test that script tags are ordered by dependencies, not alphabetically."""

    def test_deps_before_dependents(self):
        """If A depends on B, B's script tag should come before A's."""
        from tw_framework.client_bundler import ClientBundler, BundledModule

        b = ClientBundler(project_root="/tmp", output_dir="/tmp")

        # Simulate: pkg-a depends on pkg-z
        # Alphabetically: pkg-a < pkg-z
        # But dependency order: pkg-z should come FIRST (it's a dep of pkg-a)
        b._cache["pkg-a"] = BundledModule(
            name="pkg-a", source="// a", format="cjs",
            dependencies=["pkg-z"],
        )
        b._cache["pkg-z"] = BundledModule(
            name="pkg-z", source="// z", format="cjs",
            dependencies=[],
        )

        chunks = {"pkg-a": "/a.js", "pkg-z": "/z.js"}
        html = b.render_chunk_script_tags(chunks)

        # pkg-z should appear BEFORE pkg-a in the HTML
        pos_z = html.index("/z.js")
        pos_a = html.index("/a.js")
        assert pos_z < pos_a, \
            f"pkg-z (dependency) should come BEFORE pkg-a. " \
            f"Got z@{pos_z}, a@{pos_a} — alphabetical sort was the bug!"

    def test_no_deps_alphabetical(self):
        """With no dependencies, packages should still be in a stable order."""
        from tw_framework.client_bundler import ClientBundler, BundledModule

        b = ClientBundler(project_root="/tmp", output_dir="/tmp")
        b._cache["pkg-a"] = BundledModule(name="pkg-a", source="// a", dependencies=[])
        b._cache["pkg-b"] = BundledModule(name="pkg-b", source="// b", dependencies=[])

        chunks = {"pkg-a": "/a.js", "pkg-b": "/b.js"}
        html = b.render_chunk_script_tags(chunks)
        # Both should appear
        assert "/a.js" in html
        assert "/b.js" in html

    def test_chain_ordering(self):
        """Test a dependency chain: C → B → A (C depends on B, B depends on A)."""
        from tw_framework.client_bundler import ClientBundler, BundledModule

        b = ClientBundler(project_root="/tmp", output_dir="/tmp")
        # C depends on B, B depends on A
        # Order should be: A, B, C
        b._cache["pkg-c"] = BundledModule(name="pkg-c", source="// c", dependencies=["pkg-b"])
        b._cache["pkg-b"] = BundledModule(name="pkg-b", source="// b", dependencies=["pkg-a"])
        b._cache["pkg-a"] = BundledModule(name="pkg-a", source="// a", dependencies=[])

        chunks = {"pkg-a": "/a.js", "pkg-b": "/b.js", "pkg-c": "/c.js"}
        html = b.render_chunk_script_tags(chunks)

        pos_a = html.index("/a.js")
        pos_b = html.index("/b.js")
        pos_c = html.index("/c.js")
        assert pos_a < pos_b < pos_c, \
            f"Order should be A→B→C. Got a@{pos_a}, b@{pos_b}, c@{pos_c}"

    def test_cycle_fallback(self):
        """If there's a dependency cycle, should not crash."""
        from tw_framework.client_bundler import ClientBundler, BundledModule

        b = ClientBundler(project_root="/tmp", output_dir="/tmp")
        # A depends on B, B depends on A — cycle!
        b._cache["pkg-a"] = BundledModule(name="pkg-a", source="// a", dependencies=["pkg-b"])
        b._cache["pkg-b"] = BundledModule(name="pkg-b", source="// b", dependencies=["pkg-a"])

        chunks = {"pkg-a": "/a.js", "pkg-b": "/b.js"}
        # Should not crash
        html = b.render_chunk_script_tags(chunks)
        assert "/a.js" in html
        assert "/b.js" in html

    def test_empty_chunks(self):
        """Empty chunks should return empty string."""
        from tw_framework.client_bundler import ClientBundler
        b = ClientBundler()
        assert b.render_chunk_script_tags({}) == ""

    def test_comment_says_dependency_not_alphabetical(self):
        """The docstring should mention topological/dependency order."""
        from tw_framework.client_bundler import ClientBundler
        import inspect
        doc = inspect.getdoc(ClientBundler.render_chunk_script_tags)
        assert doc is not None
        assert "dependency" in doc.lower() or "topological" in doc.lower(), \
            "Docstring should mention dependency/topological ordering"
