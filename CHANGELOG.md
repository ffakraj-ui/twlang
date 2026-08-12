# Changelog

All notable changes to TW Framework are documented here.

## [0.9.27] - 2026-08-12

### Added
- Stability test suite: 580 new tests covering architecture and core modules
- `tests/test_stability.py` and `tests/test_stability_core.py`
- `STABILITY_REPORT.md`

### Fixed
- `infrastructure.py`: Terraform template rendering with HCL brace syntax
- `edge_middleware.py`: CORS headers on default pass-through responses

## [0.9.26] - 2026-08-12

### Fixed
- Missing typing imports in 6 files
- Missing stdlib imports in 63 locations across 20+ files
- SyntaxWarnings in ppr.py and enterprise_features.py
- Circular imports in `__init__.py`

## [0.9.25] - 2026-08-11

### Added
- `instant_navigation.py`, `devtools_mcp.py`, `parallel_routes.py`
- `react19_features.py`, `web_vitals.py`, `enterprise_features.py`
- `infrastructure.py` (Terraform IaC for AWS)

## [0.9.24] - 2026-08-11

### Added
- PPR boundaries, use cache directive, ESBuild minification
- RSC streaming, Turbopack bundler concept, incremental prefetch

## [0.9.23] - 2026-08-10

### Added
- `rsc_payload.py`, `react_compiler.py`, `hooks.py`, `metadata_api.py`
- `edge_middleware.py`, `static_export.py`, `image_loader.py`, `shallow_routing.py`

## [0.9.22] - 2026-08-10

### Changed
- Expanded PPR, cache tiers, bundle optimizer, feature architecture
- Expanded enhanced actions, fetch memo

## [0.9.21] - 2026-08-10

### Changed
- Expanded PPR with compiler integration, streaming SSR
- Expanded cache tiers with Redis support
- Expanded bundle optimizer with build pipeline

## [0.9.20] - 2026-08-09

### Added
- `feature_architecture.py`, `enhanced_actions.py`, `fetch_memo.py`

## [0.9.19] - 2026-08-09

### Added
- `ppr.py`, `cache_tiers.py`, `bundle_optimizer.py`

## [0.9.18] - 2026-08-08

### Fixed
- `BaseRuntime.execute()` abstract method
- `EdgeV8Cache` class missing from edge runtime
- WASM runtime environment variable filtering

## [0.9.17] - 2026-08-08

### Changed
- Rewrote documentation based on source code analysis

## [0.9.16] - 2026-08-07

### Added
- `py.typed`, `__main__.py`, `__version__.py`, `middleware.py`, `extensions.py`

### Changed
- Replaced XOR encryption with scrypt+HMAC
- Made EdgeV8Storage thread-safe
- Added V8 execution timeout

## [0.9.15] - 2026-08-07

### Changed
- Updated llms.txt and README.md for PyPI release

## [0.9.14] - 2026-08-06

### Fixed
- `edge_v8_adapter.py`, `module_boundaries.py`, `tw_runtime/__init__.py`

## [0.9.13] - 2026-08-06

### Fixed
- `reactivity.py`, `twm_parser.py`, `security.py`, `client_bundler.py`, `error_formatter.py`, `common.py`

## [0.9.12] - 2026-08-05

### Fixed
- `app_router.py`, `server.py`, `compiler.py`

## [0.9.11] - 2026-08-05

### Fixed
- `compiler.py`, `cli.py`

## [0.9.10] - 2026-08-04

### Fixed
- `react_compat.py` recursion, Zero-JS prefetch, version mismatch

## [0.9.09] - 2026-08-04

### Added
- Initial public release
- Custom DSL, App Router, Component system, TSS, VDOM, Server actions
- Streaming SSR, ISR, CLI, Multi-runtime support, Plugin system
