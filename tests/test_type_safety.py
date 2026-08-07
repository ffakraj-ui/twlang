"""
Tests for type safety in TW Framework.

Covers `let` and `state` block type annotations:
    let count: number = 5
    let name: string = "World"
    state {
        count: number = 0
    }
"""
from __future__ import annotations

import os
import sys

import pytest

# Ensure the framework is importable when tests are run from the repo root
sys.path.insert(0, os.path.join(os.path.dirname(__file__), ".."))

from tw_framework import compiler
from tw_framework import parser as tw_parser
from tw_framework import lowering, semantic
from tw_framework.ast_nodes import LetNode, Program, PageMeta, HeadModel
from tw_framework.reactivity import parse_state_block


# ─── Helpers ──────────────────────────────────────────────────────────────────

def _parse_let(src: str):
    tokens = compiler.tokenize_tw(src)
    return compiler.parse_let(tokens, 0)[0]


# ─── Valid type annotations ───────────────────────────────────────────────────

class TestValidTypeAnnotations:
    def test_number_int(self):
        node = _parse_let('let count: number = 5')
        assert node.name == "count"
        assert node.value == 5
        assert node.type_annotation == "number"

    def test_number_float(self):
        node = _parse_let('let price: number = 19.99')
        assert node.value == 19.99
        assert node.type_annotation == "number"

    def test_string(self):
        node = _parse_let('let name: string = "World"')
        assert node.value == "World"
        assert node.type_annotation == "string"

    def test_boolean_true(self):
        node = _parse_let('let isActive: boolean = true')
        assert node.value is True
        assert node.type_annotation == "boolean"

    def test_boolean_false(self):
        node = _parse_let('let isActive: boolean = false')
        assert node.value is False
        assert node.type_annotation == "boolean"

    def test_array(self):
        node = _parse_let('let items: array = ["a", "b"]')
        assert node.value == ["a", "b"]
        assert node.type_annotation == "array"

    def test_any_accepts_number(self):
        node = _parse_let('let data: any = 42')
        assert node.value == 42
        assert node.type_annotation == "any"

    def test_any_accepts_string(self):
        node = _parse_let('let data: any = "hello"')
        assert node.value == "hello"
        assert node.type_annotation == "any"

    def test_null_annotation(self):
        node = _parse_let('let x: null = null')
        assert node.value is None
        assert node.type_annotation == "null"


# ─── Backward compatibility (no type) ──────────────────────────────────────────

class TestBackwardCompatibility:
    def test_let_without_type(self):
        node = _parse_let('let count = 5')
        assert node.value == 5
        assert node.type_annotation is None

    def test_let_without_type_string(self):
        node = _parse_let('let name = "World"')
        assert node.value == "World"
        assert node.type_annotation is None


# ─── Type mismatch errors ─────────────────────────────────────────────────────

class TestTypeMismatch:
    def test_number_with_string_value(self):
        with pytest.raises(compiler.CompilerError, match="Type error"):
            _parse_let('let count: number = "hello"')

    def test_string_with_number_value(self):
        with pytest.raises(compiler.CompilerError, match="Type error"):
            _parse_let('let name: string = 42')

    def test_string_with_boolean_value(self):
        with pytest.raises(compiler.CompilerError, match="Type error"):
            _parse_let('let x: string = true')

    def test_boolean_with_number_value(self):
        with pytest.raises(compiler.CompilerError, match="Type error"):
            _parse_let('let x: boolean = 5')

    def test_array_with_number_value(self):
        with pytest.raises(compiler.CompilerError, match="Type error"):
            _parse_let('let x: array = 5')

    def test_number_with_boolean_value(self):
        with pytest.raises(compiler.CompilerError, match="Type error"):
            _parse_let('let x: number = true')


# ─── Invalid type names ───────────────────────────────────────────────────────

class TestInvalidTypeNames:
    def test_integer_not_valid(self):
        with pytest.raises(compiler.CompilerError, match="Unknown type"):
            _parse_let('let x: integer = 5')

    def test_int_not_valid(self):
        with pytest.raises(compiler.CompilerError, match="Unknown type"):
            _parse_let('let x: int = 5')

    def test_str_not_valid(self):
        with pytest.raises(compiler.CompilerError, match="Unknown type"):
            _parse_let('let x: str = "hello"')


# ─── infer_value_type helper ──────────────────────────────────────────────────

class TestInferValueType:
    def test_int_is_number(self):
        assert compiler.infer_value_type(5) == "number"

    def test_float_is_number(self):
        assert compiler.infer_value_type(3.14) == "number"

    def test_string(self):
        assert compiler.infer_value_type("hello") == "string"

    def test_true_is_boolean(self):
        assert compiler.infer_value_type(True) == "boolean"

    def test_false_is_boolean(self):
        assert compiler.infer_value_type(False) == "boolean"

    def test_list_is_array(self):
        assert compiler.infer_value_type([1, 2]) == "array"

    def test_dict_is_object(self):
        assert compiler.infer_value_type({"a": 1}) == "object"

    def test_none_is_null(self):
        assert compiler.infer_value_type(None) == "null"


# ─── State block type annotations ──────────────────────────────────────────────

class TestStateBlockTypes:
    def test_state_with_types(self):
        source = '''
        state {
            count: number = 0
            name: string = "hello"
            isActive: boolean = true
            items: array = ["a", "b"]
        }
        '''
        result = parse_state_block(source)
        assert result["count"] == 0
        assert result["name"] == "hello"
        assert result["isActive"] is True
        assert result["items"] == ["a", "b"]

    def test_state_without_types_backward_compat(self):
        source = '''
        state {
            count 0
            name "hello"
            isActive true
        }
        '''
        result = parse_state_block(source)
        assert result["count"] == 0
        assert result["name"] == "hello"
        assert result["isActive"] is True


# ─── Full .tw file integration ────────────────────────────────────────────────

class TestFullFileIntegration:
    SOURCE = '''page {
    title "Type Safety Test"
    render static
}

let count: number = 42
let name: string = "TW Lang"
let isActive: boolean = true
let items: array = ["apple", "banana"]
let data: any = "anything"

body {
    h1 "Count: {count}"
    p "Name: {name}"
    p "Active: {isActive}"
}
'''

    BAD_SOURCE = '''page {
    title "Bad Type"
    render static
}

let count: number = "not a number"

body {
    h1 "Count: {count}"
}
'''

    def test_full_build_with_types(self, tmp_path):
        tw_file = tmp_path / "test.tw"
        tw_file.write_text(self.SOURCE)
        tokens = compiler.tokenize_tw(self.SOURCE)
        page = compiler.build_tw_ast(tokens, str(tmp_path), str(tw_file), self.SOURCE)
        assert page.let_vars["count"] == 42
        assert page.let_vars["name"] == "TW Lang"
        assert page.let_vars["isActive"] is True
        assert page.let_vars["items"] == ["apple", "banana"]
        assert page.let_vars["data"] == "anything"

    def test_type_mismatch_raises(self, tmp_path):
        tw_file = tmp_path / "bad.tw"
        tw_file.write_text(self.BAD_SOURCE)
        with pytest.raises(compiler.CompilerError, match="Type error"):
            tokens = compiler.tokenize_tw(self.BAD_SOURCE)
            compiler.build_tw_ast(tokens, str(tmp_path), str(tw_file), self.BAD_SOURCE)

    def test_modular_ast_pipeline(self):
        program = tw_parser.parse_text(self.SOURCE, file_path="test.tw")
        assert program.lets["count"] == 42
        assert program.lets["name"] == "TW Lang"
        assert program.lets["isActive"] is True

    def test_ir_lowering(self):
        program = tw_parser.parse_text(self.SOURCE, file_path="test.tw")
        ir_program = lowering.lower_program(program)
        assert ir_program.lets["count"] == 42
        assert ir_program.lets["name"] == "TW Lang"

    def test_semantic_analyzer_valid(self):
        program = tw_parser.parse_text(self.SOURCE, file_path="test.tw")
        diag_bag = semantic.analyze_program(program)
        type_errors = [
            d for d in diag_bag.items
            if d.severity == "error" and "Type error" in d.message
        ]
        assert len(type_errors) == 0

    def test_semantic_analyzer_mismatch(self):
        # Manually create a LetNode with mismatched type
        bad_let = LetNode("x", "hello", type_annotation="number")
        program = Program(
            meta=PageMeta(title="Test"),
            head=HeadModel(),
            lets={},
            body=[bad_let],
        )
        diag_bag = semantic.analyze_program(program)
        type_errors = [
            d for d in diag_bag.items
            if d.severity == "error" and "Type error" in d.message
        ]
        assert len(type_errors) == 1
        assert "annotated as `number`" in type_errors[0].message
        assert "got `string`" in type_errors[0].message
