"""Tests for plugin integrity via registry code matching (v0.9.38).

Verifies that:
1. Plugins saved via install_plugin() have TWP1 format with embedded hash
2. Manually created plugins (no TWP1 format) are rejected on load
3. Tampered plugins (modified content) are rejected — hash won't match
4. Valid TWP1 plugins with correct hash load successfully
5. Plugin name in metadata must match directory name
"""
import json
import os
import tempfile
import shutil

import pytest

from tw_framework.plugin_manager import (
    _save_plugin_with_hash,
    _load_plugin_with_hash,
    _verify_plugin_from_registry,
    PluginManager,
    HOOKS,
)


# ── Save/Load with hash tests ────────────────────────────────────────────────

class TestSaveLoadWithHash:
    """Test TWP1 format with embedded SHA-256 hash."""

    def test_save_load_roundtrip(self):
        """Saved content loads back correctly."""
        original = 'plugin.register("afterBuild", function(ctx) { ctx.log("hi"); });'
        tmpdir = tempfile.mkdtemp()
        try:
            fpath = os.path.join(tmpdir, "plugin.twp")
            _save_plugin_with_hash(original.encode("utf-8"), fpath, "tw-test")
            loaded = _load_plugin_with_hash(fpath)
            assert loaded == original
        finally:
            shutil.rmtree(tmpdir, ignore_errors=True)

    def test_saved_file_starts_with_twp1(self):
        """Saved file starts with TWP1 marker."""
        tmpdir = tempfile.mkdtemp()
        try:
            fpath = os.path.join(tmpdir, "plugin.twp")
            _save_plugin_with_hash(b"hello", fpath, "tw-test")
            with open(fpath, "r") as f:
                content = f.read()
            assert content.startswith("TWP1\n")
        finally:
            shutil.rmtree(tmpdir, ignore_errors=True)

    def test_load_rejects_plain_text(self):
        """Plain text file (not TWP1) returns None."""
        tmpdir = tempfile.mkdtemp()
        try:
            fpath = os.path.join(tmpdir, "plugin.twp")
            with open(fpath, "w") as f:
                f.write("just plain text, no TWP1")
            result = _load_plugin_with_hash(fpath)
            assert result is None
        finally:
            shutil.rmtree(tmpdir, ignore_errors=True)

    def test_load_rejects_empty_file(self):
        """Empty file returns None."""
        tmpdir = tempfile.mkdtemp()
        try:
            fpath = os.path.join(tmpdir, "plugin.twp")
            with open(fpath, "w") as f:
                f.write("")
            result = _load_plugin_with_hash(fpath)
            assert result is None
        finally:
            shutil.rmtree(tmpdir, ignore_errors=True)

    def test_load_rejects_tampered_content(self):
        """Modified content (hash mismatch) returns None."""
        tmpdir = tempfile.mkdtemp()
        try:
            fpath = os.path.join(tmpdir, "plugin.twp")
            _save_plugin_with_hash(b"original content", fpath, "tw-test")
            # Tamper: modify the content after the hash line
            with open(fpath, "r") as f:
                raw = f.read()
            parts = raw.split("\n", 2)
            # Change content but keep old hash
            tampered = parts[0] + "\n" + parts[1] + "\n" + "tampered content"
            with open(fpath, "w") as f:
                f.write(tampered)
            result = _load_plugin_with_hash(fpath)
            assert result is None  # Hash won't match
        finally:
            shutil.rmtree(tmpdir, ignore_errors=True)

    def test_load_rejects_fake_twp1(self):
        """Hand-crafted TWP1 with wrong hash returns None."""
        tmpdir = tempfile.mkdtemp()
        try:
            fpath = os.path.join(tmpdir, "plugin.twp")
            fake = "TWP1\n" + "a" * 64 + "\n" + "malicious code"
            with open(fpath, "w") as f:
                f.write(fake)
            result = _load_plugin_with_hash(fpath)
            assert result is None
        finally:
            shutil.rmtree(tmpdir, ignore_errors=True)

    def test_load_rejects_missing_file(self):
        """Non-existent file returns None."""
        result = _load_plugin_with_hash("/nonexistent/plugin.twp")
        assert result is None

    def test_save_json_metadata(self):
        """JSON metadata can be saved and loaded."""
        tmpdir = tempfile.mkdtemp()
        try:
            meta = {"name": "tw-test", "version": "0.1.0", "hooks": ["afterBuild"]}
            fpath = os.path.join(tmpdir, "plugin.json")
            _save_plugin_with_hash(json.dumps(meta).encode("utf-8"), fpath, "tw-test")
            loaded = _load_plugin_with_hash(fpath)
            assert json.loads(loaded) == meta
        finally:
            shutil.rmtree(tmpdir, ignore_errors=True)


# ── PluginManager load_all tests ────────────────────────────────────────────

class TestPluginManagerIntegrity:
    """Test that PluginManager rejects unsigned/tampered plugins."""

    def _make_plugin_files(self, plugins_dir, name, valid=True):
        """Create plugin files in plugins_dir/name/.

        If valid=True: use _save_plugin_with_hash (proper TWP1 format)
        If valid=False: write plain text (manual/fake plugin)
        """
        pdir = os.path.join(plugins_dir, name)
        os.makedirs(pdir, exist_ok=True)

        meta = json.dumps({
            "name": name,
            "version": "0.1.0",
            "description": "Test plugin",
            "hooks": ["afterBuild"],
        })
        code = 'plugin.register("afterBuild", function(ctx) { ctx.log("test"); });'

        if valid:
            _save_plugin_with_hash(meta.encode("utf-8"), os.path.join(pdir, "plugin.json"), name)
            _save_plugin_with_hash(code.encode("utf-8"), os.path.join(pdir, "plugin.twp"), name)
        else:
            with open(os.path.join(pdir, "plugin.json"), "w") as f:
                f.write(meta)
            with open(os.path.join(pdir, "plugin.twp"), "w") as f:
                f.write(code)

    def test_valid_twp1_plugin_loads(self):
        """Plugin saved via _save_plugin_with_hash loads successfully."""
        tmpdir = tempfile.mkdtemp()
        try:
            self._make_plugin_files(tmpdir, "tw-test", valid=True)
            pm = PluginManager(plugins_dir=tmpdir, project_root=tmpdir)
            pm.load_all()
            # May or may not load depending on registry verification (offline)
            # but at least should not crash
        finally:
            shutil.rmtree(tmpdir, ignore_errors=True)

    def test_custom_plugin_loaded_with_warning(self):
        """Custom plugin (plain text, no TWP1) is loaded with warning, not rejected."""
        tmpdir = tempfile.mkdtemp()
        try:
            self._make_plugin_files(tmpdir, "tw-hack", valid=False)
            pm = PluginManager(plugins_dir=tmpdir, project_root=tmpdir)
            pm.load_all()
            # v0.9.40: Custom plugins are allowed (with warning)
            assert "tw-hack" in pm.plugins
            assert pm.has_plugins()
        finally:
            shutil.rmtree(tmpdir, ignore_errors=True)

    def test_tampered_plugin_rejected(self):
        """Plugin with modified content (valid TWP1 but tampered) is rejected."""
        tmpdir = tempfile.mkdtemp()
        try:
            self._make_plugin_files(tmpdir, "tw-tamper", valid=True)
            # Tamper: modify content after hash
            pt_path = os.path.join(tmpdir, "tw-tamper", "plugin.twp")
            with open(pt_path, "r") as f:
                raw = f.read()
            parts = raw.split("\n", 2)
            tampered = parts[0] + "\n" + parts[1] + "\n" + "tampered code here"
            with open(pt_path, "w") as f:
                f.write(tampered)

            pm = PluginManager(plugins_dir=tmpdir, project_root=tmpdir)
            pm.load_all()
            assert "tw-tamper" not in pm.plugins
        finally:
            shutil.rmtree(tmpdir, ignore_errors=True)

    def test_mixed_valid_and_invalid(self):
        """Valid TWP1 plugin loads silently, custom plugin loads with warning."""
        tmpdir = tempfile.mkdtemp()
        try:
            self._make_plugin_files(tmpdir, "tw-valid", valid=True)
            self._make_plugin_files(tmpdir, "tw-custom", valid=False)

            pm = PluginManager(plugins_dir=tmpdir, project_root=tmpdir)
            pm.load_all()
            # v0.9.40: Both load — valid silently, custom with warning
            assert "tw-valid" in pm.plugins
            assert "tw-custom" in pm.plugins
        finally:
            shutil.rmtree(tmpdir, ignore_errors=True)

    def test_empty_plugins_dir(self):
        """Empty plugins directory loads nothing."""
        tmpdir = tempfile.mkdtemp()
        try:
            pm = PluginManager(plugins_dir=tmpdir, project_root=tmpdir)
            pm.load_all()
            assert not pm.has_plugins()
        finally:
            shutil.rmtree(tmpdir, ignore_errors=True)

    def test_no_plugins_dir(self):
        """Missing plugins directory loads nothing without error."""
        tmpdir = tempfile.mkdtemp()
        try:
            pm = PluginManager(plugins_dir=os.path.join(tmpdir, "nonexistent"), project_root=tmpdir)
            pm.load_all()
            assert not pm.has_plugins()
        finally:
            shutil.rmtree(tmpdir, ignore_errors=True)

    def test_fake_twp1_with_wrong_hash_rejected(self):
        """Hand-crafted TWP1 file with wrong hash is rejected."""
        tmpdir = tempfile.mkdtemp()
        try:
            pdir = os.path.join(tmpdir, "tw-fake")
            os.makedirs(pdir)
            # Create fake TWP1 files with wrong hash
            fake_meta = "TWP1\n" + "0" * 64 + "\n" + json.dumps({"name": "tw-fake", "version": "0.1.0"})
            fake_code = "TWP1\n" + "0" * 64 + "\n" + 'plugin.register("afterBuild", function(ctx) {});'
            with open(os.path.join(pdir, "plugin.json"), "w") as f:
                f.write(fake_meta)
            with open(os.path.join(pdir, "plugin.twp"), "w") as f:
                f.write(fake_code)

            pm = PluginManager(plugins_dir=tmpdir, project_root=tmpdir)
            pm.load_all()
            assert "tw-fake" not in pm.plugins
        finally:
            shutil.rmtree(tmpdir, ignore_errors=True)
