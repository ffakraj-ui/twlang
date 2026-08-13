# Changelog

All notable changes to TW Framework are documented here.

## [0.9.33] - 2026-08-13

### Fixed
- **Critical**: Lib function calls in `{ }` interpolation now execute correctly. Previously `{greet('Suraj')}` would render as raw text instead of `Hello, Suraj!`.
  - Added `ast.Call` handler to `_safe_eval()` in `compiler.py` — function calls were silently failing because `ast.Call` nodes raised `ValueError("Unsupported expression node: Call")`.
  - Added lib function fallback in `evaluate_expression()` — when normal eval fails, checks `_LIB_MODULES` and calls `_try_execute_lib_function()`.
  - Added `None` input guard to `evaluate_expression()` to prevent `AttributeError` on `None.strip()`.
- **Critical**: Fixed `_scan_matching_brace()` in `twm_parser.py` — template literal `${...}` interpolation (e.g. `` `Hello, ${name}!` ``) caused "Unterminated `{ ... }` block" error because the parser didn't return to template mode after closing the `${...}` expression. Added `template_stack` to track interpolation depth and correctly resume template mode.

### Tests
- Added 32 new regression tests in `test_interpolation_fix.py` covering:
  - `_safe_eval` ast.Call handler (callable in context, lib functions, nested calls, attribute methods)
  - `interpolate()` with function calls in text (simple, multiple, mixed with variables)
  - Lib module registration and execution
  - `evaluate_expression()` integration (variables, attributes, arithmetic, booleans, comparisons)

## [0.9.32] - 2026-08-13

### Fixed
- **Critical**: `twm_api_runner_persistent.js` line 44 — `findProjectRoot()` used undefined variable `result` instead of `current`, causing `ReferenceError: result is not defined` for ALL API routes with `runtime = "nodejs"` directive. This was the root cause of the 500 error on every `.twm` API route.
- Also checked and fixed same bug in `twm_api_runner.js` (non-persistent runner).

## [0.9.31] - 2026-08-13

### Fixed
- Updated all 281 documentation files in `docs/` directory:
  - Replaced old version references (v0.5.x, v0.6.x, v0.7.x, v0.8.x) with current version
  - Added `index.tw` mentions to routing, project structure, and getting-started docs
  - Replaced `TW_PORT` environment variable with `--port` flag in deployment docs
  - Added new CLI commands (`tw infrastructure`, `tw health`, `tw routes`) to CLI reference
  - Added API response shapes (`json`, `text`, `html`) to API route documentation
  - Added runtime directive documentation to all API-related docs
  - Updated error reference with new error types and debug mode
  - Updated FAQ with index.tw, port auto-increment, and response shape questions
  - Updated best-practices and troubleshooting guides

## [0.9.30] - 2026-08-13

### Added
- `index.tw` is now supported as an alternative to `page.tw`. Both work identically as page files.
- When both `index.tw` and `page.tw` exist in the same directory, `index.tw` takes priority and a build-time warning is shown.
- Updated all documentation files with new features, CLI commands, error documentation, and response shapes.

### Changed
- `app_router.py`: `discover_routes()` now checks for both `index.tw` and `page.tw`.
- `framework.py`: route artifact generation also recognizes `index.tw`.
- README.md: comprehensive update with index.tw docs, error table, response shapes, CLI commands.
- IMPLEMENTED_FEATURES.md: all 21 architecture modules listed with descriptions.
- API_TESTING_GUIDE.md: response shapes, runtime directives, error table.
- DEPLOYMENT.md: infrastructure command, port auto-increment.
- RUNTIMES.md: response shapes for all runtimes.
- SECURITY.md: updated with scrypt+HMAC, thread safety.
- PROGRESS.md: v0.9.28-0.9.30 entries added.

## [0.9.29] - 2026-08-12

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
