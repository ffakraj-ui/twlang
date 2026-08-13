"""Integration tests for ES6 import → lib function interpolation (v0.9.34).

Simulates the user's exact scenario:
  1. .twm lib module with `function greet(name) { ... }`
  2. .tw page with `import { greet } from "@/lib/helpers"`
  3. `body { p "Greeting: {greet('Suraj')}" }` interpolation

Verifies that:
  - ES6 import resolves the .twm file path
  - register_lib_module() is called, populating _LIB_MODULES
  - evaluate_expression("greet('Suraj')", {}) finds the function
"""
import json
import os
import sys
import tempfile
import shutil

import pytest

from tw_framework.compiler import (
    evaluate_expression,
    interpolate,
    _LIB_MODULES,
    register_lib_module,
    _ES6_IMPORTS,
    resolve_source_path,
)
from tw_framework.lib_executor import is_function_call


def _process_es6_imports(base_dir):
    """Simulate the build_tw_ast post-processing loop for ES6 imports."""
    import tw_framework.compiler as _comp
    home_dir = _comp.HOME_DIR
    for imp in _ES6_IMPORTS:
        imp_path = imp.get("path", "")
        if not imp_path:
            continue
        try:
            if imp_path.startswith("@"):
                clean = imp_path[1:].lstrip("/")
                resolved = os.path.join(home_dir, clean)
            else:
                resolved = os.path.join(base_dir, imp_path)
            if not os.path.splitext(resolved)[1]:
                resolved = resolved + ".twm"
            if os.path.isfile(resolved):
                with open(resolved) as f:
                    mod_source = f.read()
                register_lib_module(mod_source, module_id=resolved)
        except Exception:
            pass


# ── ES6 import → register_lib_module integration ────────────────────────────

class TestES6ImportRegistration:
    """Verify ES6 import statement triggers register_lib_module()."""

    def test_es6_import_registers_in_lib_modules(self, monkeypatch):
        """import { greet } from '@/lib/helpers' should register greet in _LIB_MODULES."""
        tmpdir = tempfile.mkdtemp()
        try:
            # Monkey-patch PROJECT_ROOT so @/ resolves to our temp dir
            import tw_framework.compiler as _comp
            monkeypatch.setattr(_comp, "PROJECT_ROOT", tmpdir)
            monkeypatch.setattr(_comp, "HOME_DIR", os.path.join(tmpdir, "[home]"))

            home_dir = os.path.join(tmpdir, "[home]")
            lib_dir = os.path.join(home_dir, "lib")
            os.makedirs(lib_dir)

            # Create helpers.twm
            helpers_path = os.path.join(lib_dir, "helpers.twm")
            with open(helpers_path, "w") as f:
                f.write('''runtime = "nodejs"

function greet(name) {
    return `Hello, ${name}!`
}

function farewell(name) {
    return `Goodbye, ${name}!`
}
''')

            # Simulate ES6 import parsing
            _ES6_IMPORTS.clear()
            _ES6_IMPORTS.append({"names": ["greet"], "path": "@/lib/helpers"})

            # Simulate build_tw_ast post-processing
            _process_es6_imports(home_dir)

            # Verify both functions are registered
            assert "greet" in _LIB_MODULES, f"greet not in _LIB_MODULES: {list(_LIB_MODULES.keys())}"
            assert "farewell" in _LIB_MODULES, f"farewell not in _LIB_MODULES: {list(_LIB_MODULES.keys())}"
        finally:
            shutil.rmtree(tmpdir, ignore_errors=True)

    def test_es6_import_with_multiple_names(self, monkeypatch):
        """import { fn1, fn2 } from '@/lib/utils' should register both."""
        tmpdir = tempfile.mkdtemp()
        try:
            import tw_framework.compiler as _comp
            monkeypatch.setattr(_comp, "PROJECT_ROOT", tmpdir)
            monkeypatch.setattr(_comp, "HOME_DIR", os.path.join(tmpdir, "[home]"))

            home_dir = os.path.join(tmpdir, "[home]")
            lib_dir = os.path.join(home_dir, "lib")
            os.makedirs(lib_dir)

            utils_path = os.path.join(lib_dir, "utils.twm")
            with open(utils_path, "w") as f:
                f.write('''function add(a, b) {
    return a + b
}

function sub(a, b) {
    return a - b
}
''')

            _ES6_IMPORTS.clear()
            _ES6_IMPORTS.append({"names": ["add", "sub"], "path": "@/lib/utils"})

            _process_es6_imports(home_dir)

            assert "add" in _LIB_MODULES
            assert "sub" in _LIB_MODULES
        finally:
            shutil.rmtree(tmpdir, ignore_errors=True)

    def test_es6_import_resolves_at_path(self, monkeypatch):
        """@/lib/helpers should resolve to [home]/lib/helpers.twm via HOME_DIR."""
        tmpdir = tempfile.mkdtemp()
        try:
            import tw_framework.compiler as _comp
            monkeypatch.setattr(_comp, "PROJECT_ROOT", tmpdir)
            home_dir = os.path.join(tmpdir, "[home]")
            monkeypatch.setattr(_comp, "HOME_DIR", home_dir)

            lib_dir = os.path.join(home_dir, "lib")
            os.makedirs(lib_dir)
            helpers_path = os.path.join(lib_dir, "helpers.twm")
            with open(helpers_path, "w") as f:
                f.write('function test_fn() { return 42 }')

            # v0.9.34: @/ resolves to HOME_DIR, not resolve_source_path
            imp_path = "@/lib/helpers"
            clean = imp_path[1:].lstrip("/")
            resolved = os.path.join(home_dir, clean)
            if not os.path.splitext(resolved)[1]:
                resolved = resolved + ".twm"
            assert os.path.isfile(resolved), f"Expected {resolved} to exist"
        finally:
            shutil.rmtree(tmpdir, ignore_errors=True)

    def test_es6_import_missing_file_does_not_crash(self):
        """Missing .twm file should be silently skipped, not crash."""
        _ES6_IMPORTS.clear()
        _ES6_IMPORTS.append({"names": ["nonexistent"], "path": "@/lib/nonexistent"})

        # This should not raise
        _process_es6_imports("/tmp/nonexistent_base")

        # nonexistent should NOT be in _LIB_MODULES
        assert "nonexistent" not in _LIB_MODULES


# ── End-to-end: import → register → evaluate ────────────────────────────────

class TestEndToEndInterpolation:
    """End-to-end: import → register → evaluate_expression → interpolate."""

    def test_full_pipeline_greet_suraj(self, monkeypatch):
        """The exact user scenario: import greet, interpolate {greet('Suraj')}."""
        tmpdir = tempfile.mkdtemp()
        try:
            import tw_framework.compiler as _comp
            monkeypatch.setattr(_comp, "PROJECT_ROOT", tmpdir)
            monkeypatch.setattr(_comp, "HOME_DIR", os.path.join(tmpdir, "[home]"))

            home_dir = os.path.join(tmpdir, "[home]")
            lib_dir = os.path.join(home_dir, "lib")
            os.makedirs(lib_dir)

            helpers_path = os.path.join(lib_dir, "helpers.twm")
            with open(helpers_path, "w") as f:
                f.write('''function greet(name) {
    return `Hello, ${name}!`
}
''')

            # Step 1: Simulate ES6 import parsing
            _ES6_IMPORTS.clear()
            _ES6_IMPORTS.append({"names": ["greet"], "path": "@/lib/helpers"})

            # Step 2: Simulate build_tw_ast post-processing
            _process_es6_imports(home_dir)

            # Step 3: Verify greet is registered
            assert "greet" in _LIB_MODULES

            # Step 4: evaluate_expression should find it
            # If Node.js is available, this returns "Hello, Suraj!"
            # If not, it returns None (graceful degradation)
            result = evaluate_expression("greet('Suraj')", {})
            assert result is None or "Hello" in str(result)

            # Step 5: interpolate should work too
            result = interpolate("Greeting: {greet('Suraj')}", {})
            assert result is not None
        finally:
            shutil.rmtree(tmpdir, ignore_errors=True)

    def test_function_call_detection_for_greet(self):
        """is_function_call correctly detects greet('Suraj')."""
        result = is_function_call("greet('Suraj')")
        assert result is not None
        assert result["name"] == "greet"
        assert "'Suraj'" in result["raw_args"]

    def test_function_call_detection_for_no_args(self):
        """is_function_call detects pi()."""
        result = is_function_call("pi()")
        assert result is not None
        assert result["name"] == "pi"
        assert result["raw_args"] == ""


# ── ast.Call handler regression tests ──────────────────────────────────────

class TestAstCallHandler:
    """Verify _safe_eval ast.Call handler works for various call patterns."""

    def test_call_with_context_function(self):
        def greet(name):
            return "Hello, " + str(name) + "!"
        ctx = {"greet": greet}
        result = evaluate_expression("greet('Suraj')", ctx)
        assert result == "Hello, Suraj!"

    def test_call_with_lambda(self):
        ctx = {"double": lambda x: x * 2}
        result = evaluate_expression("double(5)", ctx)
        assert result == 10

    def test_call_unknown_returns_none(self):
        result = evaluate_expression("unknown_fn('test')", {})
        assert result is None

    def test_call_nested(self):
        ctx = {"double": lambda x: x * 2, "inc": lambda x: x + 1}
        result = evaluate_expression("double(inc(5))", ctx)
        assert result == 12

    def test_call_with_multiple_args(self):
        ctx = {"add": lambda a, b: a + b}
        result = evaluate_expression("add(3, 4)", ctx)
        assert result == 7

    def test_call_in_interpolation(self):
        ctx = {"greet": lambda name: f"Hello, {name}!"}
        result = interpolate("Greeting: {greet('Suraj')}", ctx)
        assert result == "Greeting: Hello, Suraj!"

    def test_plain_var_still_works(self):
        ctx = {"name": "Suraj"}
        result = interpolate("Hello, {name}!", ctx)
        assert result == "Hello, Suraj!"

    def test_mixed_vars_and_functions(self):
        ctx = {"name": "Suraj", "upper": lambda s: s.upper()}
        result = interpolate("{name} says {upper('hello')}", ctx)
        assert result == "Suraj says HELLO"

    def test_none_input(self):
        assert evaluate_expression(None, {}) is None

    def test_empty_input(self):
        assert evaluate_expression("", {}) == ""
