"""Tests for the lib/ system — build-time .twm function execution."""
from __future__ import annotations
import os, sys
import pytest

sys.path.insert(0, os.path.join(os.path.dirname(__file__), ".."))
from tw_framework import compiler
from tw_framework.lib_executor import is_function_call, execute_lib_function, LibExecutionError


class TestIsFunctionCall:
    def test_simple_call(self):
        assert is_function_call('getApps("whatsapp")') == {"name": "getApps", "raw_args": '"whatsapp"'}
    def test_multi_args(self):
        assert is_function_call("calc(5, 10)") == {"name": "calc", "raw_args": "5, 10"}
    def test_no_args(self):
        assert is_function_call("noArgs()") == {"name": "noArgs", "raw_args": ""}
    def test_string_literal(self):
        assert is_function_call('"hello"') is None
    def test_number(self):
        assert is_function_call("42") is None
    def test_boolean(self):
        assert is_function_call("true") is None
    def test_array(self):
        assert is_function_call("[1, 2]") is None
    def test_none(self):
        assert is_function_call(None) is None
    def test_empty(self):
        assert is_function_call("") is None


class TestExecuteLibFunction:
    def test_object_return(self):
        src = 'fn greet(name) {\n  return { message: "Hello, " + name + "!", name: name }\n}\n'
        result = execute_lib_function(src, "greet", '"TestUser"', module_id="test")
        assert result["message"] == "Hello, TestUser!"
    def test_array_return(self):
        src = 'fn getApps() {\n  return [{name: "WhatsApp"}, {name: "Telegram"}]\n}\n'
        result = execute_lib_function(src, "getApps", "", module_id="test")
        assert len(result) == 2
        assert result[0]["name"] == "WhatsApp"
    def test_number_return(self):
        src = 'fn calc(a, b) {\n  return a + b\n}\n'
        result = execute_lib_function(src, "calc", "5, 10", module_id="test")
        assert result == 15
    def test_string_return(self):
        src = 'fn upper(name) {\n  return name.toUpperCase()\n}\n'
        result = execute_lib_function(src, "upper", '"whatsapp"', module_id="test")
        assert result == "WHATSAPP"
    def test_function_not_found(self):
        src = 'fn foo() {\n  return 42\n}\n'
        with pytest.raises(LibExecutionError, match="not found"):
            execute_lib_function(src, "bar", "", module_id="test")
    def test_no_args(self):
        src = 'fn getVersion() {\n  return "2.0.0"\n}\n'
        result = execute_lib_function(src, "getVersion", "", module_id="test")
        assert result == "2.0.0"


class TestFullFileIntegration:
    @pytest.fixture
    def setup_project(self, tmp_path):
        home_dir = tmp_path / "[home]"
        lib_dir = home_dir / "lib"
        pages_dir = home_dir / "pages"
        lib_dir.mkdir(parents=True, exist_ok=True)
        pages_dir.mkdir(parents=True, exist_ok=True)
        old_home = compiler.HOME_DIR
        compiler.HOME_DIR = str(home_dir)
        (lib_dir / "getApps.twm").write_text(
            'fn getApp(slug) {\n'
            '  return { name: "WhatsApp", slug: slug, version: "2.23.10", size: "45MB" }\n'
            '}\n'
        )
        (lib_dir / "utils.twm").write_text(
            'fn getName(slug) {\n  return "WhatsApp"\n}\n'
            'fn getVersion(slug) {\n  return "2.23.10"\n}\n'
        )
        yield home_dir
        compiler.HOME_DIR = old_home

    def test_full_build_with_lib(self, setup_project, tmp_path):
        tw_src = '''page {
    title "Download"
    render static
}

load @./lib/getApps.twm

let slug = "whatsapp"
let app = getApp("whatsapp")

body {
    h1 "{app.name}"
    p "Version: {app.version}"
    p "Size: {app.size}"
}
'''
        tw_file = setup_project / "pages" / "download.tw"
        tw_file.write_text(tw_src)
        compiler._LIB_MODULES.clear()
        tokens = compiler.tokenize_tw(tw_src)
        page = compiler.build_tw_ast(tokens, str(setup_project), str(tw_file), tw_src)
        assert page.let_vars["app"]["name"] == "WhatsApp"
        assert page.let_vars["app"]["version"] == "2.23.10"
        assert page.let_vars["slug"] == "whatsapp"

    def test_type_safety_with_lib(self, setup_project, tmp_path):
        tw_src = '''page {
    title "Typed"
    render static
}

load @./lib/getApps.twm

let app: object = getApp("whatsapp")

body {
    h1 "{app.name}"
}
'''
        tw_file = setup_project / "pages" / "typed.tw"
        tw_file.write_text(tw_src)
        compiler._LIB_MODULES.clear()
        tokens = compiler.tokenize_tw(tw_src)
        page = compiler.build_tw_ast(tokens, str(setup_project), str(tw_file), tw_src)
        assert page.let_vars["app"]["name"] == "WhatsApp"

    def test_type_mismatch_with_lib(self, setup_project, tmp_path):
        tw_src = '''page {
    title "Bad"
    render static
}

load @./lib/getApps.twm

let app: string = getApp("whatsapp")

body {
    h1 "{app}"
}
'''
        tw_file = setup_project / "pages" / "bad.tw"
        tw_file.write_text(tw_src)
        compiler._LIB_MODULES.clear()
        with pytest.raises(compiler.CompilerError, match="Type error"):
            tokens = compiler.tokenize_tw(tw_src)
            compiler.build_tw_ast(tokens, str(setup_project), str(tw_file), tw_src)

    def test_multiple_lib_functions(self, setup_project, tmp_path):
        tw_src = '''page {
    title "Multi"
    render static
}

load @./lib/utils.twm

let name = getName("whatsapp")
let version = getVersion("whatsapp")

body {
    h1 "{name} {version}"
}
'''
        tw_file = setup_project / "pages" / "multi.tw"
        tw_file.write_text(tw_src)
        compiler._LIB_MODULES.clear()
        tokens = compiler.tokenize_tw(tw_src)
        page = compiler.build_tw_ast(tokens, str(setup_project), str(tw_file), tw_src)
        assert page.let_vars["name"] == "WhatsApp"
        assert page.let_vars["version"] == "2.23.10"

    def test_unknown_function_fallback(self, setup_project, tmp_path):
        tw_src = '''page {
    title "Unknown"
    render static
}

let x = unknownFunc("test")

body {
    p "{x}"
}
'''
        tw_file = setup_project / "pages" / "unknown.tw"
        tw_file.write_text(tw_src)
        compiler._LIB_MODULES.clear()
        tokens = compiler.tokenize_tw(tw_src)
        page = compiler.build_tw_ast(tokens, str(setup_project), str(tw_file), tw_src)
        assert page.let_vars["x"] == 'unknownFunc("test")'

    def test_backward_compat(self, setup_project, tmp_path):
        tw_src = '''page {
    title "Simple"
    render static
}

let count: number = 5
let name: string = "World"

body {
    h1 "{name}"
}
'''
        tw_file = setup_project / "pages" / "simple.tw"
        tw_file.write_text(tw_src)
        compiler._LIB_MODULES.clear()
        tokens = compiler.tokenize_tw(tw_src)
        page = compiler.build_tw_ast(tokens, str(setup_project), str(tw_file), tw_src)
        assert page.let_vars["count"] == 5
        assert page.let_vars["name"] == "World"

    def test_lib_number_with_type(self, setup_project, tmp_path):
        lib_dir = setup_project / "lib"
        (lib_dir / "math.twm").write_text('fn double(n) {\n  return n * 2\n}\n')
        tw_src = '''page {
    title "Math"
    render static
}

load @./lib/math.twm

let result: number = double(21)

body {
    p "Result: {result}"
}
'''
        tw_file = setup_project / "pages" / "math.tw"
        tw_file.write_text(tw_src)
        compiler._LIB_MODULES.clear()
        tokens = compiler.tokenize_tw(tw_src)
        page = compiler.build_tw_ast(tokens, str(setup_project), str(tw_file), tw_src)
        assert page.let_vars["result"] == 42

    def test_lib_string_with_type(self, setup_project, tmp_path):
        lib_dir = setup_project / "lib"
        (lib_dir / "format.twm").write_text('fn formatName(name) {\n  return name.toUpperCase()\n}\n')
        tw_src = '''page {
    title "Format"
    render static
}

load @./lib/format.twm

let formatted: string = formatName("whatsapp")

body {
    h1 "{formatted}"
}
'''
        tw_file = setup_project / "pages" / "format.tw"
        tw_file.write_text(tw_src)
        compiler._LIB_MODULES.clear()
        tokens = compiler.tokenize_tw(tw_src)
        page = compiler.build_tw_ast(tokens, str(setup_project), str(tw_file), tw_src)
        assert page.let_vars["formatted"] == "WHATSAPP"

    def test_lib_array_with_type(self, setup_project, tmp_path):
        lib_dir = setup_project / "lib"
        (lib_dir / "list.twm").write_text('fn getItems() {\n  return ["apple", "banana", "cherry"]\n}\n')
        tw_src = '''page {
    title "List"
    render static
}

load @./lib/list.twm

let items: array = getItems()

body {
    p "Items: {items}"
}
'''
        tw_file = setup_project / "pages" / "list.tw"
        tw_file.write_text(tw_src)
        compiler._LIB_MODULES.clear()
        tokens = compiler.tokenize_tw(tw_src)
        page = compiler.build_tw_ast(tokens, str(setup_project), str(tw_file), tw_src)
        assert page.let_vars["items"] == ["apple", "banana", "cherry"]
