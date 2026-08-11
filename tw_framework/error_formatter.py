"""
Better error formatting for TW Framework.

Every error includes: error code, category, severity, file, relative path,
absolute path, line, column, highlighted code, explanation, reason,
expected, found, suggestions, and documentation link.
"""

import logging
import os
from typing import Any, Optional

from .diagnostics import Diagnostic

logger = logging.getLogger(__name__)


def format_error(diag: Diagnostic, project_root: str) -> Any:
    """Format a diagnostic into a human-readable string with all required fields."""
    lines = []
    # FIX #511: Handle numeric/short codes that don't have TW prefix
    _raw_code = str(diag.code) if diag.code else "0000"
    code_display = _raw_code if _raw_code.upper().startswith("TW") else f"TW{_raw_code}"
    lines.append(f"{code_display} • {diag.category} Error")
    lines.append("")
    lines.append(f"Severity: {diag.severity.upper()}")
    if diag.file_path:
        # v0.9.08 FIX #14: os.path.relpath crashes on Windows with different drives
        # (ValueError: path is on mount 'C:', start is on mount 'D:')
        try:
            rel_path = os.path.relpath(diag.file_path, project_root) if project_root else diag.file_path
        except (ValueError, TypeError):
            rel_path = diag.file_path
        lines.append(f"Project: {rel_path}")
        lines.append(f"Absolute: {os.path.abspath(diag.file_path)}")
    if diag.line:
        lines.append(f"Line: {diag.line}")
    if diag.col:
        lines.append(f"Column: {diag.col}")
    if diag.source_snippet:
        lines.append("")
        lines.append("Code:")
        # FIX #513: Escape source snippet to prevent terminal injection
        import html as _html
        lines.append(_html.escape(str(diag.source_snippet)))
    if diag.reason:
        lines.append("")
        lines.append(f"Reason: {diag.reason}")
    if diag.expected:
        lines.append(f"Expected: {diag.expected}")
    if diag.found:
        lines.append(f"Found: {diag.found}")
    if diag.why:
        # FIX #514: Truncate very long explanations
        _why = str(diag.why)
        if len(_why) > 500:
            _why = _why[:500] + "..."
        lines.append(f"Why: {_why}")
    if diag.suggestion and str(diag.suggestion).strip():
        # FIX #517: Don't print empty suggestion
        lines.append(f"Suggestion: {diag.suggestion}")
    if diag.doc_link:
        # FIX #516: Basic URL validation
        _link = str(diag.doc_link)
        if _link.startswith(("http://", "https://", "/")):
            lines.append(f"Docs: {_link}")
    # FIX #519: Show exception type if available
    _exc_type = getattr(diag, "exception_type", None)
    if _exc_type:
        lines.append(f"Exception: {_exc_type}")
    return "\n".join(lines)


__all__ = ["format_error"]
