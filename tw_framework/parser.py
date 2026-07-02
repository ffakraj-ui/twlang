from __future__ import annotations

import os
import ast
import warnings
from typing import Any, List

from .ast_nodes import (
    Attribute,
    ComponentNode,
    ElementNode,
    ForNode,
    HeadModel,
    IfNode,
    LetNode,
    PageMeta,
    Program,
    ScriptNode,
    node_to_dict,
)
from .lexer import tokenize_tw


def _legacy():
    from . import compiler

    return compiler


def _convert_node(node: Any):
    tag = getattr(node, "tag", "")
    if tag == "__let__":
        return LetNode(node.name, node.value)
    if tag == "__if__":
        return IfNode(
            condition=node.condition,
            children=[_convert_node(child) for child in getattr(node, "children", [])],
            else_children=[_convert_node(child) for child in getattr(node, "else_children", [])],
        )
    if tag == "__for__":
        return ForNode(
            var_name=node.var_name,
            iterable=node.list_expr,
            children=[_convert_node(child) for child in getattr(node, "children", [])],
        )
    if tag == "__script__":
        return ScriptNode(node.raw_js)
    if tag == "__script_tag__":
        # Declarative external script tag (Next.js-like). In the modular AST we
        # model it as a regular <script> element with a data attribute so the
        # structure is still meaningful for analysis/debugging.
        return ElementNode(
            tag="script",
            text=None,
            attrs=[
                Attribute(name="src", value=getattr(node, "src", "")),
                Attribute(name="data-tw-strategy", value=getattr(node, "strategy", "")),
            ],
            styles=[],
            events=[],
            router={},
            children=[],
        )
    if tag == "__component__":
        return ComponentNode(
            name=node.name,
            props=[Attribute(name=name, value=value) for name, value in getattr(node, "props", [])],
            children=[_convert_node(child) for child in getattr(node, "children", [])],
        )
    return ElementNode(
        tag=getattr(node, "tag", "div"),
        text=getattr(node, "text", None),
        attrs=[Attribute(name=name, value=value) for name, value in getattr(node, "attrs", [])],
        styles=[Attribute(name=name, value=value) for name, value in getattr(node, "inline_style", [])],
        events=[Attribute(name=name, value=value) for name, value in getattr(node, "events", [])],
        router=dict(getattr(node, "router", {}) or {}),
        children=[_convert_node(child) for child in getattr(node, "children", [])],
    )


def _normalize_scalar(value: Any):
    compiler = _legacy()
    if not isinstance(value, str):
        return value
    stripped = value.strip()
    if len(stripped) >= 2 and stripped[0] == stripped[-1] and stripped[0] in {"'", '"'}:
        try:
            return ast.literal_eval(stripped)
        except Exception as err:
            warnings.warn(
                f"Malformed quoted literal {stripped!r}: {err}. Falling back to raw string content.",
                RuntimeWarning,
            )
            return stripped[1:-1]
    return compiler.parse_literal_value(stripped)


def from_legacy_page(page, source_path: str = "") -> Program:
    program = Program(
        meta=PageMeta(
            title=page.title,
            layout=page.layout,
            layouts=list(getattr(page, "layouts", []) or []),
            render_mode=page.render_mode,
            revalidate=page.revalidate,
            redirect_to=page.redirect_to,
            rewrite_to=page.rewrite_to,
            responsive=bool(getattr(page, "responsive", False)),
        ),
        head=HeadModel(
            metas=list(getattr(page.head, "metas", []) or []),
            icon=getattr(page.head, "icon", None),
            seo=dict(getattr(page.head, "seo", {}) or {}),
        ),
        lets={key: _normalize_scalar(value) for key, value in dict(getattr(page, "let_vars", {}) or {}).items()},
        state={key: _normalize_scalar(value) for key, value in dict(getattr(page, "state_vars", {}) or {}).items()},
        body=[_convert_node(node) for node in getattr(page, "body", [])],
        loaded_sheets=list(getattr(page, "loaded_sheets", []) or []),
        loaded_json=list(getattr(page, "loaded_json", []) or []),
        source_path=source_path or getattr(page, "_tw_source_path", ""),
        legacy_page=page,
    )
    return program


def parse_text(text: str, base_dir: str = ".", file_path: str = "<memory>") -> Program:
    compiler = _legacy()
    tokens = compiler.tokenize_tw(text)
    page = compiler.build_tw_ast(tokens, base_dir, file_path, text)
    page._tw_source_path = file_path
    return from_legacy_page(page, source_path=file_path)


def parse_file(path: str) -> Program:
    compiler = _legacy()
    source = compiler.read_text_file(path)
    return parse_text(source, base_dir=compiler.normalize_path(os.path.dirname(path)), file_path=path)


def build_tw_ast(tokens, base_dir, file_path, source):
    compiler = _legacy()
    return compiler.build_tw_ast(tokens, base_dir, file_path, source)


def build_tss_ast_from_text(text: str):
    compiler = _legacy()
    return compiler.build_tss_ast_from_text(text)


def program_to_dict(program: Program):
    return program.to_dict()


def nodes_to_dict(nodes: List[Any]):
    return [node_to_dict(node) for node in nodes]


__all__ = [
    "build_tss_ast_from_text",
    "build_tw_ast",
    "from_legacy_page",
    "nodes_to_dict",
    "parse_file",
    "parse_text",
    "program_to_dict",
    "tokenize_tw",
]
