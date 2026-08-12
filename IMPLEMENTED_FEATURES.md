# TW Framework — Implemented Features

## Core Framework
- Custom DSL with lexer, parser, compiler (6863-line compiler.py)
- App Router with nested layouts, dynamic routes, catch-all, route groups
- 6 render modes: static, server, edge, interactive, dynamic, csr
- Component system with scoped CSS, typed props, children slots
- TSS stylesheet system with CSS variables and dark mode
- Reactive state management with VDOM (~19KB runtime)
- Server actions with CSRF support
- Streaming SSR with skeleton loaders
- Incremental Static Regeneration (ISR)

## CLI (1680 lines)
- 22+ commands: create, init, dev, build, export, preview, serve, deploy
- Plugin management: add, list, search
- npm package management: install, add, remove, list
- Debug tools: ast, ir, tokens, check, run
- Health check: doctor, info, clean
- Global flags: --project-root, --debug, --version

## Multi-Runtime (5 runtimes)
- Node.js (persistent worker, full npm ecosystem)
- Edge V8 (real V8 isolate via py_mini_racer)
- Python (in-process, ML-ready)
- WASM (wasmtime sandbox)
- Edge legacy (Python fallback)
- Common tw.* API layer (storage, http, crypto, cache, env)

## Server (744 lines)
- Production SSR server with threaded TCP
- SSR cache (in-memory LRU + Redis)
- Brotli/gzip pre-compressed file negotiation
- ETag and Cache-Control headers
- WebSocket support
- Health check endpoint
- Graceful shutdown (SIGTERM/SIGINT)
- AST cache with TTL
- Request body size limiting
- Security headers on all responses

## Security (388 lines)
- CSP nonce generation and header builder
- HTML/URL/attribute sanitization with double-escape protection
- CSRF token generation and validation
- Null byte removal
- Env var filtering for Edge runtime
- Authenticated encryption (scrypt + HMAC-SHA256)
- V8 execution timeout (30s)

## Middleware
- Rule-based: match, header, methods, auth, rate_limit, user_agent, origin
- Function-based: fn before(ctx), fn after(ctx)
- Path security: deny_traversal, deny_null_bytes, regex, extensions
- Token bucket rate limiting

## Module Boundaries (337 lines)
- Import classification: SERVER, CLIENT, SHARED
- Source code analysis with caching
- Dynamic import() and require() scanning
- Boundary violations with severity field
- ImportInfo with is_dynamic flag

## Plugin System
- .twp plugin format
- 5 lifecycle hooks
- ExtensionManager with event emission
- Plugin discovery and dependency tracking

## Build Pipeline
- 11-stage pipeline (lexing → output)
- Parallel compilation (--workers)
- HMR via WebSocket
- Bundle analysis (--analyze)
- Build reports (--report)
- Dead code detection
- Tree shaking
- Code splitting
- Minification (HTML, CSS, JS)
- Production optimizations (brotli, SRI hashes)

## Image Optimization
- WebP variant generation
- Responsive srcset
- Lazy loading
- Auto alt text from filename
- Multiple format support (requires Pillow)

## Deployment
- Zero-config deployment to Vercel, Netlify, Cloudflare, GitHub Pages, Docker
- Auto-generated configs
- --dry-run preview mode

## Testing
- 610 tests, 9 skipped, 0 failed
- pytest-based test suite

## Package Structure
- py.typed (PEP 561 type marker)
- __main__.py (python -m tw_framework)
- __version__.py (standalone version info)
- Optional dependencies via pyproject.toml extras
