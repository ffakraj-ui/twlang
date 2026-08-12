# Security

## Environment Variables

All env vars are server-only by default. Only allow-listed vars reach page HTML:

```
// tw.config
env { public "API_URL" }
```

This prevents accidental leakage of secrets like `DATABASE_URL` or `JWT_SECRET` into generated HTML.

## Path Traversal Protection

Middleware path rules block directory traversal attacks:

```tw
rule "secure-paths" {
    match "/api/**"
    path {
        deny_traversal true
        deny_null_bytes true
    }
}
```

- `deny_traversal` — blocks `../` in URLs
- `deny_null_bytes` — blocks null bytes in paths

## CSRF Protection

TW generates and verifies CSRF tokens:

```tw
form {
    on:submit "submitForm()"
    input { type "hidden", name "_csrf", value "{csrf_token}" }
}
```

CSRF tokens are signed and time-limited (2-hour expiry by default).

## Security Headers

Set via middleware or `tw.config`:

```tw
rule "security-headers" {
    match "/**"
    header "X-Content-Type-Options" "nosniff"
    header "X-Frame-Options" "DENY"
    header "X-XSS-Protection" "1; mode=block"
    header "Referrer-Policy" "strict-origin-when-cross-origin"
}
```

Or in `tw.config`:

```
headers {
  rule {
    source "/**"
    set "X-Content-Type-Options" "nosniff"
    set "X-Frame-Options" "DENY"
  }
}
```

## Cookie Security

Cookies set by API routes support:

| Option | Description |
|---|---|
| `httpOnly` | Prevents JS access to cookie |
| `secure` | Only sent over HTTPS |
| `maxAge` | Expiry in seconds |
| `sameSite` | `strict`, `lax`, or `none` |

```js
return {
    status: 200,
    cookies: [
        { name: "session", value: token, httpOnly: true, secure: true, maxAge: 3600 }
    ]
};
```

## CORS

```tw
rule "cors" {
    match "/api/**"
    origin {
        allow ["https://mysite.com"]
        allow_referer true
    }
    header "Access-Control-Allow-Origin" "https://mysite.com"
    header "Access-Control-Allow-Methods" "GET, POST, PUT, DELETE"
}
```

## Rate Limiting

Protect against brute force:

```tw
rule "login-protection" {
    match "/api/auth/login"
    rate_limit { requests 5, window 60 }
}
```

## User Agent Blocking

```tw
rule "block-bots" {
    match "/**"
    user_agent {
        block ["bot", "crawler", "spider"]
        empty_is_blocked true
    }
}
```

## Origin/Referer Validation

```tw
rule "csrf-protection" {
    match "/api/**"
    origin {
        allow ["https://mysite.com"]
        require true
    }
}
```
