"""
Better error formatting for TW Framework.

Every error includes: error code, category, severity, file, relative path,
absolute path, line, column, highlighted code, explanation, reason,
expected, found, suggestions, and documentation link.
"""

import logging
import os
from typing import Optional

from .diagnostics import Diagnostic

logger = logging.getLogger(__name__)


def format_error(diag: Diagnostic, project_root: str) -> str:
    """Format a diagnostic into a human-readable string with all required fields."""
    lines = []
    code_display = diag.code if str(diag.code).upper().startswith("TW") else f"TW{diag.code}"
    lines.append(f"{code_display} • {diag.category} Error")
    lines.append("")
    lines.append(f"Severity: {diag.severity.upper()}")
    if diag.file_path:
        rel_path = os.path.relpath(diag.file_path, project_root) if project_root else diag.file_path
        lines.append(f"Project: {rel_path}")
        lines.append(f"Absolute: {os.path.abspath(diag.file_path)}")
    if diag.line:
        lines.append(f"Line: {diag.line}")
    if diag.col:
        lines.append(f"Column: {diag.col}")
    if diag.source_snippet:
        lines.append("")
        lines.append("Code:")
        lines.append(diag.source_snippet)
    if diag.reason:
        lines.append("")
        lines.append(f"Reason: {diag.reason}")
    if diag.expected:
        lines.append(f"Expected: {diag.expected}")
    if diag.found:
        lines.append(f"Found: {diag.found}")
    if diag.why:
        lines.append(f"Why: {diag.why}")
    if diag.suggestion:
        lines.append(f"Suggestion: {diag.suggestion}")
    if diag.doc_link:
        lines.append(f"Docs: {diag.doc_link}")
    return "\n".join(lines)


__all__ = ["format_error"]
