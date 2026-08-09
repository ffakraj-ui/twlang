"""
Error Boundaries for TW Framework.

Provides application-level error handling:
- Route errors (404, 500)
- Client errors
- Server errors
- Loading states
- Fallback UI
- Development error details
- Production-safe error messages
"""

from __future__ import annotations

import html
import os
import traceback
from dataclasses import dataclass, field
from typing import Any, Dict, List, Optional


@dataclass
class ErrorInfo:
    """Information about an error."""
    code: int = 500
    title: str = "Server Error"
    message: str = "Something went wrong"
    file: str = ""
    line: int = 0
    col: int = 0
    stack: str = ""
    suggestion: str = ""
    is_dev: bool = False


def render_error_page(error: ErrorInfo) -> str:
    """Render an error page as HTML."""
    safe_title = html.escape(error.title)
    safe_message = html.escape(error.message)

    # Production: hide stack traces and internal details
    if not error.is_dev:
        if error.code == 404:
            safe_message = "The page you are looking for does not exist."
        elif error.code == 500:
            safe_message = "An internal server error occurred. Please try again later."
        elif error.code == 403:
            safe_message = "You do not have permission to access this page."

    dev_details = ""
    if error.is_dev and error.stack:
        safe_stack = html.escape(error.stack)
        dev_details = f"""
    <details class="tw-error-details">
      <summary>Stack Trace</summary>
      <pre>{safe_stack}</pre>
    </details>"""
        if error.file:
            dev_details += f"\n    <p><strong>File:</strong> {html.escape(error.file)}:{error.line}:{error.col}</p>"
        if error.suggestion:
            dev_details += f"\n    <p><strong>Suggestion:</strong> {html.escape(error.suggestion)}</p>"

    return f"""<!DOCTYPE html>
<html lang="en">
<head>
  <meta charset="UTF-8">
  <meta name="viewport" content="width=device-width, initial-scale=1.0">
  <title>{error.code} — {safe_title}</title>
  <style>
    * {{ margin: 0; padding: 0; box-sizing: border-box; }}
    body {{
      font-family: -apple-system, BlinkMacSystemFont, 'Segoe UI', Roboto, sans-serif;
      background: #f5f5f5;
      color: #333;
      min-height: 100vh;
      display: flex;
      align-items: center;
      justify-content: center;
      padding: 2rem;
    }}
    .tw-error {{
      background: white;
      border-radius: 8px;
      padding: 3rem;
      max-width: 600px;
      width: 100%;
      box-shadow: 0 2px 8px rgba(0,0,0,0.1);
    }}
    .tw-error-code {{
      font-size: 4rem;
      font-weight: bold;
      color: {'#e53e3e' if error.code >= 500 else '#3182ce' if error.code >= 400 else '#38a169'};
      line-height: 1;
      margin-bottom: 1rem;
    }}
    .tw-error-title {{
      font-size: 1.5rem;
      font-weight: 600;
      margin-bottom: 0.5rem;
    }}
    .tw-error-message {{
      color: #666;
      margin-bottom: 2rem;
    }}
    .tw-error-details {{
      margin-top: 2rem;
      padding: 1rem;
      background: #f7f7f7;
      border-radius: 4px;
    }}
    .tw-error-details summary {{
      cursor: pointer;
      font-weight: 500;
      margin-bottom: 0.5rem;
    }}
    .tw-error-details pre {{
      font-size: 0.875rem;
      overflow-x: auto;
      white-space: pre-wrap;
      word-break: break-all;
    }}
    .tw-error-actions {{
      margin-top: 2rem;
      display: flex;
      gap: 1rem;
    }}
    .tw-error-actions a {{
      display: inline-block;
      padding: 0.5rem 1.5rem;
      background: #3182ce;
      color: white;
      text-decoration: none;
      border-radius: 4px;
      font-weight: 500;
    }}
    .tw-error-actions a:hover {{
      background: #2c5aa0;
    }}
  </style>
</head>
<body>
  <div class="tw-error">
    <div class="tw-error-code">{error.code}</div>
    <h1 class="tw-error-title">{safe_title}</h1>
    <p class="tw-error-message">{safe_message}</p>{dev_details}
    <div class="tw-error-actions">
      <a href="/">Go Home</a>
      <a href="javascript:history.back()">Go Back</a>
    </div>
  </div>
</body>
</html>"""


def render_error_from_exception(
    err: Exception,
    is_dev: bool = False,
    file_path: str = "",
) -> str:
    """Create an error page from a Python exception."""
    error = ErrorInfo(
        code=500,
        title=type(err).__name__,
        message=str(err),
        file=file_path,
        stack=traceback.format_exc() if is_dev else "",
        is_dev=is_dev,
    )
    return render_error_page(error)


def render_404(path: str = "", is_dev: bool = False) -> str:
    """Render a 404 error page."""
    error = ErrorInfo(
        code=404,
        title="Not Found",
        message=f"Route not found: {path}" if path else "Page not found",
        is_dev=is_dev,
    )
    return render_error_page(error)


def render_500(message: str = "", is_dev: bool = False, err: Exception = None) -> str:
    """Render a 500 error page."""
    error = ErrorInfo(
        code=500,
        title="Server Error",
        message=message or "An internal server error occurred",
        stack=traceback.format_exc() if is_dev and err else "",
        is_dev=is_dev,
    )
    return render_error_page(error)


def render_loading() -> str:
    """Render a loading state placeholder."""
    return """<div class="tw-loading" style="padding:2rem;text-align:center;">
  <div style="display:inline-block;width:2rem;height:2rem;border:3px solid #e0e0e0;border-top-color:#3182ce;border-radius:50%;animation:tw-spin 0.8s linear infinite;"></div>
  <style>@keyframes tw-spin{to{transform:rotate(360deg)}}</style>
</div>"""


# Client-side error boundary JS
_ERROR_BOUNDARY_JS = """// TW Error Boundary Runtime
(function(){
'use strict';
window.__tw = window.__tw || {};
__tw.errorBoundary = {
  _handlers: [],

  catch: function(fn) {
    try { return fn(); }
    catch(err) {
      console.error('[TW Error]', err);
      this._handlers.forEach(function(h) { try { h(err); } catch(e){} });
      return null;
    }
  },

  register: function(handler) {
    this._handlers.push(handler);
    return function() {
      var idx = this._handlers.indexOf(handler);
      if (idx > -1) this._handlers.splice(idx, 1);
    }.bind(this);
  },

  wrap: function(element, fallbackHTML) {
    try {
      if (typeof element === 'function') element();
    } catch(err) {
      var target = typeof element === 'string' ? document.querySelector(element) : element;
      if (target && fallbackHTML) target.innerHTML = fallbackHTML;
    }
  }
};

window.addEventListener('error', function(e) {
  __tw.errorBoundary._handlers.forEach(function(h) {
    try { h(e.error); } catch(_){}
  });
});
})();"""


def get_error_boundary_js() -> str:
    return _ERROR_BOUNDARY_JS


__all__ = [
    "ErrorInfo", "render_error_page", "render_error_from_exception",
    "render_404", "render_500", "render_loading", "get_error_boundary_js",
]
