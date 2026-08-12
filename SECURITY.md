# TW Framework — Security

## Security Features (security.py — 388 lines)

### Content Security Policy
- `generate_csp_nonce()` — cryptographically secure per-request nonce
- `build_csp_header(nonce, extra_directives)` — CSP header with directive dedup
- `upgrade-insecure-requests` directive included by default

### HTML/URL/Attribute Sanitization
- `sanitize_html(html)` — XSS prevention with double-escape protection
- `sanitize_js_string(js)` — JS string sanitization for safe embedding
- `sanitize_url(url)` — blocks `javascript:` and `data:` URL injection
- `sanitize_attribute(attr, value)` — href/src sanitization with double-escape prevention
- Null byte removal from all user inputs

### CSRF Protection
- `generate_csrf_token()` — CSRF token generation
- `validate_csrf_token(token, expected)` — constant-time comparison

### Server-Side Security
- Security headers on all responses: `X-Frame-Options: SAMEORIGIN`, `X-Content-Type-Options: nosniff`
- Request body size limit (default 10MB, configurable via `TW_MAX_BODY_SIZE`)
- Env var filtering for Edge runtime (only `TW_`, `PUBLIC_`, `EDGE_` prefixes exposed)
- V8 execution timeout (30s via daemon thread, returns HTTP 504)
- Authenticated encryption (scrypt + HMAC-SHA256, not XOR)
- Error message sanitization (internal paths removed)

### Edge V8 Sandbox
- Real V8 isolate — no filesystem, no subprocess, no native modules
- KV storage is thread-safe (threading.Lock)
- Environment variables filtered before injection
- Request data double-JSON-encoded to prevent JS injection
- Max fetch passes limit (default 10, configurable 1-50)

## Middleware Security

### Auth
- Cookie-based authentication
- JWT authentication (secret or env var via `jwt_secret`/`jwt_secret_env`)

### Rate Limiting
- Token bucket algorithm (`TokenBucketRateLimiter`)
- Configurable: requests, window, identity, bucket_segments
- Per-IP or custom identity

### Path Security
- `deny_traversal` — blocks path traversal (`../`)
- `deny_null_bytes` — blocks null bytes in paths
- `single_segment_max` — limits path segment count
- `extensions` — restrict allowed file extensions
- `regex` — custom path validation

### CORS
- `origin` rules: allow, require, allow_referer
- Configurable allowed origins

## Best Practices

1. Always use `render static` for public pages (zero JS = zero attack surface)
2. Use `render server` only when you need per-request data
3. Enable middleware rate limiting on API routes
4. Use CSP nonces for any inline scripts
5. Set `TW_MAX_BODY_SIZE` appropriately for your use case
6. Use `tw-secure` encryption (not `xor`) for sensitive data
7. Filter env vars — only expose what's needed via `TW_` prefix
