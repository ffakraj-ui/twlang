# Changelog

All notable changes to TW Framework are documented here.

## [0.9.27] - 2026-08-12

### Added
- Stability test suite: 580 new tests covering architecture and core modules
- `tests/test_stability.py` — tests for PPR, cache tiers, RSC payload, hooks, metadata API, edge middleware, static export, image loader, shallow routing, and 12 other modules
- `tests/test_stability_core.py` — tests for compiler, server, app router, reactivity, security, client bundler, CLI, runtime, and 55+ other core modules
- `STABILITY_REPORT.md` — test results summary

### Fixed
- `infrastructure.py`: Terraform template rendering crashed because `str.format()` could not handle HCL brace syntax. Replaced with `str.replace()`-based `_render()` method.
- `edge_middleware.py`: CORS headers were missing on default pass-through responses.

## [0.9.26] - 2026-08-12

### Fixed
- Added missing typing imports in 6 files (compiler.py, enhanced_actions.py, feature_architecture.py, fetch_memo.py, ppr.py, server.py)
- Added missing stdlib imports in 63 locations across 20+ files (time, os, json, re, logging, threading, hashlib, gzip, base64, datetime, urllib, struct, signal)
- Fixed SyntaxWarnings in ppr.py (invalid escape sequences) and enterprise_features.py (regex pattern)
- Cleaned up `__init__.py` to avoid circular imports from bulk module imports

## [0.9.25] - 2026-08-11

### Added
- `instant_navigation.py` — instant navigation with route caching and Playwright insights
- `devtools_mcp.py` — debugging protocol for development tools
- `parallel_routes.py` — parallel route slots and intercepting routes for modals
- `react19_features.py` — view transitions and `useEffectEvent`
- `web_vitals.py` — streaming optimization and web vitals monitoring
- `enterprise_features.py` — health checks, coupling graph, observability, conventional commits
- `infrastructure.py` — Terraform IaC generator for AWS (VPC, ECS, ALB, S3, CloudFront, WAF, Redis)

## [0.9.24] - 2026-08-11

### Added
- Partial prerendering boundaries in `ppr.py`
- `use cache` directive support in `compiler.py`
- ESBuild minification and `next/dynamic` CSR in `client_bundler.py`
- RSC streaming and TanStack hydration boundary in `server.py`
- Turbopack-style bundler concept in `bundle_optimizer.py`
- Incremental prefetch and layout dedup in `cache_tiers.py`
- `edge_middleware.py` proxy handler
- `static_export.py` SPA mode and `generateStaticParams`
- `image_loader.py` custom loader with Cloudinary/Imgix support
- `shallow_routing.py` pushState-based shallow routes

## [0.9.23] - 2026-08-10

### Added
- `rsc_payload.py` — RSC binary payload format, streaming, client/server directives
- `react_compiler.py` — automatic memoization analysis
- `hooks.py` — useOptimistic, useActionState, useFormStatus, useTransition
- `metadata_api.py` — OpenGraph, Twitter cards, JSON-LD, robots, canonical
- `edge_middleware.py` — edge runtime middleware, request interception
- `static_export.py` — static export with auto-optimization
- `image_loader.py` — custom image loader support
- `shallow_routing.py` — shallow routing with history API

## [0.9.22] - 2026-08-10

### Changed
- Expanded PPR module with hydration, error boundaries, debug tools, route matcher, snapshot manager
- Expanded cache tiers with metrics, compression, migration, monitoring, garbage collection
- Expanded bundle optimizer with CSS optimizer, asset pipeline, image integration
- Expanded feature architecture with feature loader, sandboxing, code generation
- Expanded enhanced actions with action composition, chaining, pipeline, event emitter
- Expanded fetch memo with retry, timeout, queue, batch fetch

## [0.9.21] - 2026-08-10

### Changed
- Expanded PPR module with compiler integration, streaming SSR, suspense rendering
- Expanded cache tiers with Redis support, SSR integration, revalidation system
- Expanded bundle optimizer with build pipeline, chunking, source maps
- Expanded feature architecture with compiler/router integration
- Expanded enhanced actions with server integration, middleware, rate limiting
- Expanded fetch memo with runtime integration, stats, cache layer chaining

## [0.9.20] - 2026-08-09

### Added
- `feature_architecture.py` — feature-sliced architecture support
- `enhanced_actions.py` — enhanced server actions with progressive enhancement
- `fetch_memo.py` — request memoization integration

## [0.9.19] - 2026-08-09

### Added
- `ppr.py` — partial prerendering with component-level static/dynamic boundaries
- `cache_tiers.py` — four-tier cache system (request memoization, data cache, full route cache, router cache)
- `bundle_optimizer.py` — code splitting, tree-shaking, bundle analysis

## [0.9.18] - 2026-08-08

### Fixed
- `BaseRuntime.execute()` — added abstract method implementation
- `EdgeV8Cache` class was missing from edge runtime
- WASM runtime environment variable filtering

## [0.9.17] - 2026-08-08

### Changed
- Rewrote documentation files based on source code analysis
- Updated README.md, llms.txt, llms-full.txt
- Updated RUNTIMES.md, SECURITY.md, DEPLOYMENT.md, DOCUMENTATION.md

## [0.9.16] - 2026-08-07

### Added
- `py.typed` marker for PEP 561 compliance
- `__main__.py` for `python -m tw_framework` support
- `__version__.py` for version centralization
- `middleware.py` with AuthMiddleware and MiddlewareChain
- `extensions.py` with ExtensionManager

### Changed
- Replaced XOR encryption with scrypt+HMAC in security module
- Made EdgeV8Storage thread-safe with threading.Lock
- Added V8 execution timeout
- Improved path sanitization

## [0.9.15] - 2026-08-07

### Changed
- Updated llms.txt files for PyPI release
- Updated README.md with installation and usage instructions
- Version bump for PyPI release

## [0.9.14] - 2026-08-06

### Fixed
- `edge_v8_adapter.py`: V8 execution timeout, thread-safe storage, memory leak on context reload, cache TTL tracking
- `module_boundaries.py`: import classifier, boundary violation detection, package boundary resolution
- `tw_runtime/__init__.py`: runtime registry, capability validation, compatibility checks

## [0.9.13] - 2026-08-06

### Fixed
- `reactivity.py`: state block parsing, server action extraction, VDOM runtime
- `twm_parser.py`: module compilation, function extraction
- `security.py`: CSP nonce, password strength check, content integrity hash
- `client_bundler.py`: CJS/ESM conversion, builtin module stubs
- `error_formatter.py`: diagnostic formatting
- `common.py`: utility functions

## [0.9.12] - 2026-08-05

### Fixed
- `app_router.py`: file-based routing, dynamic routes, catch-all routes, route groups, layout resolution
- `server.py`: SSR cache, static file serving, ETag computation, production handler
- `compiler.py`: cache directive, build options, diagnostic emitter

## [0.9.11] - 2026-08-05

### Fixed
- `compiler.py`: expression analysis, semantic analysis, node lowering, diagnostic output
- `cli.py`: build command, check command, package.json generation, deploy config

## [0.9.10] - 2026-08-04

### Fixed
- `react_compat.py`: recursion issue in component rendering
- Zero-JS prefetch injection on static pages
- Version string mismatch between modules

## [0.9.09] - 2026-08-04

### Added
- Initial public release
- Custom DSL with lexer, parser, compiler
- App Router with nested layouts, dynamic routes, catch-all, route groups
- Component system with scoped CSS, typed props
- TSS stylesheet system
- Reactive state management with VDOM
- Server actions with CSRF support
- Streaming SSR with skeleton loaders
- Incremental Static Regeneration (ISR)
- CLI with create, dev, build, deploy commands
- Multi-runtime support: Node.js, Edge V8, Python, WASM
- Plugin system with `.twp` format
- Zero-JS static site generation
