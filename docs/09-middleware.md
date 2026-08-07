# Middleware

Middleware is configured in `[home]/middleware.tw` using a rule-based system.

## Basic Structure

```tw
rule "protect-admin" {
    match "/admin/**"
    methods ["GET", "POST"]
    auth {
        cookie "session"
        redirect "/login"
    }
}

rule "api-rate-limit" {
    match "/api/**"
    rate_limit {
        requests 100
        window 60
        identity "ip"
    }
}
```

## Rule Properties

| Property | Description |
|---|---|
| `match` | URL pattern to match (glob: `**` for wildcards) |
| `methods` | HTTP methods to apply (empty = all) |
| `redirect` | Redirect to URL if rule matches |
| `rewrite` | Rewrite to different URL |
| `deny` | Deny request with status code |
| `header` | Set response header |
| `cookie` | Set response cookie |
| `response` | Custom response block |
| `auth` | Authentication check |
| `auth_rule` | Advanced auth (JWT) |
| `rate_limit` | Rate limiting |
| `origin` | CORS / origin checks |
| `user_agent` | User agent filtering |
| `path` | Path validation rules |

## Authentication

### Cookie-based

```tw
rule "require-login" {
    match "/dashboard/**"
    auth {
        cookie "session"
        redirect "/login"
    }
}
```

### JWT-based

```tw
rule "api-auth" {
    match "/api/admin/**"
    auth_rule {
        jwt_secret_env "JWT_SECRET"
        required true
        cookie "token"
    }
}
```

## Rate Limiting

```tw
rule "rate-limit-api" {
    match "/api/**"
    rate_limit {
        requests 100
        window 60
        identity "ip"
        bucket_segments 2
    }
}
```

| Field | Description |
|---|---|
| `requests` | Max requests in window |
| `window` | Time window in seconds |
| `identity` | `ip` (default) or custom |
| `bucket_segments` | Bucket segmentation (default: 2) |

## CORS / Origin

```tw
rule "cors" {
    match "/api/**"
    origin {
        allow ["https://mysite.com", "https://app.mysite.com"]
        allow_referer true
        require false
    }
}
```

## User Agent Filtering

```tw
rule "block-bots" {
    match "/**"
    user_agent {
        block ["bot", "crawler", "spider"]
        empty_is_blocked false
    }
}
```

## Path Validation

```tw
rule "secure-paths" {
    match "/api/**"
    path {
        deny_traversal true
        deny_null_bytes true
        prefixes ["/api/"]
        extensions [".json", ".twm"]
    }
}
```

## Custom Response

```tw
rule "maintenance" {
    match "/**"
    response {
        status 503
        html "<h1>Maintenance Mode</h1>"
    }
}
```

## Deny

```tw
rule "block-admin" {
    match "/admin/old/**"
    deny 403 "This section has been removed"
}
```

## Headers and Cookies

```tw
rule "security-headers" {
    match "/**"
    header "X-Content-Type-Options" "nosniff"
    header "X-Frame-Options" "DENY"
    cookie "session" "abc123"
}
```

## Multiple Rules

Rules are evaluated in order. First match wins.

```tw
rule "allow-public" {
    match "/public/**"
    // No auth needed
}

rule "protect-private" {
    match "/**"
    auth { cookie "session", redirect "/login" }
}
```
