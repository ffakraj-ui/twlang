from __future__ import annotations

from dataclasses import dataclass, field
from typing import Any, Dict, Iterable, List, Optional


@dataclass
class Diagnostic:
    severity: str
    code: str
    message: str
    file_path: str = ""
    line: int = 0
    col: int = 0
    suggestion: Optional[str] = None
    notes: List[str] = field(default_factory=list)
    phase: Optional[str] = None
    exception_type: Optional[str] = None
    category: str = "compiler"
    relative_path: str = ""
    absolute_path: str = ""
    source_snippet: str = ""
    highlight: str = ""
    reason: str = ""
    expected: str = ""
    found: str = ""
    why: str = ""
    doc_link: str = ""
    parser_state: str = ""
    traceback: str = ""

    @classmethod
    def from_legacy(cls, item) -> Any:
        return cls(
            severity=getattr(item, "severity", "error"),
            code=getattr(item, "code", "TW0000"),
            message=getattr(item, "message", str(item)),
            file_path=getattr(item, "file_path", "") or "",
            line=getattr(item, "line", 0) or 0,
            col=getattr(item, "col", 0) or 0,
            suggestion=getattr(item, "suggestion", None),
            notes=list(getattr(item, "notes", []) or []),
            category=getattr(item, "category", "compiler") or "compiler",
            relative_path=getattr(item, "relative_path", "") or "",
            absolute_path=getattr(item, "absolute_path", "") or "",
            source_snippet=getattr(item, "source_snippet", "") or "",
            highlight=getattr(item, "highlight", "") or "",
            reason=getattr(item, "reason", "") or "",
            expected=getattr(item, "expected", "") or "",
            found=getattr(item, "found", "") or "",
            why=getattr(item, "why", "") or "",
            doc_link=getattr(item, "doc_link", "") or "",
            parser_state=getattr(item, "parser_state", "") or "",
            traceback=getattr(item, "traceback", "") or "",
            phase=getattr(item, "phase", None),
            exception_type=getattr(item, "exception_type", None),
        )

    def to_dict(self) -> Dict[str, Any]:
        return {
            "severity": self.severity,
            "code": self.code,
            "message": self.message,
            "file_path": self.file_path,
            "line": self.line,
            "col": self.col,
            "suggestion": self.suggestion,
            "notes": list(self.notes),
            "phase": self.phase,
            "exception_type": self.exception_type,
        }


def format_advanced_error(diag: Diagnostic, project_root: str = "") -> Any:
    """Format a diagnostic with all required fields."""
    from .error_formatter import format_error
    return format_error(diag, project_root)


class DiagnosticBag:
    def __init__(self) -> None:
        self.items: List[Diagnostic] = []

    def add(self, diagnostic: Diagnostic) -> None:
        self.items.append(diagnostic)

    def extend(self, diagnostics: Iterable[Diagnostic]) -> None:
        self.items.extend(diagnostics)

    @property
    def has_errors(self) -> Any:
        return any(item.severity == "error" for item in self.items)

    def to_list(self) -> List[Any]:
        return [item.to_dict() for item in self.items]


__all__ = ["Diagnostic", "DiagnosticBag"]
