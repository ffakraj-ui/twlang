# Changelog

## v0.8.1 (2026-08-10)

### Major Features

#### NPM Package Manager
- `tw install <package>` — Install npm packages like Next.js (alias: `tw add`)
- `tw install` (no args) — Install all dependencies from package.json
- `tw remove <package>` — Remove npm packages (alias: `tw rm`)
- `tw list` — List installed packages (alias: `tw ls`)
- `tw list --detailed` — Show installed versions from node_modules
- `--dev` flag for devDependencies, `--exact` for exact versions
- Auto-detects package manager (npm, pnpm, yarn, bun) from lockfiles
- Auto-updates `tw.config` `server.external_packages` on install/remove
- Version specifiers supported: `tw install react@18.2.0`
- Multiple packages: `tw install react react-dom axios`
- React detection hint when react/react-dom is installed

#### React Compatibility Layer
- `tw_framework/react_compat.py` — Full React integration module
- React can be used alongside TW's native VDOM for interactive islands
- `ReactCompat` class: detect React usage, get version, generate bootstrap JS
- React bootstrap JS with mount/unmount/register API
- CDN fallback loader for dev mode
- Setup hints and documentation for React + TW integration
- Does NOT replace TW VDOM — coexists as progressive enhancement

#### Security Module (`tw_framework/security.py`)
- CSP (Content Security Policy) nonce generation
- `build_csp_header()` — Build CSP headers with nonce support
- `get_secure_headers()` — 9 secure HTTP headers (HSTS, X-Frame-Options, etc.)
- `render_secure_headers_html()` — Render secure headers as meta tags
- `sanitize_html()` — Escape HTML special characters (XSS prevention)
- `sanitize_attribute()` — Sanitize HTML attribute values
- `sanitize_js_string()` — Sanitize strings for JavaScript context
- `sanitize_url()` — Block javascript:, data:, vbscript: URLs
- `generate_csrf_token()` / `validate_csrf_token()` — CSRF protection
- `safe_join_path()` — Path traversal prevention
- `strip_dangerous_html()` — Remove dangerous tags and event handlers

#### Enhanced Lib System
- `_is_npm_package()` and `_resolve_npm_package()` in lib_executor.py
- npm packages from node_modules are now properly resolved in .twm files
- Node.js bridge script enhanced (v0.8.1):
  - Uses `createRequire` for proper module resolution from project root
  - Auto-detects missing npm packages and suggests `tw install`
  - Injects `http`, `env`, `pkg` runtime helpers (matching twm_api_runner.js)
  - `pkg.require()`, `pkg.has()`, `pkg.resolve()`, `pkg.json()` API
- `resolve_module_path()` now handles npm packages (react, chart.js, etc.)
- Better error messages with install hints for missing packages

#### Enhanced JS Interop
- `generate_import_map()` — Generate ES Module import maps for client-side resolution
- `render_import_map_script()` — Render import map as `<script type="importmap">` tag
- Better npm loader stubs with install hints
- `_generate_npm_loader()` now warns about uninstalled packages

#### Enhanced twm_api_runner.js (v0.8.1)
- `isInstalled()` method on package helper
- `install()` method to add packages to package.json
- Better error messages with `tw install` hints
- Improved `resolve()` with helpful error messages

### Other Changes
- 69 new tests (543 total, all passing)
- `npm_manager.py` — New module for NPM package management
- `react_compat.py` — New module for React compatibility
- `security.py` — New module for security utilities
- CLI now has `install`, `add`, `remove`/`rm`, `list`/`ls` subcommands
- Zero-JS preservation verified for static pages
- All existing v0.8.0 features remain fully backward compatible

### Breaking Changes
- `tw.config` `server.external_packages` is automatically updated when using `tw install` (non-breaking — just adds packages)
- Lib executor Node.js bridge now uses `createRequire` from project root instead of module directory (improves npm package resolution, backward compatible)
- `resolve_module_path()` now checks node_modules for npm packages before trying project root (backward compatible — only affects npm-style package names)

### Migration
- See [MIGRATION_V0.8.1.md](MIGRATION_V0.8.1.md) for step-by-step migration guide
- No code changes required for existing projects — all changes are additive
- Run `tw install` to verify all dependencies are properly installed

---

## v0.8.0 (2026-08-09)


### Major Features

#### Virtual DOM (VDOM)
- TW-native Virtual DOM with diff-and-patch algorithm (~3KB gzipped, no React dependency)
- O(n) diffing with keyed children support
- Batched updates via `requestAnimationFrame`
- Auto-detection: VDOM injected only when page uses state/events
- `render interactive` mode forces VDOM
- New directives: `tw-if`, `tw-else`, `tw-key`
- VDOM public API: `__tw.h()`, `__tw.text()`, `__tw.set()`, `__tw.get()`, `__tw.watch()`
- Server-side HTML is initial VDOM state (no hydration mismatch)

#### Lib System Overhaul
- `import { getData } from "@/lib/data"` syntax (Next.js-style)
- Supports named, default, namespace, and default+named imports
- Module resolution: `@/` prefix, relative paths, extension auto-detection
- Async/await support in `.twm` files
- TypeScript-style type annotations (stripped before execution)
- Client-side functions: `export client function` ships to browser
- Backward compatible with v0.7.x `execute_lib_function` API

#### Server Actions
- `action {}` block syntax in `.tw` pages
- Call server functions from client without API routes
- `__twAction("name", args)` client-side helper
- CSRF + auth validation support
- Rate limiting support

#### Metadata API
- Static `metadata {}` block
- Dynamic `generateMetadata {}` block
- Supports title, description, og-image, twitter-card

#### ISR (Incremental Static Regeneration)
- `revalidate N` directive in page block
- Background page regeneration after N seconds

#### Suspense & Streaming
- `__twSuspense()` client-side helper
- Progressive page loading support

#### Error Boundaries
- `error.tw` catches runtime errors
- Error boundary JS auto-injected

### Other Changes
- `render interactive` and `render dynamic` modes added to compiler
- Reactivity module completely rewritten as VDOM system
- Lib executor completely rewritten with import support
- 74 new tests (474 total, all passing)
- Zero-JS preservation verified for static pages

### Breaking Changes
- `reactivity.py` API changed: `get_reactivity_runtime_js()` → `get_vdom_runtime_js()` (old name kept as alias)
- `lib_executor.py` API: new `execute_lib_function` accepts old signature for backward compat

---

## v0.7.2 (2026-08-09)

- App Router scaffold in `tw create`
- Built-in Icons (60+ SVG, zero dependency)
- README rewrite (App Router focus)
- Detailed App Router guide

## v0.7.1 (2026-08-08)

- Client-side navigation (`link` keyword)
- `generateStaticParams` for dynamic routes
- `route.tw` API handlers

## v0.7.0 (2026-08-08)

- App Router architecture
- Layouts with `children` keyword
- Route groups `(folder)`
- Dynamic routes `[slug]`
- `not-found.tw` support

## v0.6.0 (2026-08-07)

- TW Image component
- Inline JSON data
- Tailwind utility class mapping
- Build cache system

## v0.5.0 (2026-08-06)

- Zero-JS static pages
- Comma syntax for attributes
- Build performance improvements

## v0.4.7 (2026-08-05)

- Lib system (`.twm` files)
- Type safety annotations
- Component classification
