# TW Framework — Documentation

## Overview

TW Framework is a Python-based full-stack web framework with App Router, Zero-JS static sites, NPM package manager, and Multi-Runtime Architecture.

- **Package**: `tw-framework` on PyPI
- **Version**: 0.9.16
- **Python**: >=3.9
- **Core Dependencies**: Zero (pure Python stdlib)
- **License**: MIT
- **Author**: KANISHK KUMAR (mlkraj290@gmail.com)

## Installation

```bash
pip install tw-framework
```

Optional features:
```bash
pip install tw-framework[image]        # Pillow — image optimization
pip install tw-framework[compression]  # brotli — pre-compression
pip install tw-framework[edge-v8]       # py_mini_racer — V8 sandbox
pip install tw-framework[redis]        # redis — SSR cache
pip install tw-framework[wasm]         # wasmtime — WASM runtime
pip install tw-framework[all]           # All combined
```

## File Types

| Extension | Purpose |
|-----------|---------|
| `.tw` | Pages, components, layouts |
| `.tss` | Stylesheets |
| `.twm` | API routes, server modules |
| `.twp` | Plugins |
| `.js`/`.ts` | Client libraries |
| `.json` | Data for dynamic routes |

## CLI Commands

See README.md for full command reference.

## Key Concepts

### App Router
File-based routing with `[home]/` as root. Supports dynamic routes (`[slug]`), catch-all (`[...slug]`), optional catch-all (`[[...slug]]`), and route groups (`(group)`).

### Render Modes
`static` (SSG), `server` (SSR), `edge` (V8 sandbox), `interactive` (VDOM), `dynamic` (auto), `csr` (React).

### Multi-Runtime
5 runtimes: Node.js, Edge V8, Python, WASM, Edge (legacy). Common API via `tw.*`.

### Middleware
Rule-based (`use`/`rule` blocks) and function-based (`fn before`/`fn after`). Supports auth, rate limiting, CORS, path security, headers.

### Plugin System
`.twp` files with 5 lifecycle hooks: beforeBuild, afterBuild, beforeRoute, afterRoute, beforeRequest.

### Security
CSP nonces, HTML/URL sanitization, CSRF tokens, security headers, env var filtering, authenticated encryption.

### Build Pipeline
Lexing → Parsing → Semantic analysis → IR lowering → HTML/CSS rendering → JS bundling → Dead code detection → Tree shaking → Minification → Output.

## References

- [README.md](README.md) — Quick start, CLI, project structure
- [RUNTIMES.md](RUNTIMES.md) — Multi-runtime details
- [SECURITY.md](SECURITY.md) — Security features
- [DEPLOYMENT.md](DEPLOYMENT.md) — Deployment guide
- [PLUGINS.md](PLUGINS.md) — Plugin system
- [CHANGELOG.md](CHANGELOG.md) — Version history
- [llms.txt](llms.txt) — AI assistant reference
- [llms-full.txt](llms-full.txt) — Full project metadata
