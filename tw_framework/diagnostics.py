from __future__ import annotations

from dataclasses import dataclass, field
from typing import Iterable, List, Optional


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

    @classmethod
    def from_legacy(cls, item):
        return cls(
            severity=getattr(item, "severity", "error"),
            code=getattr(item, "code", "TW0000"),
            message=getattr(item, "message", str(item)),
            file_path=getattr(item, "file_path", "") or "",
            line=getattr(item, "line", 0) or 0,
            col=getattr(item, "col", 0) or 0,
            suggestion=getattr(item, "suggestion", None),
            notes=list(getattr(item, "notes", []) or []),
            phase=getattr(item, "phase", None),
            exception_type=getattr(item, "exception_type", None),
        )

    def to_dict(self):
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


class DiagnosticBag:
    def __init__(self):
        self.items: List[Diagnostic] = []

    def add(self, diagnostic: Diagnostic):
        self.items.append(diagnostic)

    def extend(self, diagnostics: Iterable[Diagnostic]):
        self.items.extend(diagnostics)

    @property
    def has_errors(self) -> bool:
        return any(item.severity == "error" for item in self.items)

    def to_list(self):
        return [item.to_dict() for item in self.items]


__all__ = ["Diagnostic", "DiagnosticBag"]
