from __future__ import annotations

from dataclasses import dataclass
from typing import Dict, Optional

from .lowering import lower_program
from .parser import parse_file, parse_text
from .render_html import build_runtime_context, render_program_document
from .runtime_values import RuntimeEnvironment


@dataclass
class InterpreterResult:
    html: str
    context: Dict


class Interpreter:
    def run_program(self, program, context: Optional[Dict] = None, css_href: Optional[str] = None) -> InterpreterResult:
        ir_program = lower_program(program)
        runtime_context = build_runtime_context(program, context=context)
        html = render_program_document(ir_program, page_program=program, context=runtime_context, css_href=css_href)
        return InterpreterResult(html=html, context=runtime_context)

    def run_text(self, text: str, *, base_dir: str = ".", file_path: str = "<memory>", context: Optional[Dict] = None, css_href: Optional[str] = None) -> InterpreterResult:
        program = parse_text(text, base_dir=base_dir, file_path=file_path)
        return self.run_program(program, context=context, css_href=css_href)

    def run_file(self, path: str, context: Optional[Dict] = None, css_href: Optional[str] = None) -> InterpreterResult:
        program = parse_file(path)
        return self.run_program(program, context=context, css_href=css_href)


def run_file(path: str, context: Optional[Dict] = None, css_href: Optional[str] = None) -> InterpreterResult:
    return Interpreter().run_file(path, context=context, css_href=css_href)


def build_runtime_environment(initial: Optional[Dict] = None) -> RuntimeEnvironment:
    return RuntimeEnvironment(values=dict(initial or {}))


__all__ = ["Interpreter", "InterpreterResult", "build_runtime_environment", "run_file"]
