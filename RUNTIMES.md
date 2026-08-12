# TW Framework — Multi-Runtime Architecture

TW Framework supports 5 runtimes for API route handlers (`.twm` files). Add a `runtime = "..."` directive at the top of any `.twm` file.

## Runtime Matrix

| Runtime | Directive | Engine | Best For | Filesystem | Network | Crypto | Cache |
|---------|-----------|--------|----------|-----------|---------|--------|-------|
| **Node.js** | `runtime = "nodejs"` | Persistent Node.js worker | Full npm packages, fs, native modules | Y | Y | Y | Y |
| **Edge V8** | `runtime = "edge"` | V8 Isolate (py_mini_racer) | Fast, lightweight APIs — real JS sandbox | N | Y | Y | Y |
| **Python** | `runtime = "python"` | Python in-process | Python libraries, ML, no Node.js needed | Y | Y | Y | Y |
| **WASM** | `runtime = "wasm"` | wasmtime sandbox | Untrusted code, maximum isolation | N | N | Y | Y |
| **Edge (legacy)** | `runtime = "edge-py"` | Python in-process | Fallback if V8 not installed | N | Y | Y | Y |

Default is `nodejs` — all existing routes work as before (backward compatible).

## Installation

```bash
pip install tw-framework                  # Core — zero dependencies
pip install tw-framework[edge-v8]          # V8 runtime (py_mini_racer)
pip install tw-framework[wasm]            # WASM runtime (wasmtime)
pip install tw-framework[redis]           # Redis SSR cache
pip install tw-framework[all]             # All optional features
```

## Common API Layer (`tw.*`)

Write once, run on any runtime:

```javascript
// Storage (KV on Edge, fs on Node/Python)
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
tw.crypto.random(32)               // CSPRNG hex string
tw.crypto.uuid()                   // UUID v4
tw.crypto.encrypt("tw-secure", key, data)  // scrypt + HMAC-SHA256
tw.crypto.decrypt("tw-secure", key, data)

// Cache (with TTL)
tw.cache.set("key", value, 60)    // 60 second TTL
tw.cache.get("key", defaultVal)
tw.cache.delete("key")
tw.cache.has("key")
tw.cache.clear()

// Environment (filtered — only TW_, PUBLIC_, EDGE_ prefixes)
tw.env.get("TW_API_KEY")
tw.env.all()
tw.env.has("TW_API_KEY")

// Runtime info
tw.runtime.name()                  // "edge-v8"
tw.runtime.capabilities()          // {filesystem: false, network: true, ...}
tw.runtime.supports("network")     // true
```

## Edge V8 Runtime Details

The Edge V8 runtime uses `py_mini_racer` to create a real V8 JavaScript isolate — same engine that powers Google Chrome and Next.js Edge Runtime.

### Features:
- Real JavaScript execution (not a JS interpreter in Python)
- Multi-pass HTTP fetch (V8 is synchronous — throws `__YIELD_FETCH__`, Python catches, does HTTP, re-evals)
- Pure JS implementations of SHA-256, HMAC-SHA256, UUID
- Thread-safe KV storage (threading.Lock)
- scrypt-based authenticated encryption
- 30s execution timeout via daemon thread
- Configurable max fetch passes (`TW_MAX_FETCH_PASSES`, default 10, range 1-50)
- gc.collect() on context reload (prevents memory leaks)

### Limitations:
- No filesystem access (raises PermissionError)
- No subprocess
- No native Node.js modules
- No timers (setTimeout not available)
- No streaming
- Not persistent (in-memory only)

## Runtime Registration

Runtimes are registered via `register_runtimes()` in `tw_runtime/__init__.py`:
- Thread-safe via `_REGISTER_LOCK` with double-check pattern
- Idempotent (safe to call multiple times)
- Auto-called on import for backward compatibility

```python
from tw_framework.tw_runtime import get_runtime, list_runtimes

runtime = get_runtime("edge")
if runtime.supports("network"):
    runtime.http.fetch("https://api.com")
```

## Environment Variables

| Variable | Default | Description |
|----------|---------|-------------|
| `TW_MAX_FETCH_PASSES` | 10 | Max HTTP fetch calls per Edge V8 request (1-50) |
| `TW_REDIS_URL` | — | Redis URL for distributed SSR cache |
| `TW_SSR_CACHE_MAX` | 512 | Max SSR cache entries |
| `TW_AST_CACHE_MAX` | 128 | Max AST cache entries |
| `TW_AST_CACHE_TTL` | 300 | AST cache TTL in seconds |
| `TW_MAX_BODY_SIZE` | 10MB | Max request body size |
