# Changelog

All notable changes to TW Framework are documented here.

## [0.9.38] - 2026-08-13

### Security
- **Plugin verification via registry code matching** — removed HMAC/secret approach entirely. No secret key, no per-installation key, nothing to steal.
- How it works now:
  1. `install_plugin()` downloads plugin from official registry, saves with embedded SHA-256 hash (TWP1 format)
  2. `load_all()` reads installed plugin, verifies embedded hash (catches tampering)
  3. `_verify_plugin_from_registry()` fetches official code from registry and compares SHA-256 (catches fake/custom plugins)
  4. Match → load. Mismatch → reject. Not in registry → reject.
- Open source safe: no secret in code, no key file, nothing to reverse-engineer
- Offline fallback: if registry unreachable, trust embedded hash (still catches tampering)
- 15 tests in `test_plugin_integrity.py` covering: save/load roundtrip, tampered content, fake TWP1, manual plugin rejection, mixed valid/invalid

## [0.9.37] - 2026-08-13

### Security
- **Plugin secret no longer hardcoded**: Removed `_PLUGIN_GUARD_SECRET` constant from source code. Now uses `_get_plugin_secret()` which generates a unique 256-bit random secret per installation, stored in `~/.tw/plugin_secret.key` (user home, NOT in project/git).
  - Secret is NOT in source code (open source safe)
  - Secret is NOT in project directory (git safe)
  - Each machine has a different secret (copying .tw/plugins/ to another machine won't work)
  - Auto-generated on first `tw plugin add` using `secrets.token_hex(32)`
  - File permissions 0600 (only owner can read/write)

## [0.9.36] - 2026-08-13

### Security
- **Plugin Integrity Guard**: Plugins are now saved in TWP1 encoded format with HMAC-SHA256 signature. This prevents:
  1. Manual plugin drops into .tw/plugins/ (no valid signature → rejected)
  2. Modification of installed plugins (signature breaks → rejected)
  3. Plugin name spoofing (HMAC bound to plugin name → wrong name → rejected)
- `install_plugin()` now encodes content before saving using `_encode_plugin_content()`
- `load_all()` now decodes and verifies signature using `_decode_plugin_content()`
- Added 17 tests in `test_plugin_integrity.py` covering encoding, decoding, tampering, and name mismatch scenarios

## [0.9.35] - 2026-08-13

### Fixed
- **VDOM parser**: Text after closing brace `}` now parsed as text node. `button { on:click "count++" } "Count: {count}"` no longer crashes with "Unexpected token". Added STRING token handler in `parse_child_statement()`.
- **`tw --debug`**: `--debug` flag now works with ALL subcommands (`tw build --debug`, `tw serve --debug`, etc.). Previously `--debug` was only on the main parser, so `tw build --debug` silently failed. Added `--debug` to all 25 subparsers.
- **Plugin registry**: Updated `PLUGIN_REGISTRY_URL` to point to `ffakraj-ui/tw-plugins` repo. Created sample plugin `tw-analytics` with `registry.json`, `manifest.json`, and `index.js`.

### Changed
- **index.tw warning**: Demoted "Both index.tw and page.tw found" from `warning` to `debug` level — less noisy, priority still works.
- **Dynamic route JSON warning**: Demoted "page.json not found" from `warning` to `debug` level — JSON is optional, warning was noisy.

## [0.9.34] - 2026-08-13

### Fixed
- **Critical**: Lib function calls in `{ }` interpolation now actually execute. Previously `{greet('Suraj')}` rendered as raw text because of THREE separate bugs:
  1. **`_safe_eval()` missing `ast.Call` handler** (v0.9.33 partial fix) — function call AST nodes raised `ValueError("Unsupported expression node: Call")`. Added `ast.Call` handler that checks `_LIB_MODULES` and context callables.
  2. **ES6 imports never triggered `register_lib_module()`** — `import { greet } from "@/lib/helpers"` stored entries in `_ES6_IMPORTS` list but nobody consumed it. Added post-processing loop in `build_tw_ast()` that resolves `@/`-prefixed paths to `HOME_DIR` and calls `register_lib_module()`.
  3. **`@/` path resolution treated `/lib/helpers` as absolute** — after stripping `@` from `@/lib/helpers`, the leading `/` made `os.path.isabs()` return True, discarding `PROJECT_ROOT`. Fixed in `resolve_source_path()` by stripping leading `/` for project-relative paths. Also changed ES6 import resolution to use `HOME_DIR` directly (Next.js convention).

### Tests
- Added 17 integration tests in `test_es6_import_integration.py` covering:
  - ES6 import → `register_lib_module()` → `_LIB_MODULES` registration
  - Full pipeline: import → register → `evaluate_expression()` → `interpolate()`
  - `@/` path resolution to `HOME_DIR`
  - Multiple imported functions, missing files, `is_function_call()` detection

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
