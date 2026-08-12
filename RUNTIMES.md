# TW Framework — Multi-Runtime Architecture

## Overview

TW Framework supports 4 runtimes for API routes. Each `.twm` file can specify a runtime using the `runtime = "..."` directive at the top.

## Runtime Comparison

| Runtime | Directive | Engine | FS | Net | Crypto | Cold Start |
|---------|-----------|--------|-----|-----|--------|------------|
| Node.js | `runtime = "nodejs"` | Node.js worker | Yes | Yes | Yes | ~100ms |
| Edge V8 | `runtime = "edge"` | V8 Isolate | No | Yes | Yes | ~5ms |
| Python | `runtime = "python"` | Python in-process | Yes | Yes | Yes | ~0ms |
| WASM | `runtime = "wasm"` | wasmtime sandbox | No | No | Yes | ~10ms |

## Usage

```twm
runtime = "nodejs"

fn get(request) {
  return {
    status: 200,
    json: { message: "Hello from Node.js" }
  }
}
```

## Response Shapes

All runtimes support these response shapes:
- `{ status, json }` — JSON response
- `{ status, text }` — Plain text
- `{ status, html }` — HTML response
- `{ status, body, headers }` — Custom body
- `"string"` — Plain text (200 OK)
- `{ key: value }` — JSON (200 OK)

## Choosing a Runtime

- **Node.js**: Default. Use for npm packages, file system access, native modules.
- **Edge V8**: Use for fast, lightweight APIs. No fs access. Like Cloudflare Workers.
- **Python**: Use for Python libraries, ML inference, database access.
- **WASM**: Use for untrusted code execution in a sandbox.
