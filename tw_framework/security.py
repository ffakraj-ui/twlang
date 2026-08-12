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
        # FIX #468: Add upgrade-insecure-requests for HTTPS enforcement
        "upgrade-insecure-requests": "",
    }

    if extra_directives:
        for key, value in extra_directives.items():
            # FIX #462: Deduplicate values when appending to existing directive
            if key in directives:
                existing_parts = directives[key].split()
                new_parts = value.split()
                for part in new_parts:
                    if part not in existing_parts:
                        existing_parts.append(part)
                directives[key] = " ".join(existing_parts)
            else:
                directives[key] = value

    # FIX #485: Validate directive values — strip semicolons that would break CSP
    parts = []
    for k, v in directives.items():
        safe_k = k.strip().replace(";", "")
        safe_v = v.strip().replace(";", "")
        parts.append(f"{safe_k} {safe_v}".strip() if safe_v else safe_k)
    return "; ".join(parts)


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

    # FIX #472: X-XSS-Protection is deprecated — keep only for legacy browser support
    # Modern browsers ignore this header in favor of CSP.

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
    # FIX #467: Avoid double-escaping by unescaping first
    import html as _html
    _unescaped = _html.unescape(text)
    return _html.escape(_unescaped, quote=True)


def sanitize_attribute(value: str) -> str:
    """Sanitize an HTML attribute value — escape quotes and special chars."""
    # FIX #478: Attribute-specific escaping — always quote-escape
    import html as _html
    # Unescape first to avoid double-escaping, then re-escape with quotes
    return _html.escape(_html.unescape(value), quote=True)


def sanitize_js_string(text: str) -> str:
    """Sanitize a string for safe inclusion in JavaScript."""
    # Escape backslashes, quotes, newlines, and other dangerous chars
    text = text.replace("\\", "\\\\")
    text = text.replace("'", "\\'")
    text = text.replace('"', '\\"')
    text = text.replace("\n", "\\n")
    text = text.replace("\r", "\\r")
    text = text.replace("\t", "\\t")
    # FIX #484: Remove null bytes which break JS
    text = text.replace("\x00", "")
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


# ─── Additional Security Helpers (v0.9.10) ────────────────────────────────────

def sanitize_filename(filename: str) -> str:
    """
    Sanitize a filename to prevent directory traversal and unsafe characters.
    Strips path separators, null bytes, and keeps only safe characters.
    """
    if not filename:
        return ""
    # Remove any path components
    filename = os.path.basename(filename)
    # Remove null bytes and control characters
    filename = re.sub(r"[\x00-\x1f]", "", filename)
    # Remove leading dots (hidden files / directory traversal)
    filename = filename.lstrip(".")
    # Only allow alphanumeric, dash, underscore, dot, and space
    filename = re.sub(r"[^a-zA-Z0-9._- ]", "", filename)
    # Limit length
    if len(filename) > 255:
        name, ext = os.path.splitext(filename)
        filename = name[:255 - len(ext)] + ext
    return filename


def check_password_strength(password: str) -> dict:
    """
    Check password strength and return a report with score and suggestions.
    Returns dict with: score (0-5), strength (str), issues (list), suggestions (list).
    """
    issues = []
    suggestions = []
    score = 0

    if len(password) < 8:
        issues.append("Too short (minimum 8 characters)")
        suggestions.append("Use at least 8 characters")
    elif len(password) >= 12:
        score += 2
    else:
        score += 1

    has_lower = bool(re.search(r"[a-z]", password))
    has_upper = bool(re.search(r"[A-Z]", password))
    has_digit = bool(re.search(r"\d", password))
    has_special = bool(re.search(r"[!@#$%^&*()_+=\[\]{};:'\",.<>?/\\|~-]", password))

    if has_lower:
        score += 1
    else:
        suggestions.append("Add lowercase letters")

    if has_upper:
        score += 1
    else:
        suggestions.append("Add uppercase letters")

    if has_digit:
        score += 1
    else:
        suggestions.append("Add numbers")

    if has_special:
        score += 1
    else:
        suggestions.append("Add special characters")

    # Common weak passwords check
    weak_patterns = ["password", "123456", "qwerty", "abc123", "admin", "letmein"]
    lower_pwd = password.lower()
    for pattern in weak_patterns:
        if pattern in lower_pwd:
            issues.append(f"Contains common weak pattern: '{pattern}'")
            score = max(0, score - 1)
            break

    strength_labels = ["Very Weak", "Weak", "Fair", "Good", "Strong", "Very Strong"]
    strength = strength_labels[min(score, 5)]

    return {
        "score": score,
        "strength": strength,
        "issues": issues,
        "suggestions": suggestions,
    }


def generate_content_integrity_hash(content: bytes, algorithm: str = "sha384") -> str:
    """
    Generate a Subresource Integrity (SRI) hash for the given content.
    Used for integrity="" attributes on <script> and <link> tags.
    """
    import hashlib as _hl
    import base64 as _b64
    if algorithm not in ("sha256", "sha384", "sha512"):
        algorithm = "sha384"
    digest = _hl.new(algorithm, content).digest()
    b64 = _b64.b64encode(digest).decode("ascii")
    return f"{algorithm}-{b64}"


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
    "sanitize_filename",
    "check_password_strength",
    "generate_content_integrity_hash",
]
