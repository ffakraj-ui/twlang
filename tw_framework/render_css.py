from __future__ import annotations


def _legacy():
    from . import compiler

    return compiler


def parse_stylesheet(text: str):
    compiler = _legacy()
    return compiler.build_tss_ast_from_text(text)


def render_stylesheet(text: str, context=None, minify: bool = False) -> str:
    compiler = _legacy()
    sheet = parse_stylesheet(text)
    css = compiler.render_css(sheet, context=context or {})
    return compiler.minify_css_content(css) if minify else css


__all__ = ["parse_stylesheet", "render_stylesheet"]
