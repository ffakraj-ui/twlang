from __future__ import annotations

import logging
from typing import Dict, Optional

from .ast_nodes import ComponentNode, ElementNode, ForNode, IfNode, LetNode, Program
from .diagnostics import Diagnostic, DiagnosticBag

logger = logging.getLogger(__name__)


def _legacy():
    from . import compiler

    return compiler


class SemanticAnalyzer:
    def _check_expression(self, expr, scope, diagnostics: DiagnosticBag, source_path: str, label: str):
        compiler = _legacy()
        try:
            names = compiler.collect_expression_names(expr)
        except Exception as err:
            logger.exception("Failed to collect expression names (%s) in %s: %r", source_path, label, expr)
            names = set()
        for name in sorted(names):
            if name not in scope:
                diagnostics.add(
                    Diagnostic(
                        severity="error",
                        code="TW2101",
                        message=f"Unknown name `{name}` in {label}.",
                        file_path=source_path,
                    )
                )

    def _check_interpolations(self, text, scope, diagnostics: DiagnosticBag, source_path: str, label: str):
        compiler = _legacy()
        if not isinstance(text, str):
            return
        for expr in compiler.extract_placeholder_expressions(text):
            self._check_expression(expr, scope, diagnostics, source_path, label)

    def _walk_nodes(self, nodes, scope, diagnostics: DiagnosticBag, source_path: str):
        next_scope = dict(scope)
        for node in nodes:
            if isinstance(node, LetNode):
                next_scope[node.name] = node.value
                self._check_interpolations(node.value, next_scope, diagnostics, source_path, f"`let {node.name}`")
                continue
            if isinstance(node, IfNode):
                self._check_expression(node.condition, next_scope, diagnostics, source_path, "`if` condition")
                self._walk_nodes(node.children, dict(next_scope), diagnostics, source_path)
                self._walk_nodes(node.else_children, dict(next_scope), diagnostics, source_path)
                continue
            if isinstance(node, ForNode):
                self._check_expression(node.iterable, next_scope, diagnostics, source_path, "`for` iterable")
                child_scope = dict(next_scope)
                child_scope[node.var_name] = True
                self._walk_nodes(node.children, child_scope, diagnostics, source_path)
                continue
            if isinstance(node, ElementNode):
                self._check_interpolations(node.text, next_scope, diagnostics, source_path, f"`{node.tag}` text")
                for attr in node.attrs + node.styles + node.events:
                    self._check_interpolations(attr.value, next_scope, diagnostics, source_path, f"`{node.tag}` `{attr.name}`")
                for value in node.router.values():
                    self._check_interpolations(value, next_scope, diagnostics, source_path, f"`{node.tag}` router")
                self._walk_nodes(node.children, dict(next_scope), diagnostics, source_path)
                continue
            if isinstance(node, ComponentNode):
                for prop in node.props:
                    self._check_interpolations(prop.value, next_scope, diagnostics, source_path, f"`{node.name}` prop `{prop.name}`")
                self._walk_nodes(node.children, dict(next_scope), diagnostics, source_path)

    def _check_page_meta(self, program: Program, diagnostics: DiagnosticBag, source_path: str):
        meta = program.meta

        valid_render_modes = {"static", "server", "edge"}
        if meta.render_mode not in valid_render_modes:
            diagnostics.add(
                Diagnostic(
                    severity="error",
                    code="TW2201",
                    message=f'Invalid `render` mode "{meta.render_mode}". Use one of: static, server, edge.',
                    file_path=source_path,
                )
            )

        if meta.render_mode == "static" and meta.revalidate is not None:
            diagnostics.add(
                Diagnostic(
                    severity="warning",
                    code="TW2202",
                    message="`revalidate` has no effect on `render static` pages. "
                            "Use `render server` or `render edge` for ISR-style revalidation.",
                    file_path=source_path,
                )
            )

        if meta.revalidate is not None and meta.revalidate < 0:
            diagnostics.add(
                Diagnostic(
                    severity="error",
                    code="TW2203",
                    message=f"`revalidate` must be a non-negative number, got {meta.revalidate}.",
                    file_path=source_path,
                )
            )

        if meta.redirect_to and meta.rewrite_to:
            diagnostics.add(
                Diagnostic(
                    severity="error",
                    code="TW2204",
                    message="A page cannot define both `redirect` and `rewrite` at the same time.",
                    file_path=source_path,
                )
            )

    def analyze(self, program: Program, context: Optional[Dict] = None) -> DiagnosticBag:
        diagnostics = DiagnosticBag()
        compiler = _legacy()

        if program.legacy_page and program.source_path:
            try:
                analysis_context = context or compiler.create_base_context(program.legacy_page, program.source_path)
            except Exception as err:
                logger.exception("Failed to create base context for %s", program.source_path)
                analysis_context = context or {}
            legacy_items = compiler.analyze_page_semantics(
                program.legacy_page,
                analysis_context,
                program.source_path,
            )
            diagnostics.extend(Diagnostic.from_legacy(item) for item in legacy_items)

        if not program.meta.title:
            diagnostics.add(
                Diagnostic(
                    severity="warning",
                    code="TW2001",
                    message='Page title is empty. Consider setting `page { title "..." }`.',
                    file_path=program.source_path,
                )
            )

        self._check_page_meta(program, diagnostics, program.source_path)

        scope = {}
        scope.update(program.lets)
        scope.update(program.state)
        scope.update(context or {})
        self._walk_nodes(program.body, scope, diagnostics, program.source_path)

        return diagnostics


def analyze_program(program: Program, context: Optional[Dict] = None) -> DiagnosticBag:
    return SemanticAnalyzer().analyze(program, context=context)


__all__ = ["SemanticAnalyzer", "analyze_program"]
