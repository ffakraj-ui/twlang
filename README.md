# TW Framework

A high-performance, HTML-first web framework with Virtual DOM, App Router, Zero-JS static sites, and **Multi-Runtime Architecture** (V8 Edge, Python, Node.js, WASM).

**v0.9.15** — Plugin System, HMR, Image Optimization, Prefetching, Streaming SSR, ISR, Edge DB, Zero-Config Deploy, VDOM + CSR Dual Rendering

---

## Quick Start

```bash
pip install tw-framework
tw create my-site
cd my-site
tw build
```

That's it. Your static site is in `dist/` — deploy it anywhere.

### Optional Features

The core framework has **zero hard dependencies**. Install extras as needed:

```bash
pip install tw-framework[image]       # Pillow — image optimization, srcset
pip install tw-framework[compression] # brotli — production pre-compression
pip install tw-framework[edge-v8]      # py_mini_racer — V8 JS sandbox runtime
pip install tw-framework[redis]       # redis — distributed SSR cache
pip install tw-framework[wasm]        # wasmtime — WebAssembly sandbox runtime
pip install tw-framework[all]         # All optional features combined
```

---

## v0.9.15 Features

### Plugin System
WordPress-inspired plugin system with `.twp` format, 5 lifecycle hooks, and auto-yes permissions.
```bash
tw plugin add seo-booster    # Install plugin
tw plugin list               # List installed plugins
tw plugin search             # Search registry
```
See [PLUGINS.md](PLUGINS.md) for full documentation.

### Hot Module Replacement (HMR)
Save `.tw` file → browser updates instantly. WebSocket-based, like Next.js Fast Refresh.

### Build-time Image Optimization
Automatic WebP variants, responsive `srcset`, and lazy loading.

### Client-side Prefetching
Hover and viewport-based link prefetching for instant navigation.

### Streaming SSR
Server-Sent Events streaming with skeleton loaders for faster TTFB.

### On-demand ISR
Incremental Static Regeneration with `POST /__tw/revalidate` endpoint.

### Edge DB Proxy
Database access from Edge runtime via `POST /__tw/db` — real SQL support.

### Zero-Config Deployment
Auto-detects target (Vercel, Netlify, Cloudflare, GitHub Pages, Docker) and generates config.

### VDOM + CSR Dual Rendering
Choose between two rendering modes:
- `render interactive` — TW native VDOM (~3KB), Zero-JS, SEO perfect (default)
- `render csr` — Full React CSR, React ecosystem, for complex UI

```tw
page {
  title "My App"
  render csr
}
```

---

## What's New (v0.9.06)

### Multi-Runtime Architecture

TW now supports **5 runtimes** for API route handlers. Add a `runtime = "..."` directive at the top of any `.twm` file:

| Runtime | Directive | Engine | Best For |
|---------|-----------|--------|----------|
| **Edge** | `runtime = "edge"` | V8 Isolate (py_mini_racer) | Fast, lightweight APIs — real JS sandbox like Next.js Edge |
| **Node.js** | `runtime = "nodejs"` | Node.js (persistent worker) | Full npm packages, fs, native modules |
| **Python** | `runtime = "python"` | Python in-process | Python libraries, ML, no Node.js needed |
| **WASM** | `runtime = "wasm"` | wasmtime / Python sandbox | Untrusted code, secure sandbox |
| **Edge (legacy)** | `runtime = "edge-py"` | Python in-process | Fallback if V8 not installed |

Default is `nodejs` — all existing routes work as before (backward compatible).

### Common API Layer (`tw.*`)

Write once, run on any runtime:

```javascript
tw.storage.read("config.json")     // → fs on Node, os on Python, KV on Edge
tw.storage.write("output.txt", data)
tw.http.fetch("https://api.com")   // → fetch on Edge, urllib on Python
tw.crypto.hash("sha256", data)     // → Node crypto, hashlib, pure JS SHA-256
tw.crypto.random(32)
tw.crypto.uuid()
tw.env.get("DATABASE_URL")
tw.cache.get("key")
tw.cache.set("key", value, 300)
tw.runtime.name()                  // → "edge", "nodejs", "python", "wasm"
tw.runtime.supports("filesystem")  // → true/false
```

### Build-Time Runtime Validation

If a route configured for Edge uses `fs.readFile()`, TW catches it at **build time** — not at runtime:

```
⚠️ Runtime validation: app/api/data/route.twm
   This route is configured for Edge Runtime,
   but `fs.readFile` requires filesystem capability.

   Solutions:
     1. Change runtime to nodejs
     2. Use tw.storage.read()
     3. Move filesystem logic to a nodejs route
```

### Edge Runtime (V8)

TW's Edge runtime uses **real V8 isolate** (same engine as Google Chrome and Next.js Edge Runtime):

- Pure JS SHA-256 (64-round, UTF-8, proper padding)
- Pure JS HMAC-SHA256
- HTTP fetch via multi-pass yield bridge
- Environment variables injection
- In-memory KV storage
- No filesystem, no subprocess, no native modules

Install V8: `pip install py_mini_racer`

---

## Core Features

### App Router

```
[home]/
├── layout.tw          ← Root layout
├── page.tw            ← Home page (/)
├── about/
│   └── page.tw        ← /about
├── blog/
│   ├── page.tw        ← /blog
│   └── [slug]/
│       └── page.tw    ← /blog/:slug (dynamic)
├── (dashboard)/       ← Route group (doesn't appear in URL)
│   ├── layout.tw
│   └── stats/
│       └── page.tw    ← /stats
├── api/
│   └── route.twm      ← API route handler
├── not-found.tw       ← 404 page
└── error.tw           ← Error boundary
```

### Virtual DOM

VDOM is auto-detected. If your page uses `state`, events, or bindings, the VDOM runtime is injected automatically.

```tw
page {
    title "Counter"
    render interactive
}

state {
    count 0
}

body {
    button { on:click "count++" } "Increment"
    p { tw-text "count" } ""
}
```

Static pages remain **Zero-JS** — no runtime, no overhead.

### API Routes (.twm)

```javascript
// app/api/users/route.twm

runtime = "edge"

fn get(request) {
    return {
        "users": [
            { "id": 1, "name": "User 1" },
            { "id": 2, "name": "User 2" }
        ]
    }
}

fn post(request) {
    var hash = tw.crypto.hash("sha256", request.body)
    return {
        "status": 201,
        "body": { "hash": hash }
    }
}
```

### NPM Package Manager

```bash
tw install react react-dom        # Install packages
tw install chart.js@4.0.0         # Specific version
tw remove react                    # Remove a package
tw list                            # List installed packages
```

### Server Actions

```tw
action createPost {
    method POST
    handler "createPost"
    require_auth true
}

body {
    button { on:click "__twAction('createPost', { title: 'Hello' })" } "Create"
}
```

### Lib System

```tw
import { getApps } from "@/lib/data"

page {
    title "Apps"
    render static
}

let apps = getApps()

body {
    each apps as app {
        div { class "card"
            h1 "{app.name}"
        }
    }
}
```

---

## CLI Commands

| Command | Description |
|---------|-------------|
| `tw create <name>` | Create new project |
| `tw build` | Build site to `dist/` |
| `tw dev` | Start dev server |
| `tw info` | Show project info + runtime diagnostics |
| `tw install <pkg>` | Install npm package |
| `tw remove <pkg>` | Remove npm package |
| `tw list` | List installed packages |
| `tw dead` | Find unused files |

---

## Runtime Capability Matrix

| Capability | nodejs | python | edge (V8) | wasm |
|-----------|--------|--------|-----------|------|
| filesystem | ✅ | ✅ | ❌ | ✅ (sandbox) |
| network | ✅ | ✅ | ✅ | ❌ |
| native modules | ✅ | ✅ | ❌ | ❌ |
| subprocess | ✅ | ✅ | ❌ | ❌ |
| database | ✅ | ✅ | ❌ | ❌ |
| crypto | ✅ | ✅ | ✅ | ✅ |
| cache | ✅ | ✅ | ✅ | ✅ |
| env vars | ✅ | ✅ | ✅ (limited) | ✅ (granted) |

---

## Deployment

Output is static HTML/CSS/JS in `dist/`. Deploy to any host:
- Vercel, Netlify, Cloudflare Pages
- GitHub Pages
- Any static file server

---

## Documentation

- [RUNTIMES.md](RUNTIMES.md) — Complete multi-runtime guide (11 sections)
- [PROGRESS.md](PROGRESS.md) — Development progress tracker
- [CHANGELOG.md](CHANGELOG.md) — All version changes

---

## License

MIT
