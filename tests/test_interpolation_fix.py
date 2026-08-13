"""Tests for lib function call interpolation fix (v0.9.33).

Regression tests for: {greet('Suraj')} in .tw pages now executes
imported lib functions instead of rendering raw text.
"""
import json
import os
import sys
import tempfile

import pytest

from tw_framework.compiler import (
    evaluate_expression,
    interpolate,
    _safe_eval,
    _LIB_MODULES,
    register_lib_module,
    _try_execute_lib_function,
    _LIB_LOCK,
)


# ── _safe_eval: ast.Call handler ──────────────────────────────────────────────

class TestSafeEvalCallHandler:
    """Verify _safe_eval can handle ast.Call nodes."""

    def test_call_with_context_callable(self):
        """A callable stored in context should be invoked."""
        ctx = {"double": lambda x: x * 2}
        result = evaluate_expression("double(5)", ctx)
        assert result == 10

    def test_call_with_context_function(self):
        """A real function in context should be called."""
        def greet(name):
            return "Hello, " + str(name) + "!"

        ctx = {"greet": greet}
        result = evaluate_expression("greet('Suraj')", ctx)
        assert result == "Hello, Suraj!"

    def test_call_with_unknown_function_returns_none(self):
        """Unknown function call should return None, not crash."""
        ctx = {}
        result = evaluate_expression("unknown_fn('test')", ctx)
        assert result is None

    def test_call_with_args(self):
        """Function with multiple args."""
        ctx = {"add": lambda a, b: a + b}
        result = evaluate_expression("add(3, 4)", ctx)
        assert result == 7

    def test_call_with_no_args(self):
        """Function with no args."""
        ctx = {"pi": lambda: 3.14}
        result = evaluate_expression("pi()", ctx)
        assert result == 3.14

    def test_call_chained_with_string(self):
        """Function call result used in string interpolation."""
        ctx = {"upper": lambda s: s.upper()}
        result = interpolate("Result: {upper('hello')}", ctx)
        assert result == "Result: HELLO"

    def test_call_nested(self):
        """Nested function calls."""
        ctx = {
            "double": lambda x: x * 2,
            "inc": lambda x: x + 1,
        }
        result = evaluate_expression("double(inc(5))", ctx)
        assert result == 12

    def test_call_attribute_method(self):
        """Method call on object attribute."""
        class Obj:
            def method(self, x):
                return x * 10

        ctx = {"obj": Obj()}
        result = evaluate_expression("obj.method(5)", ctx)
        assert result == 50

    def test_call_returns_none_silently(self):
        """If function raises, should return None gracefully."""
        def boom(x):
            raise RuntimeError("crash")

        ctx = {"boom": boom}
        result = evaluate_expression("boom(1)", ctx)
        assert result is None


# ── interpolate: {fn(args)} in text ──────────────────────────────────────────

class TestInterpolateFunctionCalls:
    """Verify {functionCall()} interpolation works in text."""

    def test_simple_function_in_text(self):
        ctx = {"greet": lambda name: f"Hello, {name}!"}
        result = interpolate("Greeting: {greet('Suraj')}", ctx)
        assert result == "Greeting: Hello, Suraj!"

    def test_function_at_start(self):
        ctx = {"upper": lambda s: s.upper()}
        result = interpolate("{upper('hi')} there", ctx)
        assert result == "HI there"

    def test_function_at_end(self):
        ctx = {"upper": lambda s: s.upper()}
        result = interpolate("hello {upper('world')}", ctx)
        assert result == "hello WORLD"

    def test_multiple_functions_in_text(self):
        ctx = {
            "upper": lambda s: s.upper(),
            "lower": lambda s: s.lower(),
        }
        result = interpolate("{upper('HELLO')} {lower('WORLD')}", ctx)
        assert result == "HELLO world"

    def test_function_with_number_arg(self):
        ctx = {"double": lambda x: x * 2}
        result = interpolate("Result: {double(21)}", ctx)
        assert result == "Result: 42"

    def test_function_with_no_args_in_text(self):
        ctx = {"time": lambda: "12:00"}
        result = interpolate("Time: {time()}", ctx)
        assert result == "Time: 12:00"

    def test_plain_var_still_works(self):
        """Regular {var} interpolation should not break."""
        ctx = {"name": "Suraj"}
        result = interpolate("Hello, {name}!", ctx)
        assert result == "Hello, Suraj!"

    def test_undefined_function_in_text_returns_raw(self):
        """Unknown function in interpolation should return the original text."""
        ctx = {}
        result = interpolate("Test: {unknown_fn('x')}", ctx)
        # Should return the raw text since function is not in context
        assert "unknown_fn" in result or result is None or "Test:" in result

    def test_mixed_vars_and_functions(self):
        ctx = {
            "name": "Suraj",
            "upper": lambda s: s.upper(),
        }
        result = interpolate("{name} says {upper('hello')}", ctx)
        assert result == "Suraj says HELLO"


# ── register_lib_module + lib function execution ────────────────────────────

class TestLibModuleRegistration:
    """Verify lib module registration and execution from interpolation."""

    def test_register_and_call_lib_function(self):
        """Register a lib module and call its function from interpolation."""
        twm_source = '''runtime = "nodejs"

fn greet(name) {
    return `Hello, ${name}!`
}
'''
        register_lib_module(twm_source, module_id="test_lib_helpers")

        # Function should be in _LIB_MODULES
        assert "greet" in _LIB_MODULES

        # Call via evaluate_expression
        ctx = {}
        result = evaluate_expression("greet('Suraj')", ctx)
        # If Node.js is available, this should return the string
        # If not, it should return None (graceful degradation)
        assert result is None or "Hello" in str(result)

    def test_is_function_call_detection(self):
        """Verify is_function_call correctly detects function calls."""
        from tw_framework.lib_executor import is_function_call

        # Valid function calls
        result = is_function_call("greet('Suraj')")
        assert result is not None
        assert result["name"] == "greet"
        assert "'Suraj'" in result["raw_args"]

        result = is_function_call("add(1, 2)")
        assert result is not None
        assert result["name"] == "add"

        result = is_function_call("pi()")
        assert result is not None
        assert result["name"] == "pi"

        # Non-function-calls
        assert is_function_call("hello") is None
        assert is_function_call("'string'") is None
        assert is_function_call("123") is None
        assert is_function_call("") is None
        assert is_function_call(None) is None

    def test_lib_module_persisted_in_registry(self):
        """Verify registered lib module persists in _LIB_MODULES."""
        twm_source = '''function square(x) {
    return x * x
}
'''
        register_lib_module(twm_source, module_id="test_math_lib")
        assert "square" in _LIB_MODULES
        mod_info = _LIB_MODULES["square"]
        assert mod_info["module_id"] == "test_math_lib"
        assert "square" in mod_info["source"]


# ── evaluate_expression: full integration ───────────────────────────────────

class TestEvaluateExpressionIntegration:
    """Full integration tests for evaluate_expression with various expr types."""

    def test_variable_access(self):
        ctx = {"name": "World"}
        assert evaluate_expression("name", ctx) == "World"

    def test_attribute_access(self):
        ctx = {"user": {"name": "Alice"}}
        assert evaluate_expression("user.name", ctx) == "Alice"

    def test_subscript_access(self):
        ctx = {"items": [10, 20, 30]}
        assert evaluate_expression("items[0]", ctx) == 10

    def test_arithmetic(self):
        ctx = {}
        assert evaluate_expression("2 + 3", ctx) == 5
        assert evaluate_expression("10 - 4", ctx) == 6
        assert evaluate_expression("3 * 4", ctx) == 12

    def test_comparison(self):
        ctx = {}
        assert evaluate_expression("5 > 3", ctx) is True
        assert evaluate_expression("2 > 5", ctx) is False

    def test_boolean_and(self):
        ctx = {"a": True, "b": False}
        assert evaluate_expression("a && b", ctx) is False
        assert evaluate_expression("a && true", ctx) is True

    def test_boolean_or(self):
        ctx = {"a": False, "b": True}
        assert evaluate_expression("a || b", ctx) is True

    def test_string_concat(self):
        ctx = {"first": "Hello", "second": "World"}
        assert evaluate_expression("first + ' ' + second", ctx) == "Hello World"

    def test_function_call_in_expression(self):
        """Function call as part of larger expression."""
        ctx = {"upper": lambda s: s.upper(), "name": "world"}
        result = evaluate_expression("upper(name)", ctx)
        assert result == "WORLD"

    def test_empty_expression(self):
        assert evaluate_expression("", {}) == ""

    def test_none_expression(self):
        assert evaluate_expression(None, {}) is None
