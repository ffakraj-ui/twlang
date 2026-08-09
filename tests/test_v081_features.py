"""
Tests for v0.8.1 features: NPM package manager, React compatibility,
Security module, enhanced lib executor, enhanced js_interop.

Run: pytest tests/test_v081_features.py -v
"""

from __future__ import annotations

import json
import os
import sys
import tempfile

import pytest

sys.path.insert(0, os.path.join(os.path.dirname(__file__), ".."))


# ─── NPM Manager Tests ───────────────────────────────────────────────────────

class TestNpmManager:
    """Test the npm package manager module."""

    def test_parse_package_spec_simple(self):
        from tw_framework.npm_manager import parse_package_spec
        name, version = parse_package_spec("react")
        assert name == "react"
        assert version == ""

    def test_parse_package_spec_with_version(self):
        from tw_framework.npm_manager import parse_package_spec
        name, version = parse_package_spec("react@18.2.0")
        assert name == "react"
        assert version == "18.2.0"

    def test_parse_package_spec_scoped(self):
        from tw_framework.npm_manager import parse_package_spec
        name, version = parse_package_spec("@scope/pkg")
        assert name == "@scope/pkg"
        assert version == ""

    def test_parse_package_spec_scoped_with_version(self):
        from tw_framework.npm_manager import parse_package_spec
        name, version = parse_package_spec("@scope/pkg@1.0.0")
        assert name == "@scope/pkg"
        assert version == "1.0.0"

    def test_read_package_json(self):
        from tw_framework.npm_manager import read_package_json
        with tempfile.TemporaryDirectory() as tmpdir:
            pkg = {"name": "test", "dependencies": {"react": "^18.0.0"}}
            with open(os.path.join(tmpdir, "package.json"), "w") as f:
                json.dump(pkg, f)
            result = read_package_json(tmpdir)
            assert result["name"] == "test"
            assert "react" in result["dependencies"]

    def test_read_package_json_missing(self):
        from tw_framework.npm_manager import read_package_json
        with tempfile.TemporaryDirectory() as tmpdir:
            result = read_package_json(tmpdir)
            assert "dependencies" in result

    def test_write_package_json(self):
        from tw_framework.npm_manager import write_package_json, read_package_json
        with tempfile.TemporaryDirectory() as tmpdir:
            pkg = {"name": "test", "dependencies": {"vue": "^3.0.0"}}
            write_package_json(tmpdir, pkg)
            result = read_package_json(tmpdir)
            assert result["name"] == "test"
            assert "vue" in result["dependencies"]

    def test_update_tw_config_packages_add(self):
        from tw_framework.npm_manager import update_tw_config_packages, get_tw_config_packages
        with tempfile.TemporaryDirectory() as tmpdir:
            config_content = (
                'name: Test\n'
                'server {\n'
                '  external_packages [\n'
                '    "existing-pkg"\n'
                '  ]\n'
                '}\n'
            )
            config_path = os.path.join(tmpdir, "tw.config")
            with open(config_path, "w") as f:
                f.write(config_content)

            update_tw_config_packages(tmpdir, ["react", "react-dom"], remove=False)
            packages = get_tw_config_packages(tmpdir)
            assert "existing-pkg" in packages
            assert "react" in packages
            assert "react-dom" in packages

    def test_update_tw_config_packages_remove(self):
        from tw_framework.npm_manager import update_tw_config_packages, get_tw_config_packages
        with tempfile.TemporaryDirectory() as tmpdir:
            config_content = (
                'name: Test\n'
                'server {\n'
                '  external_packages [\n'
                '    "react", "lodash", "chart.js"\n'
                '  ]\n'
                '}\n'
            )
            config_path = os.path.join(tmpdir, "tw.config")
            with open(config_path, "w") as f:
                f.write(config_content)

            update_tw_config_packages(tmpdir, ["lodash"], remove=True)
            packages = get_tw_config_packages(tmpdir)
            assert "lodash" not in packages
            assert "react" in packages
            assert "chart.js" in packages

    def test_get_tw_config_packages_empty(self):
        from tw_framework.npm_manager import get_tw_config_packages
        with tempfile.TemporaryDirectory() as tmpdir:
            packages = get_tw_config_packages(tmpdir)
            assert packages == []

    def test_verify_node_modules(self):
        from tw_framework.npm_manager import verify_node_modules
        with tempfile.TemporaryDirectory() as tmpdir:
            pkg = {"name": "test", "dependencies": {"react": "^18.0.0"}}
            with open(os.path.join(tmpdir, "package.json"), "w") as f:
                json.dump(pkg, f)

            report = verify_node_modules(tmpdir)
            assert report["total"] == 1
            assert report["missing"] == 1
            assert report["installed"] == 0
            assert report["missing_packages"][0]["name"] == "react"

    def test_verify_node_modules_installed(self):
        from tw_framework.npm_manager import verify_node_modules
        with tempfile.TemporaryDirectory() as tmpdir:
            pkg = {"name": "test", "dependencies": {"react": "^18.0.0"}}
            with open(os.path.join(tmpdir, "package.json"), "w") as f:
                json.dump(pkg, f)

            nm_dir = os.path.join(tmpdir, "node_modules", "react")
            os.makedirs(nm_dir)
            with open(os.path.join(nm_dir, "package.json"), "w") as f:
                json.dump({"name": "react", "version": "18.2.0"}, f)

            report = verify_node_modules(tmpdir)
            assert report["total"] == 1
            assert report["installed"] == 1
            assert report["missing"] == 0

    def test_detect_package_manager(self):
        from tw_framework.npm_manager import detect_package_manager
        with tempfile.TemporaryDirectory() as tmpdir:
            pm = detect_package_manager(tmpdir)
            assert pm in ("npm", "pnpm", "yarn", "bun")

    def test_detect_package_manager_with_lockfile(self):
        from tw_framework.npm_manager import detect_package_manager
        with tempfile.TemporaryDirectory() as tmpdir:
            with open(os.path.join(tmpdir, "pnpm-lock.yaml"), "w") as f:
                f.write("")
            pm = detect_package_manager(tmpdir)
            assert pm == "pnpm"

    def test_list_packages(self):
        from tw_framework.npm_manager import list_packages, write_package_json
        with tempfile.TemporaryDirectory() as tmpdir:
            pkg = {
                "name": "test",
                "dependencies": {"react": "^18.0.0"},
                "devDependencies": {"jest": "^29.0.0"},
            }
            write_package_json(tmpdir, pkg)
            list_packages(tmpdir)


# ─── Lib Executor NPM Resolution Tests ───────────────────────────────────────

class TestLibExecutorNpmResolution:
    """Test npm package resolution in lib_executor."""

    def test_is_npm_package_builtin(self):
        from tw_framework.lib_executor import _is_npm_package
        with tempfile.TemporaryDirectory() as tmpdir:
            assert _is_npm_package("fs", tmpdir) is True
            assert _is_npm_package("path", tmpdir) is True
            assert _is_npm_package("http", tmpdir) is True

    def test_is_npm_package_not_installed(self):
        from tw_framework.lib_executor import _is_npm_package
        with tempfile.TemporaryDirectory() as tmpdir:
            assert _is_npm_package("some-random-pkg", tmpdir) is False

    def test_is_npm_package_installed(self):
        from tw_framework.lib_executor import _is_npm_package
        with tempfile.TemporaryDirectory() as tmpdir:
            nm_dir = os.path.join(tmpdir, "node_modules", "react")
            os.makedirs(nm_dir)
            with open(os.path.join(nm_dir, "package.json"), "w") as f:
                json.dump({"name": "react", "version": "18.0.0"}, f)
            assert _is_npm_package("react", tmpdir) is True

    def test_is_npm_package_rejects_relative(self):
        from tw_framework.lib_executor import _is_npm_package
        with tempfile.TemporaryDirectory() as tmpdir:
            assert _is_npm_package("./local", tmpdir) is False
            assert _is_npm_package("../parent", tmpdir) is False
            assert _is_npm_package("@/lib/data", tmpdir) is False

    def test_resolve_npm_package(self):
        from tw_framework.lib_executor import _resolve_npm_package
        with tempfile.TemporaryDirectory() as tmpdir:
            nm_dir = os.path.join(tmpdir, "node_modules", "react")
            os.makedirs(nm_dir)
            with open(os.path.join(nm_dir, "package.json"), "w") as f:
                json.dump({"name": "react", "version": "18.0.0", "main": "index.js"}, f)
            with open(os.path.join(nm_dir, "index.js"), "w") as f:
                f.write("module.exports = {};")

            result = _resolve_npm_package("react", tmpdir)
            assert result is not None
            assert "react" in result
            assert result.endswith("index.js")

    def test_resolve_npm_package_not_found(self):
        from tw_framework.lib_executor import _resolve_npm_package
        with tempfile.TemporaryDirectory() as tmpdir:
            result = _resolve_npm_package("nonexistent", tmpdir)
            assert result is None

    def test_resolve_module_path_npm(self):
        from tw_framework.lib_executor import resolve_module_path
        with tempfile.TemporaryDirectory() as tmpdir:
            nm_dir = os.path.join(tmpdir, "node_modules", "chart.js")
            dist_dir = os.path.join(nm_dir, "dist")
            os.makedirs(dist_dir)
            with open(os.path.join(nm_dir, "package.json"), "w") as f:
                json.dump({"name": "chart.js", "version": "4.0.0", "main": "dist/chart.js"}, f)
            with open(os.path.join(dist_dir, "chart.js"), "w") as f:
                f.write("// chart.js")

            result = resolve_module_path("chart.js", os.path.join(tmpdir, "page.tw"), tmpdir)
            assert result is not None
            assert "chart.js" in result


# ─── React Compatibility Tests ───────────────────────────────────────────────

class TestReactCompat:
    """Test React compatibility layer."""

    def test_react_compat_import(self):
        from tw_framework.react_compat import ReactCompat
        r = ReactCompat()
        assert r is not None

    def test_is_react_installed_false(self):
        from tw_framework.react_compat import ReactCompat
        with tempfile.TemporaryDirectory() as tmpdir:
            r = ReactCompat(project_root=tmpdir)
            assert r.is_react_installed() is False

    def test_is_react_installed_true(self):
        from tw_framework.react_compat import ReactCompat
        with tempfile.TemporaryDirectory() as tmpdir:
            for pkg in ("react", "react-dom"):
                nm_dir = os.path.join(tmpdir, "node_modules", pkg)
                os.makedirs(nm_dir)
                with open(os.path.join(nm_dir, "package.json"), "w") as f:
                    json.dump({"name": pkg, "version": "18.2.0"}, f)

            r = ReactCompat(project_root=tmpdir)
            assert r.is_react_installed() is True

    def test_get_react_version(self):
        from tw_framework.react_compat import ReactCompat
        with tempfile.TemporaryDirectory() as tmpdir:
            # Need both react and react-dom for is_react_installed to return True
            for pkg_name in ("react", "react-dom"):
                nm_dir = os.path.join(tmpdir, "node_modules", pkg_name)
                os.makedirs(nm_dir)
                with open(os.path.join(nm_dir, "package.json"), "w") as f:
                    json.dump({"name": pkg_name, "version": "18.2.0"}, f)

            r = ReactCompat(project_root=tmpdir)
            assert r.get_react_version() == "18.2.0"

    def test_get_bootstrap_js(self):
        from tw_framework.react_compat import ReactCompat
        r = ReactCompat()
        js = r.get_bootstrap_js()
        assert len(js) > 100
        assert "__tw.react" in js
        assert "register" in js
        assert "mount" in js
        assert "unmount" in js

    def test_detect_react_usage_import(self):
        from tw_framework.react_compat import ReactCompat
        r = ReactCompat()
        assert r.detect_react_usage('import React from "react"') is True
        assert r.detect_react_usage('import { useState } from "react"') is True
        assert r.detect_react_usage("React.createElement") is True

    def test_detect_react_usage_none(self):
        from tw_framework.react_compat import ReactCompat
        r = ReactCompat()
        assert r.detect_react_usage('page { title "Home" }') is False

    def test_get_react_loader_script_cdn(self):
        from tw_framework.react_compat import ReactCompat
        r = ReactCompat()
        script = r.get_react_loader_script(use_cdn=True)
        assert "react" in script.lower()
        assert "script" in script

    def test_get_setup_hint(self):
        from tw_framework.react_compat import ReactCompat
        r = ReactCompat()
        hint = r.get_react_setup_hint()
        assert "tw install" in hint
        assert "react" in hint.lower()


# ─── Security Module Tests ───────────────────────────────────────────────────

class TestSecurityModule:
    """Test the security module."""

    def test_generate_csp_nonce(self):
        from tw_framework.security import generate_csp_nonce
        nonce1 = generate_csp_nonce()
        nonce2 = generate_csp_nonce()
        assert len(nonce1) > 10
        assert nonce1 != nonce2

    def test_build_csp_header(self):
        from tw_framework.security import build_csp_header
        header = build_csp_header()
        assert "default-src" in header
        assert "script-src" in header
        assert "'self'" in header

    def test_build_csp_header_with_nonce(self):
        from tw_framework.security import build_csp_header
        nonce = "test-nonce-123"
        header = build_csp_header(nonce=nonce)
        assert f"nonce-{nonce}" in header

    def test_get_secure_headers(self):
        from tw_framework.security import get_secure_headers
        headers = get_secure_headers(csp_nonce="test-nonce")
        header_names = [h[0] for h in headers]
        assert "Content-Security-Policy" in header_names
        assert "X-Content-Type-Options" in header_names
        assert "X-Frame-Options" in header_names
        assert "Strict-Transport-Security" in header_names
        assert "Referrer-Policy" in header_names
        assert "Permissions-Policy" in header_names

    def test_sanitize_html(self):
        from tw_framework.security import sanitize_html
        # HTML special chars should be escaped to entities
        result = sanitize_html("<script>")
        lt_ent = "&" + "lt;"
        gt_ent = "&" + "gt;"
        assert lt_ent in result
        assert gt_ent in result
        # Test that quotes get escaped
        result = sanitize_html('"hello"')
        qent = "&" + "quot;"
        assert qent in result
        # Ampersand should be escaped
        result = sanitize_html("a & b")
        amp_ent = "&" + "amp;"
        assert amp_ent in result

    def test_sanitize_js_string(self):
        from tw_framework.security import sanitize_js_string
        result = sanitize_js_string('hello "world"')
        assert '\\"' in result
        assert "world" in result

    def test_sanitize_js_string_script_tag(self):
        from tw_framework.security import sanitize_js_string
        result = sanitize_js_string("</script>")
        assert "<\\/script>" in result

    def test_sanitize_url_javascript(self):
        from tw_framework.security import sanitize_url
        assert sanitize_url("javascript:alert(1)") == ""

    def test_sanitize_url_data(self):
        from tw_framework.security import sanitize_url
        assert sanitize_url("data:text/html,<script>") == ""

    def test_sanitize_url_https(self):
        from tw_framework.security import sanitize_url
        assert sanitize_url("https://example.com") == "https://example.com"

    def test_sanitize_url_relative(self):
        from tw_framework.security import sanitize_url
        assert sanitize_url("/api/data") == "/api/data"
        assert sanitize_url("#anchor") == "#anchor"

    def test_sanitize_url_mailto(self):
        from tw_framework.security import sanitize_url
        assert sanitize_url("mailto:test@example.com") == "mailto:test@example.com"

    def test_generate_csrf_token(self):
        from tw_framework.security import generate_csrf_token
        token1 = generate_csrf_token()
        token2 = generate_csrf_token()
        assert len(token1) > 20
        assert token1 != token2

    def test_validate_csrf_token_valid(self):
        from tw_framework.security import generate_csrf_token, validate_csrf_token
        token = generate_csrf_token()
        assert validate_csrf_token(token, token) is True

    def test_validate_csrf_token_invalid(self):
        from tw_framework.security import validate_csrf_token
        assert validate_csrf_token("wrong", "expected") is False
        assert validate_csrf_token("", "expected") is False
        assert validate_csrf_token("token", "") is False

    def test_render_csrf_meta_tag(self):
        from tw_framework.security import render_csrf_meta_tag
        tag = render_csrf_meta_tag("test-token")
        assert "csrf-token" in tag
        assert "test-token" in tag

    def test_safe_join_path(self):
        from tw_framework.security import safe_join_path
        with tempfile.TemporaryDirectory() as tmpdir:
            result = safe_join_path(tmpdir, "subdir/file.txt")
            assert result is not None
            assert result.startswith(tmpdir)

    def test_safe_join_path_traversal(self):
        from tw_framework.security import safe_join_path
        with tempfile.TemporaryDirectory() as tmpdir:
            result = safe_join_path(tmpdir, "../../../etc/passwd")
            assert result is None

    def test_strip_dangerous_html(self):
        from tw_framework.security import strip_dangerous_html
        result = strip_dangerous_html("<script>alert(1)</script>")
        assert "alert(1)" not in result

    def test_strip_dangerous_html_event_handlers(self):
        from tw_framework.security import strip_dangerous_html
        result = strip_dangerous_html('<div onclick="alert(1)">text</div>')
        assert "onclick" not in result

    def test_strip_dangerous_html_javascript_url(self):
        from tw_framework.security import strip_dangerous_html
        result = strip_dangerous_html('<a href="javascript:alert(1)">link</a>')
        assert "javascript:" not in result

    def test_render_secure_headers_html(self):
        from tw_framework.security import render_secure_headers_html
        html = render_secure_headers_html(csp_nonce="test-nonce")
        assert "Content-Security-Policy" in html
        assert "X-Content-Type-Options" in html


# ─── JS Interop Enhancement Tests ────────────────────────────────────────────

class TestJSInteropEnhancements:
    """Test enhanced JS interop features."""

    def test_js_interop_import(self):
        from tw_framework.js_interop import JSInterop, NPMPackage
        j = JSInterop()
        assert j is not None

    def test_generate_import_map_exists(self):
        from tw_framework.js_interop import JSInterop
        j = JSInterop()
        assert hasattr(j, "generate_import_map")

    def test_render_import_map_script_empty(self):
        from tw_framework.js_interop import JSInterop
        j = JSInterop()
        result = j.render_import_map_script({})
        assert result == ""

    def test_render_import_map_script_with_data(self):
        from tw_framework.js_interop import JSInterop
        j = JSInterop()
        result = j.render_import_map_script({"react": "/_tw/chunks/npm/react.abc.js"})
        assert "importmap" in result
        assert "react" in result
        assert "/_tw/chunks/npm/react.abc.js" in result

    def test_resolve_npm_package_known_client(self):
        from tw_framework.js_interop import JSInterop
        j = JSInterop()
        pkg = j.resolve_npm_package("react")
        assert pkg is not None
        assert pkg.name == "react"

    def test_resolve_npm_package_known_server(self):
        from tw_framework.js_interop import JSInterop
        j = JSInterop()
        pkg = j.resolve_npm_package("express")
        assert pkg is not None
        from tw_framework.module_boundaries import SERVER
        assert pkg.boundary == SERVER

    def test_detect_dynamic_imports(self):
        from tw_framework.js_interop import JSInterop
        j = JSInterop()
        result = j.detect_dynamic_imports('const mod = await import("chart.js")')
        assert len(result) == 1
        assert result[0]["path"] == "chart.js"
        assert result[0]["dynamic"] is True

    def test_detect_dynamic_imports_none(self):
        from tw_framework.js_interop import JSInterop
        j = JSInterop()
        result = j.detect_dynamic_imports("var x = 1;")
        assert len(result) == 0


# ─── CLI Command Tests ───────────────────────────────────────────────────────

class TestCLICommands:
    """Test CLI commands exist and are parseable."""

    def test_cli_parser_has_install(self):
        from tw_framework.cli import build_parser
        parser = build_parser()
        args = parser.parse_args(["install", "react"])
        assert args.command == "install"
        assert "react" in args.packages

    def test_cli_parser_has_add(self):
        from tw_framework.cli import build_parser
        parser = build_parser()
        args = parser.parse_args(["add", "lodash"])
        assert args.command == "add"
        assert "lodash" in args.packages

    def test_cli_parser_has_remove(self):
        from tw_framework.cli import build_parser
        parser = build_parser()
        args = parser.parse_args(["remove", "lodash"])
        assert args.command == "remove"
        assert "lodash" in args.packages

    def test_cli_parser_has_list(self):
        from tw_framework.cli import build_parser
        parser = build_parser()
        args = parser.parse_args(["list"])
        assert args.command == "list"

    def test_cli_parser_has_list_alias(self):
        from tw_framework.cli import build_parser
        parser = build_parser()
        args = parser.parse_args(["ls"])
        assert args.command in ("list", "ls")

    def test_cli_parser_install_with_dev(self):
        from tw_framework.cli import build_parser
        parser = build_parser()
        args = parser.parse_args(["install", "jest", "--dev"])
        assert args.dev is True

    def test_cli_parser_install_with_exact(self):
        from tw_framework.cli import build_parser
        parser = build_parser()
        args = parser.parse_args(["install", "react@18.2.0", "--exact"])
        assert args.exact is True

    def test_cli_parser_install_multiple(self):
        from tw_framework.cli import build_parser
        parser = build_parser()
        args = parser.parse_args(["install", "react", "react-dom", "axios"])
        assert len(args.packages) == 3
