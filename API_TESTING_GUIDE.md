# TW Framework — API Testing Guide

## Creating API Routes

Create a `.twm` file in `app/api/<name>/route.twm`:

```twm
runtime = "nodejs"

fn get(request) {
  return {
    status: 200,
    json: { message: "Hello World" }
  }
}

fn post(request) {
  return {
    status: 201,
    json: { created: true }
  }
}
```

## Response Shapes

### JSON Response
```twm
fn get(request) {
  return {
    status: 200,
    json: { users: ["alice", "bob"] }
  }
}
```

### Text Response
```twm
fn get(request) {
  return {
    status: 200,
    text: "Plain text response"
  }
}
```

### HTML Response
```twm
fn get(request) {
  return {
    status: 200,
    html: "<h1>Hello</h1>"
  }
}
```

### Custom Headers
```twm
fn get(request) {
  return {
    status: 200,
    json: { ok: true },
    headers: { "X-Custom-Header": "value" }
  }
}
```

### Redirect
```twm
fn get(request) {
  return {
    status: 302,
    headers: { "Location": "/login" }
  }
}
```

## Runtime Directives

| Directive | Engine | Best For |
|-----------|--------|----------|
| `runtime = "nodejs"` | Node.js worker | Full npm packages, fs access |
| `runtime = "edge"` | V8 Isolate | Fast, lightweight APIs |
| `runtime = "python"` | Python in-process | Python libraries, ML |
| `runtime = "wasm"` | wasmtime sandbox | Untrusted code |

## Request Object

The `request` object contains:

| Field | Type | Description |
|-------|------|-------------|
| `method` | string | HTTP method (GET, POST, etc.) |
| `path` | string | URL path |
| `query` | object | Query parameters |
| `body` | any | Request body |
| `headers` | object | Request headers |
| `cookies` | object | Request cookies |
| `env` | object | Environment variables |
| `project_root` | string | Project root path |

## Testing API Routes

### Start the server
```bash
tw serve --port 8000
```

### Test with curl
```bash
curl http://127.0.0.1:8000/api/contact
curl -X POST http://127.0.0.1:8000/api/contact -d '{"name":"test"}' -H "Content-Type: application/json"
```

### Common Errors

| Error | Cause | Fix |
|-------|-------|-----|
| `Handler load failed` | Syntax error in .twm | Check function syntax |
| `Method GET not allowed` | Missing `fn get` | Add the handler function |
| `Node.js not detected` | Node.js not installed | Install Node.js v18+ |
| `result is not defined` | Invalid response shape | Use `{ status, json }` format |
| 501 error | Node.js missing | Install Node.js or use `runtime = "python"` |
