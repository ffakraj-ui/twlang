# TW Framework — Progress

## Current Version: v0.9.38

### v0.9.38
- Added index.tw as alternative to page.tw (index.tw takes priority)
- Build-time warning when both index.tw and page.tw exist
- Updated all .md files with new features, commands, and error documentation

### v0.9.38
- Fixed API routes with runtime directive returning 500 error
- Added json/text/html response shape support
- Fixed --debug flag to show full Python traceback
- JS runner now always includes stack traces in error responses

### v0.9.28
- Fixed .twm runtime directive parsing
- Added port auto-increment for tw serve
- Added tw infrastructure, tw health, tw routes commands
- Added --debug and --version flags
- Improved CLI error messages

### v0.9.27
- Added 580 stability tests
- Fixed infrastructure.py Terraform rendering
- Fixed edge_middleware.py CORS headers

### v0.9.26
- Fixed missing imports across 20+ files
- Fixed SyntaxWarnings

### v0.9.25
- Added 7 new modules (instant navigation, devtools, parallel routes, etc.)

### v0.9.24
- Added PPR boundaries, cache directive, ESBuild, RSC streaming

### v0.9.23
- Added 8 new modules (RSC payload, hooks, metadata, edge middleware, etc.)

### v0.9.22
- Expanded 6 architecture modules

### v0.9.21
- Expanded 6 architecture modules with compiler integration

### v0.9.20
- Added feature_architecture, enhanced_actions, fetch_memo

### v0.9.19
- Added PPR, cache tiers, bundle optimizer

### v0.9.18
- Fixed BaseRuntime.execute(), EdgeV8Cache, WASM env filtering

### v0.9.17
- Rewrote documentation

### v0.9.16
- Added security hardening (scrypt+HMAC, thread safety)

### v0.9.15
- PyPI release preparation

### v0.9.14
- Fixed edge V8, module boundaries, runtime

### v0.9.13
- Fixed reactivity, parser, security, bundler, error formatter

### v0.9.12
- Fixed app router, server, compiler

### v0.9.11
- Fixed compiler and CLI

### v0.9.10
- Fixed react_compat recursion, Zero-JS prefetch

### v0.9.09
- Initial release
