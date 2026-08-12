# API Routes

## Creating API Routes

API routes live in `[home]/api/*/route.tw` files and use the `.twm` format.

```twm
runtime = "nodejs"

fn get(request) {
    return {
        status: 200,
        body: { message: "Hello from API" }
    }
}

fn post(request) {
    const data = request.body
    return {
        status: 201,
        body: { created: true }
    }
}
```

## HTTP Methods

Each function name maps to an HTTP method:
- `fn get(request)` → GET
- `fn post(request)` → POST
- `fn put(request)` → PUT
- `fn patch(request)` → PATCH
- `fn delete(request)` → DELETE

## Runtime Selection

Add `runtime = "..."` at the top of the `.twm` file:

| Runtime | Directive | Engine |
|---------|-----------|--------|
| Node.js | `runtime = "nodejs"` | Persistent Node.js worker (default) |
| Edge V8 | `runtime = "edge"` | V8 isolate (py_mini_racer) |
| Python | `runtime = "python"` | Python in-process |
| WASM | `runtime = "wasm"` | wasmtime sandbox |
| Edge (legacy) | `runtime = "edge-py"` | Python in-process fallback |

## Common API (tw.*)

```javascript
// Storage
tw.storage.read("config.json")
tw.storage.write("output.txt", data)
tw.storage.delete(path)
tw.storage.exists(path)

// HTTP
tw.http.fetch(url, {method: "GET", headers: {}, timeout: 30})
tw.http.get(url, headers, timeout)
tw.http.post(url, body, headers, timeout)

// Crypto
tw.crypto.hash("sha256", data)
tw.crypto.hmac("sha256", key, message)
tw.crypto.random(32)
tw.crypto.uuid()

// Cache
tw.cache.set("key", value, 60)  // 60s TTL
tw.cache.get("key", defaultVal)
tw.cache.delete("key")

// Environment
tw.env.get("TW_API_KEY")
tw.env.all()
```

## Request Object

```javascript
fn post(request) {
    const method = request.method    // "POST"
    const path = request.path        // "/api/contact"
    const headers = request.headers  // {content-type: "..."}
    const body = request.body        // parsed JSON
    const query = request.query      // query params
    return { status: 200, body: {ok: true} }
}
```

## Response Format

```javascript
return {
    status: 200,
    content_type: "application/json",
    headers: {"X-Custom": "value"},
    cookies: {"session": "abc123"},
    body: { message: "Success" }
}
```
