# Changelog

## v0.8.43 (2026-08-10)

### ES6 Import Syntax Support
- **New**: `import { fn } from "@/lib/file"` syntax now works in `.tw` files
- Supports named imports: `import { startCountdown, formatDate } from "@/lib/utils"`
- Resolves `@/` paths to `[home]/` directory (same as `load` directive)
- Auto-detects `.js`, `.ts`, `.mjs` extensions
- Both old and new import syntax work:
  - Old: `import "Navbar"` (component import — unchanged)
  - New: `import { fn } from "@/lib/file"` (ES6 library import)
- ES6 imports tracked in dependency graph for incremental builds

### Example
```tw
import { startCountdown } from "@/lib/countdown"

page {
    title "Countdown"
    render interactive
}

body {
    div { id "countdown" }
    script { startCountdown() }
}
```

## v0.8.43 (2026-08-10)


### Opt-in Sitemap, Robots, RSS
- Sitemap, robots.txt, and rss.xml are now **opt-in** via `tw.config`
- New config options: `sitemap: true`, `robots: true`, `rss: true` (all default OFF)
- No files generated unless explicitly enabled

### Priority: Developer File > Auto-Generated
- If developer places custom `sitemap.xml`, `robots.txt`, or `rss.xml` in `public/` folder or project root, TW uses that file instead of auto-generating
- Developer's custom file always wins over auto-generation
- Build log clearly shows which source was used

### XSL Stylesheet for Sitemap
- Auto-generated `sitemap.xml` includes XSL stylesheet reference
- `sitemap.xsl` auto-generated with dark theme, summary cards, URL table
- Sitemap renders as styled page in browser (like Next.js)
- Custom XSL supported: place `sitemap.xsl` in `public/`

### Auto Image Alt
- New config: `auto_image_alt: true` in `tw.config`
- When enabled, images without `alt` attribute get auto-generated alt from filename
- Takes filename, replaces hyphens/underscores with spaces, truncates to 8 chars
- Example: `/img/my-profile-photo.jpg` → alt="my profi"

### Documentation
- New: `docs/sitemap-robots-guide.md` — config options, priority, XSL
- New: `docs/public-folder-guide.md` — static files, what belongs where

## v0.8.43 (2026-08-10)


### Bug Fix — Sitemap/Robots/RSS Conflict Resolution
- **Bug**: TW `tw build` would blindly overwrite `sitemap.xml`, `robots.txt`, and `rss.xml` in `dist/` — even if the developer had placed their own custom versions
- **Fix**: TW now checks for developer-provided files in `public/` directory or project root before generating
  - If developer provided a custom `robots.txt` → TW copies it to `dist/` (no overwrite)
  - If developer provided a custom `sitemap.xml` → TW copies it to `dist/` (no overwrite)
  - If developer provided a custom `rss.xml` → TW copies it to `dist/` (no overwrite)
  - If no custom file found → TW auto-generates as before
- **Build log**: Now shows whether each file was auto-generated or developer-provided:
  - `✅ sitemap.xml: auto-generated`
  - `✅ sitemap.xml: using developer file (public/sitemap.xml)`

### Test Results
- Developer custom robots.txt preserved ✅ (GoogleBot, Disallow: /admin)
- Developer custom sitemap.xml preserved ✅ (custom-page URL)
- Auto-generated when no custom file ✅ (10 URLs, TW default robots)
- 610 tests pass, 9 skipped, 0 failures

## v0.8.43 (2026-08-10)


### Critical Bug Fix — Dev Server Not Applying Layouts
- **Bug**: `tw dev` was not applying `layout.tw`, components (Navbar, Footer, Button, Card), or CSS (`style.tss`) when rendering pages
- **Root cause**: Dev server's `compile_match_response()` used `compile_file_pipeline()` which skips `compose_nested_layouts()` — the function that wraps page content in layout HTML, loads components, and injects CSS
- **Fix**: Added App Router layout composition path in `compile_match_response()` — when `app_router=True` and `layout_files` are present, dev server now uses the same `compose_nested_layouts()` code path as `build_one_page()` (the build pipeline)
- **Impact**: Dev server now renders pages identically to build output — navbar, footer, components, CSS, theme variables all work in `tw dev`

### Also Fixed (from v0.8.43)
- Tree shaker false positive: `shake_project()` now scans inline component references (`Navbar {}`, `Button {}`) instead of only checking `import` directives
- Sitemap dynamic route URLs: `route_from_dynamic_page()` now handles `:param` format in addition to `[param]` format

### Test Results
- Dev server simulation: navbar ✅, footer ✅, CSS ✅, components ✅, hero ✅, cards ✅, buttons ✅
- Build: 10 pages (5 static + 5 dynamic blog posts) ✅
- 610 tests pass, 9 skipped, 0 failures

## v0.8.43 (2026-08-10)


### Breaking Change — Starter Template Redesign
Complete rewrite of the `tw create` starter template to use proper App Router architecture:

**Old template (legacy):**
- Plain pages with inline HTML
- No reusable components
- No dynamic routes
- No blog example
- Basic CSS without dark mode variables
- Root-level `components/` directory (unused)

**New template (App Router):**
- Reusable components: `Navbar.tw`, `Footer.tw`, `Button.tw`, `Card.tw`
- Components used in layout and pages via `<ComponentName {}>` syntax
- Dynamic blog with `[slug]` route + `generateStaticParams` + `posts.json`
- 5 sample blog posts generated from JSON at build time
- Modern CSS with CSS variables for dark/light themes
- Responsive design with `@media` queries
- Navbar with sticky positioning + backdrop blur
- Hero section with gradient text
- Feature grid with hover effects
- Blog index listing with card-style links
- Blog post detail pages
- Contact form with styled inputs
- Counter with reset button
- 404 page using Button component

### Bug Fixes
- Tree shaker false positive: `shake_project()` now scans inline component references (`Navbar {}`, `Button {}`) instead of only checking `import` directives — fixes "Unused components" warning when components are used directly in HTML
- Sitemap dynamic route URLs: `route_from_dynamic_page()` now handles `:param` format (Express-style) in addition to `[param]` (Next.js-style) — dynamic URLs show actual slug values instead of `:slug` placeholder

### Test Results
- `tw create` + `tw build` produces 10 pages (5 static + 5 dynamic blog posts)
- All components render correctly (Navbar, Footer, Button, Card)
- Sitemap contains all 10 URLs with correct paths
- No warnings, no errors

## v0.8.43 (2026-08-10)


### Bug Fixes
- Sitemap.xml now includes dynamic route URLs (was only showing static routes)
- Dynamic route URLs in sitemap show actual slug values (was showing `:slug` placeholder)
- `route_records_for_build()` now uses `generateStaticParams` items (was using `load_dynamic_items` only)
- `route_from_dynamic_page()` handles `:param` format (was only handling `[param]` format)

### Verified Improvements (from v0.8.43)
All 6 improvements tested and verified with real project:
1. React auto-bundle — verified: always bundles from node_modules when installed
2. esbuild auto-install — verified: auto-installs when complex package detected
3. Error overlay — verified: syntax error shows line number, column, suggestion
4. Scoped CSS — verified: `.btn` → `.btn[data-tw-abc123]`, @keyframes preserved as global
5. Incremental build — verified: `get_changed_files()` tracks mtime
6. Image optimization — verified: `image` tag adds lazy loading, srcset, sizes, decoding=async

### Dynamic Route Test (50 pages)
- Created blog with `[slug]/page.tw` + `generateStaticParams "posts.json"`
- 50 blog posts generated from JSON data
- All 50 pages built successfully: `dist/blog/[slug]/post-1/index.html` through `post-50`
- Sitemap.xml contains all 55 URLs (5 static + 50 dynamic)
- Blog index page lists all 50 posts with correct links

## v0.8.43 (2026-08-10)


### 6 Major Improvements

#### 1. React Auto-Bundle from node_modules
- React is now ALWAYS bundled from node_modules when installed (like Next.js)
- CDN is only used as a last-resort fallback when React is not installed
- The `react_cdn` config option is deprecated — intelligent detection replaces it
- No more hardcoded React version — uses YOUR installed version

#### 2. esbuild Auto-Install
- When a complex npm package needs bundling and esbuild is not available, TW automatically runs `npm install esbuild`
- No manual `tw install --save-dev esbuild` needed anymore
- Falls back to IIFE bundler only if auto-install fails

#### 3. Dev Server Error Overlay
- Syntax errors in `.tw` files now show a Vite-style red error overlay in the browser
- Shows source code with line numbers, error line highlighted
- Includes suggestions when available
- Auto-reload on fix via SSE

#### 4. Scoped Component CSS (CSS Modules)
- `.tss` files next to `.tw` components are automatically scoped
- `Button.tss` styles only apply to `Button.tw` — no global pollution
- Uses data attributes: `.btn[data-tw-abc123]`
- `@keyframes` and `:root` are preserved as global

#### 5. Incremental Build
- Only changed pages (and their dependents) are rebuilt
- Tracks file modification times via `get_changed_files()`
- Layout/component/.tss changes trigger dependent page rebuilds
- Faster builds for large sites

#### 6. Image Optimization
- `image` tag → optimized: lazy loading, responsive srcset, WebP, async decoding
- `img` tag → normal `<img>`, no optimization
- Developer chooses: use `image` for photos, `img` for icons/small images
- `image { src "/img/photo.jpg" alt "Photo" width 800 height 600 }`

## v0.8.43 (2026-08-10)


### Improved Error Messages
- `tw install` / `tw remove` — When Node.js is not found, now shows OS-specific install instructions with exact commands:
  - **Termux/Android**: `pkg install nodejs`
  - **Debian/Ubuntu**: `sudo apt install nodejs npm` (plus nvm instructions)
  - **Fedora/RHEL**: `sudo dnf install nodejs npm`
  - **Arch Linux**: `sudo pacman -S nodejs npm`
  - **Alpine Linux**: `apk add nodejs npm`
  - **macOS**: `brew install node` (plus nvm and download links)
  - **Windows**: `winget install OpenJS.NodeJS` (plus Chocolatey and download links)
  - **Other Linux**: nvm install instructions with download link
- All three error paths now use `_get_node_install_help()` instead of a one-line generic message

## v0.8.43 (2026-08-10)

### Documentation Overhaul
- All 200+ markdown files updated with correct `pip install tw-framework` (was `pip install -e .`)
- All `render` mode references updated: now lists `static`, `server`, `edge`, `interactive`, `dynamic` (was "only static valid")
- All `tw init` references replaced with `tw create` (App Router CLI)
- All `[home]/pages/` path references replaced with `[home]/` (App Router structure)
- All "NOT a JavaScript/Node framework" notes updated to reflect npm package support
- Old version references (0.1.0, 0.3.4) updated to 0.8.355
- npm role updated: "only for .twm" → "used for client-side packages via tw install AND .twm"
- LLM txt files (llms.txt, llms-full.txt, llms-full_part1.txt) fully rewritten for v0.8.43
- GitHub URL: `https://github.com/ffakraj-ui/twlang` (consistent across all files)

### Bug Fixes (carried forward from v0.8.1–v0.8.435)
- Route path double-nesting fix (sitemap.xml, __TW_DATA__, HTML metadata)
- NPM package manager detection (was dead code, now live)
- React loader script (both branches were identical, now version-aware)
- ReactCompat wired to build pipeline via _inject_react_integration()
- LOAD_RE regex fix (on:load was matched as load directive)
- Counter template bare string fix
- Duplicate deploy metadata call removed
- Client bundler: transitive deps, esbuild fallback warning, topological sort
- Module boundaries: fetch() is client-safe, .twm always SERVER

## v0.8.435 (2026-08-10)

### Bug Fixes

#### Route Path Double-Nesting (Critical)
- `route_path_from_page_info()` in `compiler.py` — App Router pages had `rel_dir` and `name` both set to the same value (e.g. "about"), producing `/about/about` in sitemap.xml, `__TW_DATA__` JSON, and HTML comment metadata. Fixed by checking `url_path` first and skipping duplicate `name` append for App Router pages.
- `route_from_static_page()` and `route_from_dynamic_page()` in `framework.py` — Same double-nesting bug existed in these separate functions used by sitemap.xml and RSS generation. Fixed with the same `url_path`-first + duplicate-detection logic.
- All three route path generators now produce consistent, correct URLs: `/about`, `/contact`, `/counter`, `/react` (not `/about/about` etc.)

#### Sitemap.xml / RSS Feed
- Sitemap.xml now lists correct clean URLs (`/about` instead of `/about/about`)
- RSS feed entries also fixed (same root cause)

#### README Quick Start Fix
- `pip install tw-framework` (dev-only) replaced with `pip install tw-framework` (PyPI public install)

#### Previous v0.8.1 Fixes (carried forward)
- `detect_package_manager()` — was dead code, now actually used by `install_packages()`, `remove_packages()`, `ensure_dependencies()`
- `get_react_loader_script()` — both branches were identical, now returns different output based on installed React version and CDN/bundle mode
- `ReactCompat` class — was never imported during build, now wired to build pipeline via `_inject_react_integration()` in both `render_html()` and App Router modular pipeline
- `LOAD_RE` regex — `on:load` was matched as `load` directive, fixed with negative lookbehind
- Counter template — bare strings `"+"`/`"-"` replaced with `text "+"`/`text "-"`
- Duplicate `generate_deploy_metadata()` call removed from `cli.py`

## v0.8.2 (2026-08-10)

### Bug Fixes
- Route path double-nesting fix (same as v0.8.435, initial attempt)

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
