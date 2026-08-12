# Environment Variables

## Configuration Variables

| Variable | Default | Description |
|----------|---------|-------------|
| `TW_REDIS_URL` | — | Redis URL for distributed SSR cache |
| `TW_MAX_FETCH_PASSES` | 10 | Max HTTP fetch calls per Edge V8 request (1-50) |
| `TW_SSR_CACHE_MAX` | 512 | Max SSR cache entries |
| `TW_AST_CACHE_MAX` | 128 | Max AST cache entries |
| `TW_AST_CACHE_TTL` | 300 | AST cache TTL in seconds |
| `TW_MAX_BODY_SIZE` | 10MB | Max request body size |
| `NODE_ENV` | — | Node.js environment (exposed to Edge runtime) |

## Env Var Security

Environment variables are filtered for Edge runtime — only `TW_`, `PUBLIC_`, and `EDGE_` prefixed variables (plus `NODE_ENV`) are exposed to the JavaScript sandbox.

### In Python runtime:
```python
tw.env.get("TW_API_KEY")  # Returns value if TW_ prefixed
tw.env.get("SECRET_KEY")  # Returns default — not TW_ prefixed
tw.env.all()               # Returns only safe vars
```

### In .env file:
```
SITE_NAME=My Site
TW_API_KEY=secret123
PUBLIC_ANALYTICS_ID=UA-123456
DATABASE_URL=postgresql://...  # NOT exposed to Edge runtime
```

## Using Env Vars in Pages

```tw
page {
    title "Dashboard"
    render server
}

body {
    h1 "Welcome to {{site_name}}"
    p "API Key: {{tw_api_key}}"
}
```

Env vars are available in server-rendered pages via `request.env` in middleware and API routes.
