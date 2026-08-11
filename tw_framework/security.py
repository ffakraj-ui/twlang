"""
TW Security Module (v0.8.1)

Security improvements for TW Framework:
  - CSP (Content Security Policy) nonce generation
  - Secure HTTP headers
  - Input sanitization for HTML/JS injection prevention
  - CSRF token validation helpers
  - XSS prevention utilities
"""

from __future__ import annotations

import html
import os
import re
import secrets
from typing import Any, Dict, List, Optional, Tuple


# ─── CSP Nonce ────────────────────────────────────────────────────────────────

def generate_csp_nonce() -> str:
    """Generate a cryptographically secure nonce for CSP."""
    return secrets.token_urlsafe(16)


def build_csp_header(
    nonce: str = "",
    extra_directives: Optional[Dict[str, str]] = None,
    allow_inline: bool = False,
) -> str:
    """
    Build a Content-Security-Policy header string.

    Args:
        nonce: CSP nonce for script/style elements
        extra_directives: Additional CSP directives
        allow_inline: Allow 'unsafe-inline' (not recommended for production)
    """
    directives = {
        "default-src": "'self'",
        "script-src": "'self'" + (" 'unsafe-inline'" if allow_inline else "") + (f" 'nonce-{nonce}'" if nonce else ""),
        "style-src": "'self'" + (" 'unsafe-inline'" if allow_inline else "") + (f" 'nonce-{nonce}'" if nonce else ""),
        "img-src": "'self' data: https:",
        "font-src": "'self' data: https:",
        "connect-src": "'self' https: wss: ws:",
        "frame-ancestors": "'self'",
        "base-uri": "'self'",
        "form-action": "'self'",
        "object-src": "'none'",
    }

    if extra_directives:
        for key, value in extra_directives.items():
            if key in directives:
                directives[key] = directives[key] + " " + value
            else:
                directives[key] = value

    return "; ".join(f"{k} {v}" for k, v in directives.items())


# ─── Secure Headers ───────────────────────────────────────────────────────────

def get_secure_headers(
    csp_nonce: str = "",
    hsts_max_age: int = 31536000,
    include_hsts: bool = True,
) -> List[Tuple[str, str]]:
    """
    Return a list of secure HTTP headers.

    Returns:
        List of (header_name, header_value) tuples
    """
    headers = []

    # Content-Security-Policy
    if csp_nonce:
        headers.append(("Content-Security-Policy", build_csp_header(nonce=csp_nonce)))
    else:
        headers.append(("Content-Security-Policy", build_csp_header()))

    # Strict-Transport-Security (HSTS)
    if include_hsts:
        headers.append((
            "Strict-Transport-Security",
            f"max-age={hsts_max_age}; includeSubDomains; preload"
        ))

    # X-Content-Type-Options
    headers.append(("X-Content-Type-Options", "nosniff"))

    # X-Frame-Options (defense-in-depth alongside CSP frame-ancestors)
    headers.append(("X-Frame-Options", "SAMEORIGIN"))

    # X-XSS-Protection (legacy browsers)
    headers.append(("X-XSS-Protection", "1; mode=block"))

    # Referrer-Policy
    headers.append(("Referrer-Policy", "strict-origin-when-cross-origin"))

    # Permissions-Policy
    headers.append((
        "Permissions-Policy",
        "camera=(), microphone=(), geolocation=(), payment=()"
    ))

    # Cross-Origin policies
    headers.append(("Cross-Origin-Opener-Policy", "same-origin"))
    headers.append(("Cross-Origin-Resource-Policy", "same-origin"))

    return headers


def render_secure_headers_html(csp_nonce: str = "") -> str:
    """Render secure headers as <meta> tags for static HTML.

    FIX #145: frame-ancestors CSP directive does NOT work in <meta> tags.
    It only works as an HTTP header. For static HTML, we rely on
    X-Frame-Options as a fallback. The full CSP (including frame-ancestors)
    should be set as HTTP headers by the server (see get_secure_headers()).
    """
    tags = []
    if csp_nonce:
        tags.append(f'<meta http-equiv="Content-Security-Policy" content="{html.escape(build_csp_header(nonce=csp_nonce))}">')
    tags.append('<meta http-equiv="X-Content-Type-Options" content="nosniff">')
    tags.append('<meta http-equiv="X-Frame-Options" content="SAMEORIGIN">')
    tags.append('<meta http-equiv="Referrer-Policy" content="strict-origin-when-cross-origin">')
    return "\n".join(tags)


# ─── Input Sanitization ───────────────────────────────────────────────────────

def sanitize_html(text: str) -> str:
    """Escape HTML special characters to prevent XSS."""
    return html.escape(text, quote=True)


def sanitize_attribute(value: str) -> str:
    """Sanitize an HTML attribute value — escape quotes and special chars."""
    return html.escape(value, quote=True)


def sanitize_js_string(text: str) -> str:
    """Sanitize a string for safe inclusion in JavaScript."""
    # Escape backslashes, quotes, newlines, and other dangerous chars
    text = text.replace("\\", "\\\\")
    text = text.replace("'", "\\'")
    text = text.replace('"', '\\"')
    text = text.replace("\n", "\\n")
    text = text.replace("\r", "\\r")
    text = text.replace("\t", "\\t")
    text = text.replace("</script>", "<\\/script>")
    text = text.replace("<!--", "<\\!--")
    return text


def sanitize_url(url: str) -> str:
    """
    Sanitize a URL to prevent javascript: and data: scheme attacks.
    Only allows http:, https:, and relative URLs.
    """
    url = url.strip()
    lower = url.lower()

    # Block dangerous schemes
    if lower.startswith(("javascript:", "data:", "vbscript:", "file:")):
        return ""

    # Allow relative URLs
    if url.startswith(("/", "#", "?", "./", "../")):
        return url

    # Allow http/https
    if lower.startswith(("http://", "https://")):
        return url

    # Allow mailto and tel
    if lower.startswith(("mailto:", "tel:")):
        return url

    # Default: treat as relative
    return url


# ─── CSRF Protection ─────────────────────────────────────────────────────────

def generate_csrf_token() -> str:
    """Generate a CSRF token."""
    return secrets.token_urlsafe(32)


def validate_csrf_token(token: str, expected: str) -> bool:
    """Validate a CSRF token using constant-time comparison."""
    if not token or not expected:
        return False
    return secrets.compare_digest(token, expected)


def render_csrf_meta_tag(token: str) -> str:
    """Render CSRF token as a meta tag for forms."""
    return f'<meta name="csrf-token" content="{sanitize_attribute(token)}">'


# ─── Path Traversal Prevention ───────────────────────────────────────────────

def safe_join_path(base: str, path: str) -> Optional[str]:
    """
    Safely join a base path with a user-provided path.
    Returns None if the resulting path would escape the base directory.
    """
    base_abs = os.path.abspath(base)
    full = os.path.abspath(os.path.join(base_abs, path))

    # Ensure the full path is within the base
    if not full.startswith(base_abs + os.sep) and full != base_abs:
        return None

    return full


# ─── HTML Injection Prevention ───────────────────────────────────────────────

_DANGEROUS_TAGS = re.compile(
    r'<\s*(script|iframe|object|embed|link|meta|base|form)\b',
    re.IGNORECASE,
)

_DANGEROUS_ATTRS = re.compile(
    r'\b(on\w+)\s*=\s*["\']?[^"\'>\s]*',
    re.IGNORECASE,
)

def strip_dangerous_html(content: str) -> str:
    """Remove dangerous HTML tags and event handler attributes."""
    # Remove script tags and their content
    content = re.sub(r'<script[^>]*>.*?</script>', '', content, flags=re.IGNORECASE | re.DOTALL)
    # Remove other dangerous tags
    content = _DANGEROUS_TAGS.sub('<\\1', content)
    # Remove event handler attributes (on*)
    content = _DANGEROUS_ATTRS.sub('', content)
    # Remove javascript: URLs
    content = re.sub(r'(href|src)\s*=\s*["\']javascript:', '\\1=""', content, flags=re.IGNORECASE)
    return content


__all__ = [
    "generate_csp_nonce",
    "build_csp_header",
    "get_secure_headers",
    "render_secure_headers_html",
    "sanitize_html",
    "sanitize_attribute",
    "sanitize_js_string",
    "sanitize_url",
    "generate_csrf_token",
    "validate_csrf_token",
    "render_csrf_meta_tag",
    "safe_join_path",
    "strip_dangerous_html",
]
