# TW Framework — Progress

## Current Version: v0.9.27

## Version History

### v0.9.27
- Added 580 stability tests across architecture and core modules
- Fixed infrastructure.py Terraform template rendering
- Fixed edge_middleware.py CORS headers on default responses

### v0.9.26
- Fixed missing typing imports in 6 files
- Added missing stdlib imports in 63 locations across 20+ files
- Fixed SyntaxWarnings in ppr.py and enterprise_features.py

### v0.9.25
- Added instant_navigation.py, devtools_mcp.py, parallel_routes.py
- Added react19_features.py, web_vitals.py, enterprise_features.py
- Added infrastructure.py (Terraform IaC)

### v0.9.24
- Added PPR boundaries, use cache directive, ESBuild minification
- Added RSC streaming, Turbopack bundler concept, incremental prefetch

### v0.9.23
- Added rsc_payload.py, react_compiler.py, hooks.py, metadata_api.py
- Added edge_middleware.py, static_export.py, image_loader.py, shallow_routing.py

### v0.9.22
- Expanded PPR, cache tiers, bundle optimizer, feature architecture
- Expanded enhanced actions, fetch memo

### v0.9.21
- Expanded PPR with compiler integration, streaming SSR
- Expanded cache tiers with Redis support
- Expanded bundle optimizer with build pipeline

### v0.9.20
- Added feature_architecture.py, enhanced_actions.py, fetch_memo.py

### v0.9.19
- Added ppr.py, cache_tiers.py, bundle_optimizer.py

### v0.9.18
- Fixed BaseRuntime.execute(), EdgeV8Cache, WASM env filtering

### v0.9.17
- Rewrote documentation based on source code analysis

### v0.9.16
- Added py.typed, __main__.py, __version__.py, middleware.py, extensions.py
- Replaced XOR encryption with scrypt+HMAC
- Made EdgeV8Storage thread-safe

### v0.9.15
- PyPI release preparation

### v0.9.14
- Fixed edge_v8_adapter.py, module_boundaries.py, tw_runtime/__init__.py

### v0.9.13
- Fixed reactivity.py, twm_parser.py, security.py, client_bundler.py, error_formatter.py, common.py

### v0.9.12
- Fixed app_router.py, server.py, compiler.py

### v0.9.11
- Fixed compiler.py, cli.py

### v0.9.10
- Fixed react_compat.py recursion, Zero-JS prefetch, version mismatch

### v0.9.09
- Initial release
