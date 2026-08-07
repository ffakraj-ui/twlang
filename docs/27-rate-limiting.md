# Rate Limiting

TW Framework has built-in rate limiting via middleware using a token bucket algorithm.

## Basic Rate Limiting

```tw
// [home]/middleware.tw

rule "api-rate-limit" {
    match "/api/**"
    rate_limit {
        requests 100
        window 60
        identity "ip"
    }
}
```

This allows 100 requests per 60 seconds per IP address on `/api/*` routes.

## Configuration

| Field | Type | Default | Description |
|---|---|---|---|
| `requests` | number | required | Max requests in the window |
| `window` | number | required | Time window in seconds |
| `identity` | string | `"ip"` | How to identify clients |
| `bucket_segments` | number | 2 | Bucket segmentation for smoother limits |

## Identity Options

| Value | Description |
|---|---|
| `ip` | Client IP address |
| `user` | Authenticated user ID (requires auth) |
| `ip:user` | Combination of IP and user |

## Examples

### API Rate Limiting

```tw
rule "api-limit" {
    match "/api/**"
    rate_limit {
        requests 100
        window 60
    }
}
```

### Stricter Limit for Login

```tw
rule "login-limit" {
    match "/api/auth/login"
    rate_limit {
        requests 5
        window 60
    }
}
```

### Per-User Limiting

```tw
rule "user-api-limit" {
    match "/api/**"
    rate_limit {
        requests 1000
        window 3600
        identity "user"
    }
}
```

## How Token Bucket Works

The token bucket algorithm:
1. Each client gets a bucket with `requests` capacity
2. Tokens are refilled at `requests / window` per second
3. Each request consumes one token
4. If no tokens available → 429 Too Many Requests

### Bucket Segments

`bucket_segments` splits the window into segments for smoother rate limiting:

- `1` — strict: all tokens refreshed at once after window expires
- `2` (default) — moderate: tokens refresh in two phases
- `4` — smooth: tokens refresh gradually

## Rate Limit Response

When rate limited, TW returns:

```
HTTP 429 Too Many Requests
Content-Type: application/json

{
    "error": "Rate limit exceeded",
    "retry_after": 45
}
```

## Custom Rate Limit Response

```tw
rule "api-limit" {
    match "/api/**"
    rate_limit { requests 100, window 60 }
    response {
        status 429
        json { error "Slow down!", retry_after 60 }
    }
}
```
