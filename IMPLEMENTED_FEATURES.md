# TW Framework — Implemented Features

## Core Framework
- Custom DSL with lexer, parser, compiler
- App Router with nested layouts, dynamic routes, catch-all, route groups
- `index.tw` and `page.tw` both supported as page files (index.tw takes priority)
- 6 render modes: static, server, edge, interactive, dynamic, csr
- Component system with scoped CSS, typed props, children slots
- TSS stylesheet system with CSS variables and dark mode
- Reactive state management with VDOM
- Server actions with CSRF support
- Streaming SSR with skeleton loaders
- Incremental Static Regeneration (ISR)

## CLI Commands
- `tw create` — scaffold new project
- `tw init` — initialize in current directory
- `tw dev` — local dev server with hot reload
- `tw build` — production build
- `tw export` — static export
- `tw preview` — preview production build
- `tw serve` — production server with SSR + API routes (port auto-increment)
- `tw deploy` — deploy to Vercel/Netlify/Cloudflare/Docker
- `tw infrastructure` — generate Terraform IaC for AWS
- `tw health` — run health checks
- `tw routes` — list all routes
- `tw plugin add/remove/list/search` — plugin management
- `tw install/add/remove/list` — npm package management
- `tw check` — type-check and diagnostics
- `tw ast` — dump AST JSON
- `tw ir` — dump IR JSON
- `tw tokens` — dump token stream
- `tw run` — interpret TW file
- `tw doctor` — project health checks
- `tw info` — project summary
- `tw clean` — clean dist and cache
- `tw login` — save deploy config
- `--debug` — full error traceback
- `--version` / `-v` — show version

## API Routes (.twm)
- `runtime = "nodejs"` directive support
- Response shapes: `{ status, json }`, `{ status, text }`, `{ status, html }`, `{ status, body }`
- Function handlers: get, post, put, patch, delete, options, handler
- Top-level imports (npm packages)
- Persistent Node.js worker for fast execution

## Runtimes
- Node.js (default) — full npm packages, fs, native modules
- Edge V8 — V8 Isolate, fast lightweight APIs
- Python — in-process Python execution
- WASM — wasmtime sandbox for untrusted code

## Architecture Modules (21 modules)
- PPR (Partial Prerendering) — component-level static/dynamic boundaries
- Cache Tiers (4-layer) — request memo, data cache, full route cache, router cache
- Bundle Optimizer — code splitting, tree shaking, CSS optimization
- RSC Payload — binary payload format, streaming
- React Compiler — automatic memoization analysis
- Hooks — useOptimistic, useActionState, useFormStatus, useTransition
- Metadata API — OpenGraph, Twitter cards, JSON-LD, robots, canonical
- Edge Middleware — request interception, CORS, rate limiting
- Static Export — SPA mode, generateStaticParams
- Image Loader — Cloudinary, Imgix, Vercel
- Shallow Routing — pushState, query updates
- Enhanced Actions — chaining, pipeline, queue, rate limiting
- Fetch Memo — retry, timeout, circuit breaker, batch
- Instant Navigation — route caching, insights
- DevTools MCP — debugging protocol
- Parallel Routes — slots, intercepting routes, modals
- React 19 Features — view transitions, useEffectEvent
- Web Vitals — TTFB, FCP, LCP, CLS, INP monitoring
- Enterprise Features — health checks, coupling graph, observability
- Infrastructure — Terraform IaC for AWS (VPC, ECS, ALB, S3, CloudFront, WAF, Redis)
- Feature Architecture — feature loader, sandboxing, code generation

## Security
- Content Security Policy with nonce
- CSRF token generation and verification
- HTML/URL/attribute sanitization
- Password strength checking
- Content integrity hashing (SRI)
- Secure headers (HSTS, X-Frame-Options, X-Content-Type-Options, etc.)
- scrypt+HMAC password hashing
- Thread-safe Edge V8 storage

## Plugin System
- `.twp` format with 5 lifecycle hooks
- Plugin registry and search

## Deployment
- Vercel, Netlify, Cloudflare, Docker
- Health check endpoints (/health/live, /health/ready)
- Terraform IaC generation for AWS
