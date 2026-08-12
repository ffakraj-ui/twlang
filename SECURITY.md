# TW Framework — Security

## Security Features

### Content Security Policy (CSP)
- Automatic CSP header generation with nonce
- Configurable directives via `tw.config.json`

### CSRF Protection
- Token generation and verification for server actions
- Double-submit cookie pattern

### Input Sanitization
- HTML escaping
- URL sanitization
- Attribute value sanitization
- SQL injection prevention

### Password Security
- scrypt + HMAC password hashing
- Password strength checking
- Secure session management

### Secure Headers
- HSTS (Strict-Transport-Security)
- X-Frame-Options: SAMEORIGIN
- X-Content-Type-Options: nosniff
- Referrer-Policy
- Permissions-Policy

### Content Integrity
- SRI (Subresource Integrity) hashing
- Integrity attributes on script/link tags

### Thread Safety
- Thread-safe Edge V8 storage with locking
- Thread-safe SSR cache
