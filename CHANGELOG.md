# Changelog

All notable changes to TW Framework are documented here.


## [0.7.0] — 2026-08-09

### 🚀 Major: App Router System

TW Framework now supports Next.js-style App Router architecture — layouts are
**TW components**, not raw HTML templates. Layouts nest automatically based on
directory structure.

### Added
- **App Router module** (`tw_framework/app_router.py`) — route discovery, layout
  resolution, URL matching, and output path generation for the new file-system
  based router.
- **`children` keyword** — use `children` inside `body { }` or any element block
  to mark where page content gets injected in a layout. Replaces the old
  `{slot}` HTML-template placeholder.
- **Nested layouts** — `compose_nested_layouts()` walks the layout chain
  (root → innermost) and composes them around the page body. Each layout can
  have its own `head { }`, `load` directives, and stylesheets.
- **Route groups** `(folder)` — parentheses-wrapped folders are excluded from
  the URL but participate in layout nesting. E.g. `(main)/layout.tw` wraps all
  pages inside `(main)/` without affecting URLs.
- **Dynamic routes** `[slug]` — folder names in square brackets become dynamic
  URL segments. E.g. `blog/[slug]/page.tw` → `/blog/:slug`.
- **Catch-all routes** `[...slug]` — catch-all dynamic segments.
- **`layout.tw` as TW component** — `load_layout_ast()` parses layout files
  using the same `build_tw_ast` pipeline as pages. Layouts can import
  components, stylesheets, and use TW syntax normally.
- **`loading.tw` / `not-found.tw` / `error.tw`** — route-level special files
  discovered by the App Router (output-ready, full runtime integration pending).
- **40 new tests** in `tests/test_app_router.py` covering segment classification,
  URL building, layout discovery, route matching, children parsing, and nested
  layout composition.

### Changed
- `discover_pages()` now detects App Router structure first
  (`has_app_router_structure()`). If `[home]/page.tw` or `[home]/layout.tw`
  exists, it uses `app_router.discover_routes()` instead of the legacy
  `[home]/pages/` walk. Falls back to legacy mode automatically.
- `build_one_page()` now checks `page_info["app_router"]` flag and routes to
  `compose_nested_layouts()` for layout composition instead of the old
  `render_html()` → `apply_layout_template()` string-replace pipeline.
- `parse_child_statement()` and `parse_element_block()` now recognize the
  `children` keyword and create a special `ElementNode(tag="children")` marker.
- `render_elements_html()` renders `children` nodes as `{children}` text markers
  which are later replaced by the actual page content during layout composition.

### Backward Compatible
- Legacy `[home]/pages/` + `[home]/layouts/` projects continue to work unchanged.
  The App Router is only activated when the new structure is detected.
- Old `{slot}`, `{title}`, `{head}`, `{styles}`, `{scripts}` HTML-template
  layouts still function for legacy projects.

### Migration
See `MIGRATION_V0.7.0.md` for a step-by-step guide to migrate from the legacy
pages/layouts structure to the new App Router structure.

## [0.6.4] — 2026-08-09

### Fixed
- **TSS multi-declaration parsing**: Fixed `_split_tss_body_items` to properly split
  multiple CSS declarations on the same line separated by semicolons (e.g.
  `margin 0; padding 0; box-sizing border-box`). Previously only the first
  declaration was parsed and the rest were silently dropped or merged incorrectly.
- Added `_split_tss_line` helper that respects parentheses and quotes when splitting.

### Changed
- Layout files (`[home]/layouts/*.tw`) must be HTML templates with `{slot}`, `{head}`,
  `{title}`, `{styles}`, `{scripts}` placeholders — NOT `.tw` page files with
  `page {}` / `head {}` / `body {}` blocks. The compiler reads layouts as raw
  text and performs string replacement, so a `.tw`-formatted layout would leak
  raw source code into the output HTML.

## v0.6.3 (Literal Braces Fix)

### Fixed
- **Fixed**: TW2001 "Undefined symbol" warnings are no longer generated for
  element TEXT content.  Documentation pages that show code examples containing
  braces like ``{ to, subject, message }`` or ``{variable}`` no longer break
  ``--prod`` builds.
- **Root cause**: The semantic analyzer was treating ``{...}`` inside element
  text (``p "..."``) as TW variable interpolation, producing TW2001 warnings for
  undefined symbols.  In ``--prod`` mode these warnings are treated as errors,
  causing the build to fail.
- **Fix**: Two-part solution:
  1. Added `_is_likely_literal_text()` heuristic — suppresses TW2001 for
     expressions containing commas (JS destructuring), JS keywords, or more
     than 2 space-separated tokens.
  2. Removed `analyze_interpolated_text()` call for `ElementNode.text` —
     element text is user-facing content, not code.  `{var}` in text is either
     real interpolation (var is defined → works) or literal text (var is not
     defined → shows literal ``{var}``).  Neither case should produce a warning.
- **Attributes, styles, events, and conditions are still analyzed** — those are
  code contexts where undefined variables are real bugs.
- **311 tests passing, 0 failures**


## v0.6.2 (PyPI Packaging)

- Updated `pyproject.toml` for PyPI publishing
- Version bump for package distribution



## v0.5.2 (Parallel Compilation Update)

- **Improved: Parallel page compilation** — bounded worker pool with `--workers N` option, automatic CPU-aware default, small-project sequential fallback (≤3 pages), thread-safe shared state (`_LIB_MODULES` lock added), extended build statistics (`workers`, `pages_scheduled`, `parallel_tasks`, `max_concurrent_workers`, `build_mode`), deterministic output verified (workers=1 vs workers=4 produce identical output), better error handling with worker failure cleanup. Existing `--workers`, `--force`, `--clean` all work correctly with parallel compilation. Cache hits skip compilation workers entirely.

## v0.5.2 (Original)

- **Added: TW Image system** — first-party image optimization component inspired by Next.js next/image but implemented as an original TW-native architecture. Usage: `import "tw/image"` then `Image { src "/hero.jpg" width 1200 height 800 alt "Hero" }`. Features: automatic WebP/AVIF optimization (when Pillow available), responsive srcset generation, lazy loading by default, priority loading for hero images, quality control (`quality 80`), explicit `unoptimized` escape hatch, `original_format` option, width/height for CLS prevention, image caching with incremental build integration, and full Zero-JS compatibility (static Image adds 0 KB framework JS). Normal `img { src "..." }` tags remain completely unchanged. Package at `tw_framework/tw_image/` with extensible `tw/<module>` namespace architecture for future modules (tw/font, tw/script, tw/link, etc.).

## v0.6.0

- **Added: Zero-JS output for static pages** — TW's biggest differentiator. When a page has no `state`, no events, no router keys, no client components, no TWM modules, no on-load inits, and no reactivity, the compiler automatically skips ALL framework JavaScript — `__TW_DATA__` JSON blob, `__TW__` hidden div, router/search/reactivity runtimes, and code-splitting chunks. The output is pure HTML + CSS with 0 KB of framework JS. User-written `script { ... }` blocks are NOT framework JS and are still included. This is fully automatic — no config needed. Pages with `let`, `each`, `if`, and data interpolation still qualify for Zero-JS because those are resolved at build time.

- **Added: Comma-separated syntax in element and component blocks** — you can now write `span { class "badge", "text" }` or `a { class "btn", href "/search", "Search Now" }` instead of putting each attribute and text on separate lines. The comma acts as a separator between attributes and the text content. This is fully backward-compatible — the old multi-line syntax still works.
- **Fixed: Raw `script { ... }` blocks now allowed by default** — previously raw inline script blocks were disabled by default, causing TW1000 errors on pages with client-side JavaScript. The `allow_raw_script` config option now defaults to `True`. Users who want to disable raw scripts can set `allow_raw_script: false` in `tw.config`.


## v0.5.0

- **Fixed: `tw build --clean` now properly invalidates the incremental cache** — previously `--clean` removed the `dist/` output directory but did not clear `.tw/cache/`, so the subsequent build would still find old cache entries and report `(cache hit)` instead of recompiling from scratch. `clean_project_outputs()` now calls `IncrementalCache.clear()` to wipe all cached page signatures before the build starts.
- **Fixed: `tw build --force` now bypasses the incremental cache-hit check entirely** — previously `--force` was passed to `BuildOptions` but the cache-hit check ran *before* `should_rebuild_page()` was consulted, so pages could still be skipped based on stale cache signatures even when `--force` was set. The cache lookup is now wrapped in `if not force:` so that `--force` guarantees every page is recompiled.
- **Added: Inline JSON in `let` statements** — `let` now supports inline JSON objects and arrays directly: `let items = [{"id": 1, "name": "First"}, {"id": 2, "name": "Second"}]`, `let config = {"key": "value", "num": 42}`, `let matrix = [[1, 2], [3, 4]]`. Previously the parser treated `{` as a block-opening token and failed with TW1000. The `collect_until_eol` function now tracks brace depth separately from bracket depth, correctly distinguishing JSON object literals from TW block syntax.
- **Added: Tailwind CSS utility classes in `.tss` files** — TSS files now support Tailwind utility classes alongside normal TSS syntax. Write `flex items-center gap-2 p-4` or `display flex; align-items center; gap 8px` — both work. Supports spacing (p-*, m-*, gap-*), colors (bg-red-500, text-blue-600), flexbox (flex, items-center, justify-between), grid (grid-cols-3), typography (text-xl, font-bold), shadows, borders, rounded corners, positioning, and more. Falls back to normal TSS parsing when not all words are Tailwind classes.
- **Fixed: `create_base_context` no longer overwrites `let` variables** — if a `let` variable named `config`, `site`, or `env` is defined, it takes priority over the site config defaults.


## v0.4.7

- **Added: Lib directory system** — shared server-side utility functions via `lib/` folder (`.twm` files). Load with `load @./lib/file.twm` and call in `let` statements: `let app = getApps("whatsapp")`. Functions execute at build time via Node.js bridge, results baked into static HTML. Works with type safety annotations. See `docs/21-lib-directory.md`.


## v0.4.5

- **Added: Type safety / type annotations** — `let` variables and `state` block entries now support optional TypeScript-style type annotations: `let count: number = 5`, `let name: string = "World"`, `state { count: number = 0 }`. The compiler validates values against declared types at parse time and during semantic analysis, raising clear errors like `Type error: count is annotated as number but got string.` on mismatch. Valid types: `string`, `number`, `boolean`, `array`, `object`, `null`, `any`. Annotations are optional — existing `.tw` files work unchanged.

## v0.4.4

- **Added: LSP (Language Server Protocol) server** — `tw_framework/lsp_server.py` provides autocomplete and live diagnostics for `.tw` and `.tss` files.
- **Added: VS Code extension updated** — `vscode-tw/` now launches the LSP server for autocomplete, hover info, and real-time error checking.
- **Added: ACode (mobile editor) plugin** — registers `.tw`, `.twm`, `.tss` file extensions for syntax highlighting and LSP integration.
- **Added: Deployment documentation** — `DEPLOYMENT.md` with platform-specific setup for Vercel, Netlify, Cloudflare Pages, and GitHub Pages.
- **Updated: README** — added project structure, VS Code extension, and deployment guide sections.

## v0.4.3

- **Fixed: `--prod` build broken HTML references** — CSS/JS filenames were hashed but `<link>` and `<script>` references in HTML were not updated, causing 404s and broken styles on production builds.
- **Fixed: Multi-line CSS values in `.tss`** — TSS parser was splitting on every newline, breaking multi-line values like `background-image: linear-gradient(...), linear-gradient(...);` into `true`.
- **Security: `os.environ` no longer leaked to page render context** — only env vars explicitly allow-listed in `tw.config` via `env: public: "VAR_NAME"` reach generated HTML.
- 
## [0.6.1] — 2026-08-09

### 🚀 Full-Stack Architecture — Major Upgrade

TW Framework now scales from simple static pages to complex production web
applications while preserving its HTML-first, Zero-JS philosophy. Every new
capability is **opt-in through dependency analysis** — static pages remain
static.

#### Phase 1: Foundations
- **Module Boundary System** (`module_boundaries.py`) — SERVER/CLIENT/SHARED
  classification for all imports with TW2000-series error codes for invalid
  cross-boundary imports
- **JS/NPM Ecosystem Interop** (`js_interop.py`) — npm package resolution,
  client-side bundling, server-only package isolation, dynamic import detection
- **Client Component Model** (`component_classifier.py`) — auto-classification
  of components as STATIC/SERVER/CLIENT/SHARED based on content analysis
- **Enhanced Dependency Graph** — build-time analysis of what each page needs
- **Modular Runtime Loader** (`runtime_loader.py`) — per-page JS chunk
  generation, loads only needed capabilities (~1KB base + per-feature chunks)

#### Phase 2: State & Routing
- **Global State Management** (`tw/state`) — reactive stores with subscriptions,
  derived state, cleanup, server/client separation, optional persistence
- **Client-Side Router** (`tw/router`) — SPA navigation, dynamic routes,
  prefetching, lazy loading, loading/error states, browser history
- **Enhanced Code Splitting** — per-route chunks, per-component chunks,
  per-npm-package chunks, content-hashed filenames

#### Phase 3: Forms, Fetch, Server Actions
- **Advanced Form System** (`tw/form`) — form state, field state, validation
  (required/email/min/max/pattern), async validation, multi-step forms,
  progressive enhancement, Zod integration via JS interop
- **Data Fetching** (`tw/fetch`) — server-side fetch with caching,
  deduplication, revalidation; client-side fetch with loading/error states
- **Server Actions** (`server_actions.py`) — secure invocation boundary with
  CSRF protection, authentication, argument validation, rate limiting

#### Phase 4: Realtime & Auth
- **Realtime Architecture** (`tw/realtime`) — WebSocket connections with
  auto-reconnect, event handlers, channel broadcasting, SSE fallback,
  state integration
- **Authentication/Authorization** (`tw/auth`) — session management with
  secure HTTP-only cookies, CSRF tokens, route protection, role-based
  access control, permission checks, OAuth/OIDC architecture

#### Phase 5: Error Boundaries & DX
- **Error Boundaries** (`error_boundaries.py`) — 404/500 error pages,
  development error details with stack traces, production-safe messages,
  client-side error boundary runtime, loading state UI
- **Ecosystem Packages**: `tw/font` (font optimization), `tw/metadata`
  (SEO, Open Graph, Twitter Cards, JSON-LD, sitemaps)

#### Progressive Enhancement Matrix
| Page Type | HTML | CSS | JS |
|-----------|------|-----|----|
| Static | ✅ | ✅ | ❌ |
| Interactive | ✅ | ✅ | state only |
| Dashboard | ✅ | ✅ | state+router+auth |
| Full-stack | ✅ | ✅ | all needed runtimes |

#### New Packages (all under `tw_framework/`)
- `module_boundaries.py` — import classification & enforcement
- `js_interop.py` — npm package resolution & bundling
- `component_classifier.py` — component auto-classification
- `runtime_loader.py` — per-page runtime chunk generation
- `server_actions.py` — secure server action invocation
- `error_boundaries.py` — error pages & boundaries
- `tw_state/` — reactive stores (store.py, runtime.py)
- `tw_router/` — client routing (router.py, runtime.py)
- `tw_form/` — form system (form.py, validation.py, runtime.py)
- `tw_fetch/` — data fetching (fetch.py, runtime.py)
- `tw_realtime/` — realtime (client.py, server.py, runtime.py)
- `tw_auth/` — auth (session.py, middleware.py, client.py, runtime.py)
- `tw_font/` — fonts (loader.py)
- `tw_metadata/` — metadata (meta.py)

#### Tests
- `test_module_boundaries.py` — boundary classification & validation
- `test_js_interop.py` — npm package resolution & server isolation
- `test_component_classifier.py` — auto-classification
- `test_runtime_loader.py` — capability analysis & chunk generation
- `test_tw_state.py` — stores, subscriptions, derived state, cleanup
- `test_tw_router.py` — route resolution, dynamic params, link rendering
- `test_tw_form.py` — validation, form state, submission
- `test_tw_fetch.py` — caching, deduplication
- `test_tw_realtime.py` — connection management, broadcasting
- `test_tw_auth.py` — sessions, CSRF, route protection, roles
- `test_server_actions.py` — action registration, validation, execution
- `test_error_boundaries.py` — error page rendering, dev/prod modes

---

## [0.4.1]

### Security

- **Env vars were fully exposed to every page render.** `context["env"]`
  and `context["request"]["env"]` both dumped the entire `os.environ`
  (every server secret — API keys, DB passwords, tokens) into the
  interpolation context used to render `.tw` pages. Writing `{env.X}`
  anywhere in a page — even by accident — would bake the real value into
  the static HTML shipped to every visitor. Pages now only see vars
  explicitly allow-listed via `env: public: "A, B, C"` in `tw.config`;
  everything else stays server-side only. Default (nothing declared) now
  exposes nothing, which is a breaking-but-necessary change for any
  project that was relying on the old unrestricted behavior.

## [0.4.0]

### Added

- **Typed env validation.** `env: types: "PORT:number, API_URL:url, DEBUG:boolean"`
  in `tw.config` now validates the *shape* of a value, not just whether
  it's present. Runs alongside `env: required:` at dev-server startup.

## [0.3.9]

### Fixed

- **Tree-shaking false-positive "file not found" warning**, seen on
  every build (`Tree shaking failed: load: file not found for
  @../style/site.tss`). `shake_project` resolved every page's relative
  `load @...` paths against the fixed `HOME_DIR` instead of each page's
  own directory, so any page not sitting directly at the project root
  resolved its relative imports one level off. Now resolves relative to
  each page's actual directory, matching how the real compiler already
  did it elsewhere. Also made one broken page's resolution failure no
  longer abort tree-shaking for the whole project.
- Removed a dead, byte-for-byte duplicate `command_doctor` definition in
  `cli.py` (the second definition silently overwrote the first — ~20
  lines of dead code).

### Added

- **`tw doctor` gained 4 new checks:** required/typed env vars, declared
  WebSocket routes, whether `.gitignore` excludes auto-generated
  `*.tw.json` cache files, and whether the default dev port (3000) is
  free.

## [0.3.8]

### Added

- **Native WebSocket support**, stdlib-only (no external dependency).
  Full RFC 6455 handshake and frame encode/decode implemented from
  scratch and verified against the spec's official test vector. Add a
  Python file under `[home]/ws/<name>.py` exporting `on_connect(conn)`
  and it's live at `/ws/<name>` — `conn.send_text()`, `conn.send_bytes()`,
  `conn.close()`, and `for message in conn:` to receive.
- **Env var presence validation.** `env: required: "A, B, C"` in
  `tw.config` — `tw dev` warns clearly at startup if any are missing
  from `.env`/`.env.development`/`.env.local`/the shell environment,
  instead of failing silently later at runtime.

## [0.3.7]

### Added

- Cloudflare-style click-to-reveal IP footer (`Your IP: X.***.***.Y`,
  click to unmask) added to all error pages — 404s, client errors, and
  compile errors alike.

## [0.3.6]

### Changed

- Error pages redesigned to a minimal, centered, Vercel/Next.js-style
  layout (plain background, no alarming red gradient) for 404s. Genuine
  compile/client errors keep a cleaner light card with a dark code block
  so the error detail is still easy to read.

## [0.3.5]

### Fixed

- 404 pages displayed the label **"TW Compile Error"** — misleading,
  since a normal "this route doesn't exist" case is not a compile error
  and nothing is actually broken. `render_error_html` now derives the
  label from the actual status code (`TW Not Found` for 404, `TW Client
  Error` for other 4xx, `TW Compile Error` only for 5xx).


## [0.3.4]

### Fixed
- Dynamic-page incremental cache entries are stored as a list (one per generated slug) rather than a dict. The cache-check code assumed a dict shape for every page and crashed with `'list' object has no attribute 'get'` when building dynamic routes. It now guards for the dict shape and safely falls through to a full rebuild otherwise.

## [0.3.3]

### Fixed
- The `response { header ... }` / `response { cookie ... }` block inside a middleware rule used the same greedy line-parsing bug as the top-level `header`/`cookie` keys (fixed in 0.2.5), but this occurrence was missed. Two values on one line (`header "X" "Y"`) inside a `response { }` block now parse correctly instead of crashing.

## [0.3.2]

### Fixed
- **Decimal number tokenization** — numeric literals like `3.14` were split into three tokens (`3`, `.`, `14`) because `.` was always treated as a standalone operator. Any bare decimal value in a `.tw` file was corrupted on output (e.g. `data-ratio 3.14` rendered as `data-ratio="3 . 14"`).
- **`data-tw-on` / `data-tw-bind` JSON corruption** — these framework-generated attributes (holding JSON for reactive event handlers) were being passed back through the general string-interpolation step, which mis-parsed the leading `{` as a template expression and re-serialized the value as a Python dict repr (single-quoted keys) instead of valid JSON. This broke `on:click` handlers on any element that also had other attributes. Framework-generated `data-tw-*` attributes are no longer re-interpolated.
- **Boolean attribute rendering** — a bare `true`/`false` value rendered as Python's `str(True)` → `"True"` (capital T), which is not valid for HTML/JS boolean conventions. Booleans now render as lowercase `"true"` / `"false"`.

## [0.3.1]

### Fixed
- **Major:** single-line elements with multiple properties (e.g. `a { href "/" target "_blank" text "Home" }`) had every property after the first swallowed into the first property's value, because the property-value parser only treated a quoted string as "complete" when directly followed by a newline or `}`. On the same line, the next property name looked like a continuation of the previous value and was consumed by it. A quoted string value is now always treated as complete on its own — this was likely the single highest-impact bug found, since single-line elements are an extremely common way to write markup.

## [0.3.0]

### Fixed
- `.tss` stylesheet values wrapped in quotes (needed for multi-word CSS values like `animation "pulse 2s infinite"` or `transform "translateY(-6px)"`) kept their literal quote characters in the compiled CSS output, producing invalid CSS (`animation: "pulse 2s infinite";`). Quoted `.tss` values are now unwrapped before being written out.

## [0.2.9]

### Fixed
- The dev-mode search index builder's HTML-to-text extractor (`strip_html_to_text`) had double-escaped regex patterns (`\\s` instead of `\s`) for stripping `<script>`/`<style>` blocks. Because the patterns never actually matched, raw inline JavaScript and the page's `__TW_DATA__` JSON blob leaked into every search result's excerpt text.

## [0.2.8]

### Fixed
- `pyproject.toml` only listed Python packages under `[tool.setuptools]`, so the `twm_api_runner.js` asset file (required to execute `.twm` API routes) was never included in the built wheel. Every API route failed with `Missing twm_api_runner.js (framework installation is incomplete)` on a fresh `pip install`. Added `[tool.setuptools.package-data]` to include `*.js` files.

## [0.2.7]

### Fixed
- Reactive directives `on:click` / `bind:value` were never usable: the tokenizer split `on:click` into three tokens (`on`, `:`, `click`) since `:` was always a standalone operator, and even after fixing the tokenizer, the property classifier didn't recognize `on:` / `bind:` / `show:` / `tw-*` prefixed names as valid attributes (reactivity.py explicitly expects these). Both the tokenizer and the property classifier were fixed.
- The default `tw create` starter project's `search` page relies on a raw `script { ... }` block, which is blocked by default for safety. Enabled `allow_raw_script: true` in the starter's `tw.config` so the example works out of the box.

## [0.2.6]

### Fixed
- Kebab-case attribute names (`aria-label`, `data-foo`) were split into multiple tokens by the tokenizer, since `-` was always treated as a standalone operator. This broke any accessibility or `data-*` attribute — including in the default `tw create` template itself (`ThemeToggle.tw`'s `aria-label`).

## [0.2.5]

### Fixed
- **Middleware crash:** the default `middleware.tw` template's `auth "cookie" "redirect"` and `header "name" "value"` directives put two values on one line. The value parser used a line-greedy collector for the first value, which consumed both values, leaving nothing for the second and crashing every request with `RuntimeError: Expected value token`. This affected every project created with `tw create`, since the crashing directives were in the default template.
- **String quote corruption:** parsed string literal values (e.g. `match "/dashboard/**"`) retained their literal surrounding quote characters instead of being unquoted, so middleware path-matching rules like `match` never matched real request paths.
- Removed a duplicate `doctor` subcommand registration in the CLI that crashed argument parsing (`conflicting subparser: doctor`).
- Fixed a diagnostic-formatting pipeline mismatch across three files (`compiler.py`, `diagnostics.py`, `error_formatter.py`) where the rich `Diagnostic` fields the error formatter expected had been stripped from the simplified `Diagnostic` dataclass. Any compiler error — valid or not — crashed instead of showing a readable message.
- `pyproject.toml` only declared the top-level `tw_framework` package, so the `tw_framework.adapters` subpackage (Vercel/Netlify/Cloudflare deploy adapters) was missing from the installed package, breaking every deploy-related import.
