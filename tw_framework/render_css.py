from __future__ import annotations

from typing import Any, Optional


def _legacy() -> Any:
    from . import compiler

    return compiler


def parse_stylesheet(text: str) -> Any:
    compiler = _legacy()
    return compiler.build_tss_ast_from_text(text)


def render_stylesheet(text: str, context=None, minify: bool = False) -> Any:
    compiler = _legacy()
    sheet = parse_stylesheet(text)
    css = compiler.render_css(sheet, context=context or {})
    return compiler.minify_css_content(css) if minify else css


__all__ = ["parse_stylesheet", "render_stylesheet"]
