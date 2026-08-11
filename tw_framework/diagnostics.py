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
    def from_legacy(cls, item: Any) -> "Diagnostic":
        """Create Diagnostic from a legacy error/dict object.
        v0.9.08 FIX: Uses vars() instead of 20 manual getattr() calls.
        """
        if isinstance(item, dict):
            return cls(**{k: v for k, v in item.items() if k in cls.__dataclass_fields__})
        attrs = vars(item) if hasattr(item, "__dict__") else {}
        known = {k: v for k, v in attrs.items() if k in cls.__dataclass_fields__}
        return cls(**known)

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
