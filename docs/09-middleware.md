# Middleware

## Overview

TW Framework supports two middleware styles, both defined in `middleware.tw`:

1. **Rule-based** — declarative rules for matching, headers, auth, rate limiting
2. **Function-based** — JavaScript functions executed before/after requests

## Middleware File Locations

Checked in order:
1. `middleware.tw` at project root
2. `[home]/middleware.tw`
3. `[home]/middleware/index.tw`

## Rule-Based Middleware

```tw
use {
    match "/dashboard/**"
    header "X-Content-Type-Options" "nosniff"
    header "X-Frame-Options" "DENY"
}

rule "api-rate-limit" {
    match "/api/**"
    rate_limit { requests 100, window 60 }
}

rule "auth-required" {
    match "/admin/**"
    auth { cookie "session" }
}

rule "cors" {
    match "/api/**"
    origin { allow "*" }
}
```

### Available Rules

| Rule | Description |
|------|-------------|
| `match` | Path pattern (`/dashboard/**`, `/api/**`) |
| `header` | Add response header |
| `methods` | Restrict HTTP methods |
| `path` | Path security: prefixes, contains, extensions, regex, deny_traversal, deny_null_bytes |
| `user_agent` | Allow/block user agents |
| `origin` | CORS: allow, require, allow_referer |
| `auth` | Cookie-based or JWT authentication |
| `rate_limit` | Token bucket: requests, window, identity, bucket_segments |
| `deny` | Deny access |
| `redirect` | Redirect to URL |
| `rewrite` | Rewrite URL |
| `response` | Custom response: status, json, html, text, content_type, headers, cookies |

## Function-Based Middleware

```tw
fn before(ctx) {
    if (ctx.path.startsWith("/admin") && !ctx.session) {
        return { redirect: "/login" }
    }
}

fn after(ctx) {
    ctx.response.headers["X-Response-Time"] = ctx.duration + "ms"
}
```

### Context Object (ctx)
- `ctx.path` — request path
- `ctx.method` — HTTP method
- `ctx.headers` — request headers
- `ctx.session` — session data (if auth middleware ran)
- `ctx.response` — response object (after phase only)
- `ctx.duration` — request duration in ms (after phase only)

### Return Values
- `return { redirect: "/url" }` — redirect
- `return { rewrite: "/url" }` — rewrite
- `return { status: 403, body: "Forbidden" }` — custom response
- `return null` or no return — continue to next middleware/handler
