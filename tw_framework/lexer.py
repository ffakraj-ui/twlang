from __future__ import annotations

from dataclasses import dataclass
from typing import List


@dataclass
class LexerToken:
    type: str
    value: str
    line: int
    col: int

    def to_dict(self):
        return {
            "type": self.type,
            "value": self.value,
            "line": self.line,
            "col": self.col,
        }


def _legacy():
    from . import compiler

    return compiler


def tokenize(code: str, allow_inline_scripts: bool = True) -> List[LexerToken]:
    compiler = _legacy()
    tokens = compiler.tokenize(code, allow_inline_scripts=allow_inline_scripts)
    return [
        LexerToken(
            type=token.type,
            value=token.value,
            line=token.line,
            col=token.col,
        )
        for token in tokens
    ]


def tokenize_tw(code: str) -> List[LexerToken]:
    return tokenize(code, allow_inline_scripts=True)


def tokenize_file(path: str) -> List[LexerToken]:
    compiler = _legacy()
    return tokenize_tw(compiler.read_text_file(path))


__all__ = ["LexerToken", "tokenize", "tokenize_file", "tokenize_tw"]
