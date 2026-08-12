# Security

## Overview

TW Framework includes built-in security features at the framework level — no external libraries required.

## Content Security Policy (CSP)

```python
from tw_framework.security import generate_csp_nonce, build_csp_header

nonce = generate_csp_nonce()
csp = build_csp_header(nonce, {
    "script-src": ["'self'", "'nonce-{}".format(nonce)],
    "style-src": ["'self'", "'unsafe-inline'"],
})
# → "default-src 'self'; script-src 'self' 'nonce-abc123'; ..."
```

CSP directives are deduplicated automatically. `upgrade-insecure-requests` is included by default.

## HTML Sanitization

```python
from tw_framework.security import sanitize_html, sanitize_url, sanitize_attribute

sanitize_html("<script>alert('xss')</script>")  # Escapes all tags
sanitize_url("javascript:alert(1)")               # Returns empty string
sanitize_attribute("href", "javascript:alert(1)")  # Returns ""
```

Double-escape prevention: if input is already escaped (`&`), it won't be double-escaped.

## CSRF Protection

```python
from tw_framework.security import generate_csrf_token, validate_csrf_token

token = generate_csrf_token()
# ... send token to client ...
is_valid = validate_csrf_token(received_token, token)
```

Uses constant-time comparison to prevent timing attacks.

## Server Security Headers

All responses from `tw serve` include:
- `X-Frame-Options: SAMEORIGIN`
- `X-Content-Type-Options: nosniff`

## Request Body Size Limit

Default: 10MB. Configurable via `TW_MAX_BODY_SIZE` environment variable.
Returns HTTP 413 on oversized requests.

## Edge V8 Sandbox Security

- Real V8 isolate — no filesystem, no subprocess, no native modules
- Environment variables filtered (only `TW_`, `PUBLIC_`, `EDGE_` prefixes)
- Request data double-JSON-encoded to prevent JS injection
- 30s execution timeout (returns HTTP 504 on timeout)
- Thread-safe KV storage (threading.Lock)
- Authenticated encryption (scrypt + HMAC-SHA256, not XOR)
- Max fetch passes limit (default 10, configurable 1-50)
- Error messages sanitized (internal paths removed)

## Middleware Security

### Auth
- Cookie-based authentication
- JWT authentication (via `jwt_secret` or `jwt_secret_env`)

### Rate Limiting
- Token bucket algorithm
- Configurable: requests, window, identity, bucket_segments

### Path Security
- `deny_traversal` — blocks `../` in paths
- `deny_null_bytes` — blocks null bytes
- `single_segment_max` — limits path depth
- `extensions` — restricts file types
- `regex` — custom path validation

### CORS
- `origin` rules: allow, require, allow_referer
