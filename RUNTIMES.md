# TW Framework — Multi-Runtime Guide (v0.9.0)

> **Write common application logic once and run it on the runtime that best fits the workload, while TW clearly detects and reports runtime-specific limitations.**

---

## Table of Contents

1. [Overview](#1-overview)
2. [The 4 Runtimes](#2-the-4-runtimes)
3. [Selecting a Runtime](#3-selecting-a-runtime)
4. [Common API Layer (`tw.*`)](#4-common-api-layer-tw)
5. [Runtime Capability System](#5-runtime-capability-system)
6. [Build-Time Validation](#6-build-time-validation)
7. [Runtime-Specific APIs](#7-runtime-specific-apis)
8. [Examples](#8-examples)
9. [Migration Guide](#9-migration-guide)
10. [Troubleshooting](#10-troubleshooting)
11. [Architecture Diagram](#11-architecture-diagram)

---

## 1. Overview

TW Framework v0.9.0 introduces a **multi-runtime architecture**. This means
you can choose which runtime your API route runs on — Node.js, Python,
Edge, or WASM — by adding a single line at the top of your `.twm` file.

TW does **NOT** reimplement any runtime. Instead, it wraps existing runtime
capabilities behind a **common abstraction layer** (`tw.storage`,
`tw.http`, `tw.db`, `tw.cache`, `tw.crypto`, `tw.env`). Your code uses
these common APIs, and TW automatically delegates to the correct
runtime-specific adapter.

### Why multiple runtimes?

| Need | Best Runtime | Why |
|------|-------------|-----|
| Full filesystem, npm packages, native modules | `nodejs` | Complete Node.js ecosystem |
| Python-heavy workloads, ML, data processing | `python` | Native Python, no Node.js needed |
| Fast, lightweight API (auth, redirects, JSON) | `edge` | Sub-millisecond cold start, restricted |
| Untrusted code, secure sandbox | `wasm` | Maximum isolation, restricted capabilities |

---

## 2. The 4 Runtimes

### Node.js (`nodejs`)

The default runtime. Full Node.js capabilities — filesystem, native npm
modules, subprocess, database drivers, everything Node.js offers.

**Capabilities:**
| Capability | Supported |
|------------|-----------|
| Filesystem | ✅ |
| Network | ✅ |
| Native modules (npm) | ✅ |
| Subprocess | ✅ |
| Database | ✅ |
| Crypto | ✅ |
| Cache | ✅ |
| Environment variables | ✅ |
| Persistent storage | ✅ |
| Timers | ✅ |
| Streaming | ✅ |

**Best for:** Routes that need npm packages, file I/O, database drivers,
or any Node.js-specific functionality.

**Execution:** Uses the persistent Node.js worker (added in v0.8.51)
for sub-millisecond request handling. Falls back to per-request
subprocess if the persistent worker is unavailable.

---

### Python (`python`)

Native Python runtime — runs **in-process** with the TW dev server.
No Node.js required! This is the recommended default for environments
without Node.js (Termux, restricted servers, etc.).

**Capabilities:**
| Capability | Supported |
|------------|-----------|
| Filesystem | ✅ |
| Network | ✅ |
| Native modules (pip) | ✅ |
| Subprocess | ✅ |
| Database | ✅ (sqlite3 built-in) |
| Crypto | ✅ (hashlib, hmac, secrets) |
| Cache | ✅ |
| Environment variables | ✅ |
| Persistent storage | ✅ |
| Timers | ✅ |
| Streaming | ✅ |

**Best for:** Python-heavy workloads, ML inference, data processing,
routes that use Python libraries (hashlib, sqlite3, etc.), and
environments where Node.js is not installed.

**Execution:** `.twm` handler body is translated to Python and evaluated
in-process with access to `tw`, `request`, `json`, `os`, `re`,
`hashlib`, `hmac`, `secrets`, `sqlite3`, and `urllib`.

---

### Edge (`edge`)

TW's own lightweight runtime — like Next.js Edge Runtime. Runs
in-process with sub-millisecond cold start. **Limited capabilities**:
no filesystem, no subprocess, no native modules.

**Capabilities:**
| Capability | Supported |
|------------|-----------|
| Filesystem | ❌ |
| Network | ✅ |
| Native modules | ❌ |
| Subprocess | ❌ |
| Database | ❌ |
| Crypto | ✅ |
| Cache | ✅ (in-memory) |
| Environment variables | ✅ (limited) |
| Persistent storage | ✅ (in-memory KV) |
| Timers | ❌ |
| Streaming | ❌ |

**Best for:** Auth checks, redirects, header injection, JSON API
responses, A/B testing, rate limiting, lightweight API proxies.

**Execution:** Same in-process Python evaluation as `python` runtime,
but with restricted capabilities. The Edge storage adapter uses an
in-memory KV store instead of the filesystem.

---

### WASM (`wasm`)

WebAssembly runtime — maximum security sandbox. All capabilities depend
on host permissions (like Deno's permission system). By default,
nothing is allowed unless explicitly granted.

**Capabilities:**
| Capability | Supported |
|------------|-----------|
| Filesystem | ✅ (sandboxed only) |
| Network | ❌ (disabled by default) |
| Native modules | ❌ (never) |
| Subprocess | ❌ (never) |
| Database | ❌ (disabled by default) |
| Crypto | ✅ (host-provided) |
| Cache | ✅ (in-memory) |
| Environment variables | ✅ (granted only) |
| Persistent storage | ✅ (sandbox) |
| Timers | ❌ |
| Streaming | ❌ |

**Best for:** Running untrusted code, processing user-uploaded scripts,
secure computation, plugin systems.

**Execution:** Falls back to restricted Python execution if `wasmtime`
is not installed. Filesystem access is limited to a sandboxed directory
(`.tw/wasm_sandbox/`).

---

## 3. Selecting a Runtime

Add a `runtime = "..."` directive at the **top** of any `.twm` API
route file:

```twm
runtime = "edge"

fn get(request) {
    return {
        "message": "Hello from Edge Runtime!"
    }
}
```

### Available values

| Value | Runtime |
|-------|---------|
| `"nodejs"` or `"node"` | Node.js (default) |
| `"python"` | Python (in-process) |
| `"edge"` | Edge (restricted, fast) |
| `"wasm"` | WASM (sandboxed) |

### Default behavior

If you don't specify a `runtime` directive, the route defaults to
`nodejs`. This means **all existing `.twm` routes continue to work
exactly as before** — v0.9.0 is fully backward compatible.

### Per-route vs per-project

Runtime selection is **per-route**. You can mix runtimes in the same
project:

```
app/api/users/route.twm     → runtime = "nodejs"    (needs npm packages)
app/api/search/route.twm    → runtime = "edge"      (fast, lightweight)
app/api/ml/route.twm        → runtime = "python"    (ML inference)
app/api/worker/route.twm    → runtime = "wasm"      (untrusted code)
```

---

## 4. Common API Layer (`tw.*`)

TW provides a set of common APIs that work across all runtimes. Each
runtime's adapter maps these to its own underlying implementation.

### tw.storage — File/Storage Operations

```twm
// Read a file
data = tw.storage.read("config.json")

// Write a file
tw.storage.write("output.txt", "Hello World")

// Delete a file
tw.storage.delete("temp/cache.tmp")

// Check if file exists
exists = tw.storage.exists("data/users.json")

// List files in a directory
files = tw.storage.list("./data", "*.json")
```

**Runtime mappings:**
| Runtime | Implementation |
|---------|---------------|
| Node.js | Node.js `fs` module |
| Python | Python `open()` / `os` module |
| Edge | In-memory KV store (no real filesystem) |
| WASM | Sandboxed directory only |

---

### tw.http — HTTP Client

```twm
// Fetch a URL
response = tw.http.fetch("https://api.example.com/users", {
    "method": "GET",
    "headers": {
        "Authorization": "Bearer token123"
    }
})

// Convenience methods
get_resp = tw.http.get("https://api.example.com/users")
post_resp = tw.http.post("https://api.example.com/users", {
    "name": "User"
})
put_resp = tw.http.put("https://api.example.com/users/1", {
    "name": "Updated"
})
delete_resp = tw.http.delete("https://api.example.com/users/1")
```

**Response format:**
```json
{
    "ok": true,
    "status": 200,
    "statusText": "OK",
    "url": "https://api.example.com/users",
    "headers": {"Content-Type": "application/json"},
    "text": "{\"users\": []}",
    "data": {"users": []}
}
```

**Runtime mappings:**
| Runtime | Implementation |
|---------|---------------|
| Node.js | Node.js `fetch` / `http` module |
| Python | Python `urllib.request` |
| Edge | Python `urllib.request` (restricted to HTTP) |
| WASM | ❌ Not supported (disabled by default) |

---

### tw.db — Database Operations

```twm
// Query
rows = tw.db.query("SELECT * FROM users WHERE active = ?", [true])

// Query one row
user = tw.db.query_one("SELECT * FROM users WHERE id = ?", [userId])

// Execute (INSERT/UPDATE/DELETE)
affected = tw.db.execute("UPDATE users SET last_login = ?", [now])

// Transaction
result = tw.db.transaction(function(db) {
    db.execute("INSERT INTO logs (message) VALUES (?)", ["User logged in"])
    db.execute("UPDATE users SET login_count = login_count + 1 WHERE id = ?", [userId])
})
```

**Runtime mappings:**
| Runtime | Implementation |
|---------|---------------|
| Node.js | Node database driver (pg, mysql2, etc.) |
| Python | Python `sqlite3` (built-in) or DB driver |
| Edge | ❌ Not supported (use HTTP-based DB API) |
| WASM | ❌ Not supported (disabled by default) |

> **Note:** For Python runtime, the default database is `sqlite3` with
> `:memory:` mode. Set the `TW_DB_PATH` environment variable to use a
> file-based database: `TW_DB_PATH=/data/app.db`

---

### tw.cache — Caching

```twm
// Get from cache
user = tw.cache.get("user:123", null)

// Set in cache (TTL in seconds, 0 = no expiry)
tw.cache.set("user:123", userData, 3600)

// Delete from cache
tw.cache.delete("user:123")

// Check if key exists
hasUser = tw.cache.has("user:123")

// Clear all cache
tw.cache.clear()
```

**Runtime mappings:**
| Runtime | Implementation |
|---------|---------------|
| Node.js | In-memory / Redis (configurable) |
| Python | In-memory / Redis (configurable) |
| Edge | In-memory (session-scoped) |
| WASM | In-memory (session-scoped) |

---

### tw.crypto — Cryptography

```twm
// Hash
hash = tw.crypto.hash("sha256", "hello world")
// → "b94d27b9934d3e08a52e52d7da7dabfac484efe37a5380ee9088f7ace2efcde9"

// HMAC
sig = tw.crypto.hmac("sha256", "secret-key", "message")

// Random hex string
token = tw.crypto.random(32)

// Random bytes
bytes = tw.crypto.random_bytes(32)

// UUID
id = tw.crypto.uuid()
// → "550e8400-e29b-41d4-a716-446655440000"
```

**Runtime mappings:**
| Runtime | Implementation |
|---------|---------------|
| Node.js | Node.js `crypto` module |
| Python | Python `hashlib`, `hmac`, `secrets` |
| Edge | Python `hashlib` (same as Python) |
| WASM | Host-provided (Python `hashlib`) |

---

### tw.env — Environment Variables

```twm
// Get an environment variable
dbUrl = tw.env.get("DATABASE_URL", "sqlite://default.db")

// Get as integer
port = tw.env.get_int("PORT", 3000)

// Get as boolean
debug = tw.env.get_bool("DEBUG", false)

// Check if exists
hasSecret = tw.env.has("API_SECRET")

// Get all environment variables
allVars = tw.env.all()
```

**Runtime mappings:**
| Runtime | Implementation |
|---------|---------------|
| Node.js | `process.env` |
| Python | `os.environ` |
| Edge | Limited (only `TW_*`, `PUBLIC_*`, `EDGE_*` prefixed vars) |
| WASM | Only explicitly granted variables |

---

### tw.runtime — Runtime Introspection

```twm
// Get current runtime name
name = tw.runtime.name()
// → "edge"

// Get runtime version
version = tw.runtime.version()
// → "tw-edge/3.12"

// Get all capabilities
caps = tw.runtime.capabilities()
// → {"filesystem": false, "network": true, ...}

// Check if a capability is supported
canAccessFs = tw.runtime.supports("filesystem")
// → false

// Get full runtime info
info = tw.runtime.info()
// → {"runtime": "edge", "version": "...", "capabilities": {...}}
```

---

## 5. Runtime Capability System

Each runtime declares which capabilities it supports. This information
is used by the build-time validator to catch incompatible API usage
before deployment.

### Capability Reference

| Capability | Description |
|-----------|-------------|
| `filesystem` | Read/write files on disk |
| `network` | Make HTTP requests, open sockets |
| `native_modules` | Use npm packages (Node) or pip packages (Python) |
| `subprocess` | Spawn child processes |
| `database` | Direct database connections (not HTTP-based) |
| `crypto` | Hashing, HMAC, random, encryption |
| `cache` | In-memory or external caching |
| `env_vars` | Access environment variables |
| `persistent_storage` | Data persists across requests |
| `timers` | setTimeout, setInterval, scheduling |
| `streaming` | Streaming responses (SSE, chunked transfer) |

### Capability Matrix

| Capability | nodejs | python | edge | wasm |
|-----------|--------|--------|------|------|
| filesystem | ✅ | ✅ | ❌ | ✅ (sandbox) |
| network | ✅ | ✅ | ✅ | ❌ |
| native_modules | ✅ | ✅ | ❌ | ❌ |
| subprocess | ✅ | ✅ | ❌ | ❌ |
| database | ✅ | ✅ | ❌ | ❌ |
| crypto | ✅ | ✅ | ✅ | ✅ |
| cache | ✅ | ✅ | ✅ | ✅ |
| env_vars | ✅ | ✅ | ✅ (limited) | ✅ (granted) |
| persistent_storage | ✅ | ✅ | ✅ (KV) | ✅ (sandbox) |
| timers | ✅ | ✅ | ❌ | ❌ |
| streaming | ✅ | ✅ | ❌ | ❌ |

### Checking capabilities at runtime

```twm
runtime = "edge"

fn get(request) {
    if (tw.runtime.supports("filesystem")) {
        data = tw.storage.read("config.json")
        return { "config": data }
    } else {
        return {
            "error": "Filesystem not available on Edge runtime",
            "runtime": tw.runtime.name()
        }
    }
}
```

---

## 6. Build-Time Validation

TW validates your `.twm` routes at **build time** — not at runtime. This
means you'll catch runtime-incompatible API usage before deploying.

### How it works

```
.twm file
    ↓
TW Build / Compiler
    ↓
Parse `runtime = "..."` directive
    ↓
Scan source for API usage (fs.readFile, child_process, etc.)
    ↓
Check: does the selected runtime support the required capability?
    ↓
   YES → Build continues ✅
   NO  → Build-time error ❌ (with helpful message)
```

### Example error

If a route configured for Edge Runtime uses `fs.readFile()`:

```
⚠️  Runtime validation: app/api/data/route.twm
    This route is configured for Edge Runtime,
    but `fs.readFile` requires filesystem capability
    (File system access (read/write files)).

    File: app/api/data/route.twm
    Line: 12

    Possible solutions:
      1. Change runtime to nodejs: add `runtime = "nodejs"` at top of route file
      2. Change runtime to python: add `runtime = "python"` at top of route file
      3. Use tw.storage.read() / tw.storage.write()
      4. Move filesystem logic to a separate route with `runtime = "nodejs"`
```

### APIs detected by the validator

The validator scans for these Node.js/Python-specific APIs and maps
them to required capabilities:

| API | Required Capability |
|-----|-------------------|
| `fs.readFile`, `fs.writeFile`, `fs.unlink`, `fs.readdir` | filesystem |
| `open(`, `path.join`, `os.path.join` | filesystem |
| `child_process`, `exec(`, `spawn(`, `execSync` | subprocess |
| `subprocess.run`, `subprocess.Popen`, `os.system` | subprocess |
| `require(`, `import ` | native_modules |
| `net.Socket`, `net.Server`, `dns.resolve` | network |
| `pg.Client`, `mongoose.connect`, `mysql.createConnection` | database |
| `redis.createClient`, `sqlite3.Database` | database |
| `createReadStream`, `createWriteStream`, `Transform` | streaming |

> **Tip:** Using `tw.*` common APIs instead of raw runtime-specific APIs
> will never trigger a validation error, because `tw.*` APIs adapt to
> whatever runtime is active.

---

## 7. Runtime-Specific APIs

Advanced users can access runtime-specific functionality directly:

```twm
runtime = "python"

fn get(request) {
    // Common API (portable across runtimes)
    hash = tw.crypto.hash("sha256", "hello")

    // Python-specific (only available on Python runtime)
    py_hash = hashlib.sha256("hello".encode()).hexdigest()

    return {
        "common_hash": hash,
        "python_hash": py_hash
    }
}
```

> **Warning:** Runtime-specific APIs are NOT portable. If you use
> `hashlib` directly, your route will only work on the `python` runtime.
> Use `tw.crypto.hash()` instead for cross-runtime compatibility.

---

## 8. Examples

### Example 1: Edge Runtime — Auth Check

```twm
runtime = "edge"

fn get(request) {
    token = request.headers["Authorization"]

    if (!token) {
        return {
            "status": 401,
            "body": {"error": "Unauthorized"}
        }
    }

    // Verify token using tw.crypto (works on Edge)
    expected = tw.crypto.hmac("sha256", "secret", token)

    return {
        "status": 200,
        "body": {
            "authenticated": true,
            "token_hash": expected
        }
    }
}
```

### Example 2: Python Runtime — Database Query

```twm
runtime = "python"

fn get(request) {
    // Database query (uses sqlite3 on Python runtime)
    users = tw.db.query("SELECT id, name, email FROM users")

    return {
        "users": users,
        "count": users.length
    }
}
```

### Example 3: Node.js Runtime — File Processing

```twm
runtime = "nodejs"

fn post(request) {
    // Read uploaded file
    data = tw.storage.read("uploads/data.csv")

    // Process and write result
    tw.storage.write("output/processed.json", data)

    return {
        "status": 200,
        "body": {"message": "File processed"}
    }
}
```

### Example 4: WASM Runtime — Secure Computation

```twm
runtime = "wasm"

fn post(request) {
    // Only sandboxed storage is available
    data = tw.storage.read("input.txt")

    // Process data securely
    hash = tw.crypto.hash("sha256", data)

    // Write result to sandbox
    tw.storage.write("output.hash", hash)

    return {
        "hash": hash
    }
}
```

### Example 5: Mixed Runtimes in One Project

```
app/
  api/
    auth/route.twm        → runtime = "edge"     (fast auth check)
    users/route.twm       → runtime = "nodejs"   (npm packages)
    ml-predict/route.twm  → runtime = "python"   (ML inference)
    sandbox/route.twm     → runtime = "wasm"     (untrusted code)
```

### Example 6: Using tw.runtime to Adapt

```twm
runtime = "edge"

fn get(request) {
    // Adapt behavior based on runtime capabilities
    if (tw.runtime.supports("filesystem")) {
        config = tw.storage.read("config.json")
        return { "config": config }
    } else {
        // Edge runtime: use cache instead of filesystem
        config = tw.cache.get("app_config", null)
        if (config == null) {
            // Fetch from API
            resp = tw.http.get("https://config-server.example.com/config")
            tw.cache.set("app_config", resp.data, 300)
            return { "config": resp.data }
        }
        return { "config": config }
    }
}
```

---

## 9. Migration Guide

### From v0.8.x to v0.9.0

**No changes required.** All existing `.twm` routes default to `nodejs`
runtime, which is exactly how they worked in v0.8.x.

### Adopting new runtimes

1. Identify routes that are lightweight (auth, redirects, JSON responses)
2. Add `runtime = "edge"` at the top of those `.twm` files
3. Run `tw build` — the validator will tell you if any route uses
   incompatible APIs
4. Replace raw `fs`/`child_process` calls with `tw.storage`/`tw.*` common
   APIs where possible
5. For Python-heavy routes, add `runtime = "python"`

### Replacing Node.js-specific APIs with common APIs

| Node.js API | TW Common API |
|-------------|--------------|
| `fs.readFile("path")` | `tw.storage.read("path")` |
| `fs.writeFile("path", data)` | `tw.storage.write("path", data)` |
| `fs.unlinkSync("path")` | `tw.storage.delete("path")` |
| `fs.existsSync("path")` | `tw.storage.exists("path")` |
| `fetch("url")` | `tw.http.fetch("url")` |
| `crypto.createHash("sha256")` | `tw.crypto.hash("sha256", data)` |
| `process.env.X` | `tw.env.get("X")` |
| `crypto.randomBytes(32)` | `tw.crypto.random_bytes(32)` |

---

## 10. Troubleshooting

### "Unknown runtime" error

Make sure you're using one of the supported values:
`"nodejs"`, `"node"`, `"python"`, `"edge"`, `"wasm"`.

```twm
// Wrong
runtime = "node.js"
runtime = "py"

// Correct
runtime = "nodejs"
runtime = "python"
```

### Build-time validation warning

If you see a warning like:
```
This route is configured for Edge Runtime,
but `fs.readFile` requires filesystem capability.
```

**Solutions:**
1. Change the runtime to `nodejs` or `python`
2. Replace `fs.readFile()` with `tw.storage.read()`
3. Move the filesystem logic to a separate route with `runtime = "nodejs"`

### Edge runtime: "PermissionError: Edge runtime does not support filesystem access"

The Edge runtime uses an in-memory KV store, not a real filesystem.
Use `tw.storage.write()` to store data in KV first, then `tw.storage.read()`
to retrieve it. Or switch to `python`/`nodejs` runtime for file access.

### WASM runtime: "cannot read/write outside sandbox"

The WASM runtime only allows access to a sandboxed directory
(`.tw/wasm_sandbox/`). All file paths are resolved relative to this
directory. You cannot access files outside it.

### Python runtime: "NameError: name 'X' is not defined"

The Python runtime provides these names in the execution namespace:
`tw`, `request`, `json`, `os`, `re`, `hashlib`, `hmac`, `secrets`,
`sqlite3`, `urllib`. If you need additional Python modules, use
`__import__("module_name")` inside your handler.

### Checking available runtimes

Run `tw info` in your project to see which runtimes are available on
your system and which routes use which runtime:

```
Available Runtimes:
  - nodejs (Node.js v18.17.0)
  - python (Python 3.12.0)
  - edge (tw-edge/3.12)
  - wasm (wasm-host/python)

Route Runtimes:
  /api/auth     → edge
  /api/users    → nodejs
  /api/ml       → python
  /api/worker   → wasm
```

---

## 11. Architecture Diagram

```
                         TW Framework
                              │
                       TW Runtime Core
                      (tw_runtime/base.py)
                              │
                  Runtime Abstraction Layer
                 (tw_runtime/abstractions.py)
                              │
       ┌──────────────────────┼──────────────────────┐
       ↓                      ↓                      ↓
  tw.storage               tw.http               tw.crypto
  tw.db                    tw.cache               tw.env
       │                      │                      │
       └──────────────────────┼──────────────────────┘
                              ↓
                       Runtime Adapters
                   (tw_runtime/adapters/)
                              │
       ┌────────────┬─────────┼─────────┬────────────┐
       ↓            ↓         ↓         ↓
     Node         Python     Edge      WASM
  (node_adapter) (python_   (edge_    (wasm_
                  adapter)   adapter)   adapter)
       │            │         │         │
       ↓            ↓         ↓         ↓
   Node.js       Python     In-proc   Sandbox
   (npm/fs)    (os/hashlib)  (KV)    (.tw/wasm/)
```

### Build-time validation flow

```
.twm file
    ↓
Parse `runtime = "..."` directive
    ↓
Scan source for API usage
    ↓
Map API → required capability
    ↓
Check: runtime.supports(capability)?
    ↓
   YES → Build ✅
   NO  → Error with file, line, solutions ❌
```

### Request dispatch flow

```
HTTP Request
    ↓
resolve_api_route(path)
    ↓
execute_api_route(route)
    ↓
_parse_runtime_directive(handler_path)
    ↓
  ┌─────────────────────────────┐
  │ runtime == "nodejs"?        │
  │   YES → execute_twm_api_    │
  │         handler() (Node.js  │
  │         persistent worker)  │
  │                             │
  │ runtime == "python"/"edge"/ │
  │ "wasm"?                     │
  │   YES → _execute_with_      │
  │         runtime()           │
  │         → _execute_twm_     │
  │           in_python()       │
  │         (in-process eval)   │
  └─────────────────────────────┘
    ↓
HTTP Response
```

---

## Quick Reference Card

```
┌──────────────────────────────────────────────────────────────────┐
│                    TW Multi-Runtime v0.9.0                      │
├──────────┬──────────┬──────────┬──────────┬─────────────────────┤
│ Runtime  │ nodejs   │ python   │ edge     │ wasm                │
├──────────┼──────────┼──────────┼──────────┼─────────────────────┤
│ Speed    │ Fast     │ Fast     │ Fastest  │ Medium              │
│ fs       │ ✅       │ ✅       │ ❌       │ ✅ (sandbox)        │
│ network  │ ✅       │ ✅       │ ✅       │ ❌                  │
│ npm/pip  │ ✅       │ ✅       │ ❌       │ ❌                  │
│ subprocess│ ✅      │ ✅       │ ❌       │ ❌                  │
│ database │ ✅       │ ✅       │ ❌       │ ❌                  │
│ crypto   │ ✅       │ ✅       │ ✅       │ ✅                  │
│ Best for │ Full API │ Python   │ Auth,    │ Untrusted code      │
│          │ routes   │ workloads│ JSON API │                     │
└──────────┴──────────┴──────────┴──────────┴─────────────────────┘

Directive:   runtime = "edge"     ← add at top of .twm file
Common API:  tw.storage.read()    ← works on all runtimes
Check:       tw.runtime.supports("filesystem")
Validate:    tw build              ← catches incompatible APIs at build time
Info:        tw info               ← shows available runtimes & route assignments
```

---

*TW Framework v0.9.0 — Multi-Runtime Architecture*
*TW Framework v0.9.06*
