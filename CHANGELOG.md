# Changelog

## v0.9.07 (2026-08-11)

### Credits Cleanup + PyPI Republish

- Removed incorrect contributor credits from all files (CHANGELOG, PROGRESS,
  README, RUNTIMES). Original issue reporter only contributed 5 bug reports
  early on; all subsequent work (v0.8.49 through v0.9.06) was done by the
  project maintainer.
- README.md rewritten — clean v0.9.06 content, removed stale v0.8.47 docs.
- PROGRESS.md updated — complete status tracker with accurate attribution.
- Version bumped to 0.9.07 for PyPI republish (0.9.06 already on PyPI).

---

## v0.9.06 (2026-08-11)
 (2026-08-11)

### Edge = Pure V8, QuickJS Removed

- **QuickJS completely removed** — ab sirf V8 (py_mini_racer) hai. Koi
  QuickJS fallback nahi. Edge runtime = V8 isolate, point.

- **`runtime = "edge"` = pure V8** — real V8 isolate (same engine jo
  Google Chrome aur Next.js Edge Runtime use karta hai). No QuickJS,
  no Python exec, no compromise.

- **What was removed:**
  - QuickJS engine detection
  - QuickJS Context setup
  - QuickJS host function injection (add_callable)
  - QuickJS bootstrap code (_JS_BOOTSTRAP)
  - All QuickJS references in comments and docstrings

- **What remains (pure V8):**
  - SHA-256 in pure JavaScript
  - HMAC-SHA256 in pure JavaScript
  - HTTP fetch via multi-pass yield bridge
  - Environment variables injection
  - In-memory KV storage
  - tw.crypto.random(), tw.crypto.uuid()

- **Runtime registry:**
  - `edge` → EdgeV8Runtime (V8 only)
  - `edge-v8` → alias for edge
  - `edge-py` → legacy Python fallback
  - `python`, `nodejs`, `wasm` → unchanged

- **Install requirement:** `pip install py_mini_racer` (V8 engine)

---

## v0.9.05 (2026-08-11)
 (2026-08-11)

### Edge Runtime: Python → V8 Based (Huge Update)

- **`runtime = "edge"` is now V8/QuickJS-based** — Edge runtime ab Python
  exec() nahi use karta. Seedha V8 isolate ya QuickJS sandbox me real
  JavaScript execute hota hai. Next.js Edge Runtime jaisa.

- **`edge-v8` merged into `edge`** — ab `edge` hi V8 runtime hai.
  `edge-v8` alias ke roop me kaam karta hai (backward compat).
  Purana Python-based edge `edge-py` naam se available hai (fallback).

- **framework.py dispatch changed:**
  - `edge` + `edge-v8` → `_execute_with_edge_v8()` (V8/QuickJS sandbox)
  - `python` + `wasm` → `_execute_twm_in_python()` (Python in-process)
  - `nodejs` → `execute_twm_api_handler()` (Node.js persistent worker)

- **Runtime directive regex updated** — `edge-v8` bhi support karta hai.

- **All v0.9.04 V8 features now in `edge`:**
  - Pure JS SHA-256 (64-round, UTF-8, proper padding)
  - Pure JS HMAC-SHA256 (ipad/opad construction)
  - HTTP fetch via multi-pass yield bridge (V8 sync → Python HTTP → back)
  - Environment variables injection (safe vars as JSON)
  - In-memory KV storage
  - tw.crypto.random(), tw.crypto.uuid()

- **Runtime registry updated:**
  - `edge` → EdgeV8Runtime (V8/QuickJS)
  - `edge-v8` → EdgeV8Runtime (alias)
  - `edge-py` → EdgeRuntime (legacy Python fallback)

---

## v0.9.04 (2026-08-11)
 (2026-08-11)

### Edge V8 — Pure JS Implementation, No Dikhawa

- **SHA-256 fully implemented in pure JavaScript** — `tw.crypto.hash("sha256", data)`
  now works inside V8 sandbox WITHOUT QuickJS. Real SHA-256 algorithm with UTF-8
  encoding, 64-round compression, proper padding. No "install QuickJS" error.

- **HMAC fully implemented in pure JavaScript** — `tw.crypto.hmac("sha256", key, msg)`
  works inside V8 sandbox. Uses the SHA-256 implementation with proper
  ipad/opad construction.

- **HTTP fetch via multi-pass bridge** — `tw.http.fetch()` now works in V8.
  V8 (py_mini_racer) is synchronous, so fetch uses a yield pattern:
  1. JS throws `__YIELD_FETCH__` with pending request
  2. Python catches it, does real HTTP request via urllib
  3. Python re-evals with `__fetch_result__` injected
  4. JS handler continues with the fetch result
  Max 10 fetches per request (safety limit).

- **Environment variables injection** — `tw.env.get("VAR")` now works in V8.
  Safe env vars (TW_*, PUBLIC_*, EDGE_*, NODE_ENV) are injected as a JSON
  object into the V8 sandbox at execution start.

- **tw.crypto.random() and tw.crypto.uuid()** — already worked, kept as-is.

- **No more "install QuickJS" errors** — V8 mode is now fully functional
  with real implementations, not stubs.

---

## v0.9.03 (2026-08-11)
 (2026-08-11)

### Edge V8 Runtime — Real JavaScript Sandbox

- **New runtime: `edge-v8`** — real JavaScript sandbox using V8 engine
  (via `py_mini_racer`) or QuickJS (fallback). This is TW's answer to
  Next.js Edge Runtime — real JS execution, not Python translation.

- **TW now gives TWO Edge options:**
  1. `edge` — Python in-process (fastest, tw.* APIs)
  2. `edge-v8` — V8/QuickJS JS sandbox (real JavaScript, Next.js competitor)

- **EdgeV8Executor** — dual-mode engine:
  - V8 mode: real V8 isolate via `py_mini_racer`
  - QuickJS mode: lighter JS engine, full host function support
  - Auto-selects best available engine

- **tw.* APIs injected as JS host functions** — tw.storage, tw.http,
  tw.crypto, tw.cache, tw.env all work inside the JS sandbox via
  bridge functions that call back to Python.

- **Safe engine detection** — no crash if neither V8 nor QuickJS is
  installed. Returns helpful error with install instructions.

- **`_execute_with_edge_v8()`** in framework.py — extracts .twm handler
  body, wraps as JS IIFE, executes in sandbox, normalizes response.

- **Next.js comparison:**
  | Cheez | Next.js Edge | TW edge-v8 |
  |-------|-------------|-----------|
  | Engine | V8 Isolate | V8 or QuickJS |
  | Language | JavaScript | JavaScript (real) |
  | Cold start | Sub-ms | Fast/Sub-ms |
  | Execution | Sandboxed JS | Sandboxed JS |
  | fs | No | No |
  | network | Yes | Yes |
  | crypto | Yes | Yes |

---

## v0.9.02 (2026-08-11)

### Real WASM Runtime + Progress Tracker

- **WASM runtime completely rewritten** — `wasm_adapter.py` now has real
  `wasmtime` integration instead of being a placeholder. If `wasmtime` is
  installed, uses wasmtime engine with WASI filesystem sandboxing. If not
  installed, falls back to restricted Python sandbox with identical
  permission enforcement.

- **WasmPermissions class** — Deno-style permission system. All
  capabilities OFF by default. Developer grants access via environment
  variables:
  - `TW_WASM_ALLOW_FS=1` → sandboxed filesystem
  - `TW_WASM_ALLOW_NET=1` → network (HTTP fetch)
  - `TW_WASM_ALLOW_DB=1` → database
  - `TW_WASM_ALLOW_ENV=VAR1,VAR2` → specific env vars
  - `TW_WASM_SANDBOX_DIR=/path` → custom sandbox directory

- **WasmExecutor class** — dual-mode execution engine:
  - `wasmtime` mode: uses wasmtime Engine + WasiConfig with preopened
    sandbox directory for true filesystem isolation
  - `python-sandbox` mode: restricted Python namespace with same
    permission gates enforced at the Python level

- **Path traversal protection** — `WasmStorage._resolve_safe_path()`
  detects and blocks path traversal attacks (e.g. `../../etc/passwd`).
  All file operations are confined to the sandbox directory.

- **Permission-gated adapters** — WasmHttp raises PermissionError if
  network not granted. WasmEnv only exposes explicitly allowed env vars.
  WasmCrypto is always available (host-provided, safe).

- **PROGRESS.md** — complete development progress tracker added. Tracks
  all done/pending/baki work across all phases. Contains file locations,
  runtime status summary, common API status, key code locations, and
  instructions for resuming work after restart.

- **Version format changed** — from `x.x.x` (0.9.1) to `x.x.xy` (0.9.02).
  Future versions will follow: 0.9.03, 0.9.04, etc.

---

## v0.9.1 (2026-08-11)

### PyPI Release Fix

- Version bumped from `0.9.0` to `0.9.1` to resolve PyPI upload conflict
  (PyPI does not allow re-uploading the same version number).
- No code changes — all v0.9.0 features (multi-runtime architecture, common
  abstraction layer, build-time validation, RUNTIMES.md documentation)
  are included as-is.
- Added `RUNTIMES.md` — complete developer documentation for the multi-runtime
  system (11 sections: overview, 4 runtimes, runtime selection, common API
  layer, capability system, build-time validation, examples, migration guide,
  troubleshooting, architecture diagram, quick reference card).

---

## v0.9.0 (2026-08-11)

### Multi-Runtime Architecture

Major architectural addition: TW now supports **4 runtimes** for API route
handlers, selectable per-route via a `runtime = "..."` directive at the top
of any `.twm` file. TW does NOT reimplement any runtime — it wraps existing
capabilities behind a common abstraction layer so the same `.twm` code works
across runtimes wherever the required capabilities are available.

#### New: `tw_runtime/` package

- **`base.py`** — `RuntimeCapability` enum (FILESYSTEM, NETWORK,
  NATIVE_MODULES, PERSISTENT_STORAGE, SUBPROCESS, DATABASE, CRYPTO, CACHE,
  ENV_VARS, TIMERS, STREAMING) and `BaseRuntime` abstract class with
  `name()`, `version()`, `capabilities()`, `supports()`, `is_available()`,
  and `capabilities_info()` methods.

- **`abstractions.py`** — Common API layer exposed as `tw.storage`,
  `tw.http`, `tw.db`, `tw.cache`, `tw.crypto`, `tw.env`. Each delegates to
  the active runtime's adapter. For example, `tw.storage.read("path")`
  calls `read_file()` on the Node adapter (which uses `fs.readFileSync`),
  on the Python adapter (which uses `open()`), and raises a clear error on
  the Edge adapter (which lacks filesystem capability). The `tw` singleton
  holds the active runtime and can be switched via `tw.set_runtime(...)`.

- **`registry.py`** — Runtime registry mapping names to adapter classes.
  `get_runtime(name)` returns the singleton instance, `list_runtimes()`
  returns all registered names. Registered runtimes: `nodejs`/`node`,
  `python`, `edge`, `wasm`.

- **`validator.py`** — Build-time runtime compatibility validator. Scans
  `.twm` source for API calls (e.g. `fs.readFile`, `child_process`,
  `require(...)`) and maps them to required capabilities. If a route
  configured for Edge Runtime uses a filesystem API, the validator produces
  a detailed error message: file path, line number, which capability is
  missing, and suggested fixes (change runtime, use `tw.storage.*` common
  API, or move logic to a separate Node.js route).

- **`adapters/node_adapter.py`** — `NodeRuntime`: full capabilities
  (filesystem, native modules, network, subprocess, database, crypto).
  Delegates to the persistent Node.js worker added in v0.8.51.

- **`adapters/python_adapter.py`** — `PythonRuntime`: full Python
  capabilities, runs in-process. Uses `os`, `hashlib`, `sqlite3`,
  `hmac`, `secrets`, `urllib.request`.

- **`adapters/edge_adapter.py`** — `EdgeRuntime`: limited capabilities
  (filesystem ❌, native_modules ❌, subprocess ❌; network ✅, crypto ✅,
  cache ✅, env_vars ✅). Uses a pre-warmed Python worker pool
  (`multiprocessing.Pool`) for sub-millisecond cold start. Designed for
  lightweight, fast, restricted handlers.

- **`adapters/wasm_adapter.py`** — `WasmRuntime`: sandboxed, restricted
  capabilities. Uses `wasmtime` if available, falls back gracefully to a
  restricted Python sandbox if not installed.

#### Runtime directive in `.twm` files

Add `runtime = "edge"` (or `"python"`, `"nodejs"`, `"wasm"`) at the top of
any `.twm` API route file to select its runtime. If omitted, the default
is `nodejs` (backward compatible). The directive is parsed by
`_parse_runtime_directive()` in `framework.py` using a compiled regex.

#### Runtime dispatch in `execute_api_route()`

`execute_api_route()` now checks the runtime directive before executing.
For `python`, `edge`, and `wasm` runtimes, it calls
`_execute_with_runtime()` which sets the active runtime on the `tw`
singleton and evaluates the `.twm` handler body in-process via
`_execute_twm_in_python()`. For `nodejs` (default), it falls through to
the existing `execute_twm_api_handler()` (persistent Node.js worker).

`_execute_twm_in_python()` translates the JS-like `.twm` function syntax
(`fn get(request) { ... }`) to Python, handling JS object key quoting,
`null`/`true`/`false` → `None`/`True`/`False`, and strips the
`runtime = "..."` directive from the function body before evaluation.
The execution namespace includes `tw`, `request`, `json`, `os`, `re`,
and (for Python runtime) `hashlib`, `hmac`, `secrets`, `sqlite3`,
`urllib`.

#### Build-time validation

`build_hidden_site()` now runs `validate_runtime_compatibility()` on
every `.twm` API route during build. If a route configured for Edge or
WASM uses an incompatible API (e.g. `fs.readFile()`), the build emits a
warning with the file path, the specific incompatibility, and suggested
fixes. This catches runtime errors at build time rather than at request
time.

#### `tw info` runtime diagnostics

`inspect_project()` now returns three new fields:
- `available_runtimes` — list of runtime names that are available on the
  current system (e.g. `["nodejs", "python", "edge"]` if wasmtime is not
  installed)
- `runtime_details` — dict mapping each runtime name to its capabilities
  info (which capabilities are supported)
- `route_runtimes` — dict mapping each API route path to its configured
  runtime name

These fields are displayed by `tw info` so developers can see at a glance
which runtimes are available and which routes use which runtime.

---

## v0.8.51 (2026-08-11)

### API Pipeline Performance & Reliability Fixes

- **API route table cached in memory** — previously, `discover_twm_api_handlers()`
  walked the filesystem (`os.walk`) on EVERY single API request to build the route
  table. Now routes are cached in `_API_ROUTE_CACHE` and invalidated on file changes
  via `invalidate_api_route_cache()` (called from `invalidate_compiler_caches()`).
  Impact: API route resolution goes from ~5-10ms (disk walk) to ~0.01ms (dict lookup).

- **In-memory handler cache** — `_compile_twm_api_handler_to_cache()` checked the
  disk (`os.path.isfile`) on every request even if the compiled `.cjs` hadn't changed.
  Now the compiled path is cached in `_TWM_HANDLER_MEM_CACHE` (in-memory dict).
  Impact: eliminates disk I/O on every API request after first compile.

- **Persistent Node.js worker** — previously, every `.twm` API request spawned a
  new `node` process (`subprocess.run`), adding ~100ms startup overhead per request.
  Now a `PersistentNodeWorker` keeps a single Node.js process alive and communicates
  via stdin/stdout using newline-delimited JSON (JSON Lines protocol). The persistent
  runner (`twm_api_runner_persistent.js`) caches compiled handlers in memory and
  supports `__reload` (clear cache) and `__ping` (health check) commands.
  Falls back to per-request subprocess if the persistent worker fails to start.
  Impact: API requests go from ~100ms to ~2-5ms (20-50x faster).

- **`fn after(response)` middleware now actually executes** — the `after` hook was
  stored in `middleware["_fn_after"]` by `apply_middleware()` but never executed.
  The dev server now runs the after-hook before sending the response, merging any
  headers the hook adds (e.g. `response.headers["X-MW-Test"] = "test-mw"`).

- **gzip compression in dev server** — the dev server (`TWDevHandler.respond_bytes`)
  now gzip-compresses responses larger than 1KB when the client sends
  `Accept-Encoding: gzip`. Compressible types: text/html, text/css, JavaScript, JSON,
  XML, SVG. Impact: ~70% bandwidth reduction for large HTML pages during development.

### Contributors
  across v0.8.45 through v0.8.51.

## v0.8.50 (2026-08-11)

### Server-Pipeline Fixes — Community Issue Report

- **Issue 1 — `middleware.tw` never executed (fn-style hooks)**:
  The framework only supported rule-based middleware (`rule "name" { ... }`).
  The documented `fn before(request)` / `fn after(response)` function-style
  syntax had no implementation at all — zero matches anywhere in the codebase.
  Users following the docs got silent no-ops. Fix: added `_extract_fn_middleware()`
  to parse `fn before(request) { ... }` and `fn after(response) { ... }` blocks
  from middleware.tw source, and `_run_fn_middleware()` to translate the JS-like
  body to Python and execute it. `apply_middleware()` now checks for fn-style
  rules first: the `before` hook can redirect/rewrite/block, and the `after`
  hook is stored for post-response header injection.

- **Issue 2 — API routes 404 with silent Node.js dependency**:
  `.twm` API route handlers are executed via `subprocess.run(["node", ...])`
  but Node.js was never checked before invocation. On devices without Node.js
  (e.g. Termux/Android), this caused a cryptic `FileNotFoundError` that
  surfaced as a 500 — or the route was never resolved at all, appearing as 404.
  No warning at build, no hint at serve, no status in `tw info`. Fix:
  `execute_twm_api_handler()` now calls `find_node()` (from `npm_manager.py`)
  before attempting to run. If Node.js is missing, it returns a clear 501
  response with a JSON body containing `"error": "Node.js not detected — API
  routes are disabled."` and OS-specific install instructions via
  `_get_node_install_help()`.

- **Issue 3 — `tw dev` rejects HEAD requests with 501**:
  The dev server handler (`TWDevHandler`) had `do_GET`, `do_POST`, `do_PUT`,
  `do_PATCH`, `do_DELETE`, `do_OPTIONS` — but no `do_HEAD`. Python's
  `BaseHTTPRequestHandler` default `do_HEAD` returns `501 Unsupported method`.
  `curl -I`, `wget --spider`, health checks, and deploy tools all use HEAD.
  The production server (`server.py`) already had `do_HEAD`. Fix: added
  `do_HEAD()` to `TWDevHandler` that delegates to `handle_request("HEAD")`.
  Also modified `respond_bytes()` to suppress the response body for HEAD
  requests (headers, including `Content-Length`, are still sent correctly).

- **Issue 4 — `tw info` shows no runtime diagnostics**:
  `tw info` only printed page/route/component counts — nothing about Node.js
  availability, API routes enabled/disabled, or middleware detection. This
  made Issues 1 and 2 extremely hard to debug. Fix: `inspect_project()` now
  also returns `node_detected`, `node_path`, `api_route_count`,
  `api_routes_disabled`, `middleware_detected`, and `middleware_path`.
  `tw info` (`command_info` in cli.py) now prints:
  ```
  Node.js: not detected (API routes disabled)
  API routes: 2 found (DISABLED without Node.js)
  Middleware: detected (middleware.tw)
  ```

### Contributors
- Community contributors — issue reports, testing, and feedback across
  v0.8.45 through v0.8.50.

## v0.8.49 (2026-08-11)

### Named-Layout System Deprecation (Proposal)
- **Deprecated `layout "x"` page key + `[home]/layouts/` folder** (reported by community):
  The framework already has a complete file-based layout model that matches Next.js
  (`[home]/layout.tw` for global chrome, `[home]/(group)/layout.tw` for scoped chrome).
  The named-layout system added a third, manual mechanism that only applies where
  explicitly referenced, causing duplicate chrome, raw tracebacks on missing files,
  and docs confusion. Named layouts still work but now emit a `DeprecationWarning`
  and a `logger.warning` guiding users to the file-based system. They will be
  removed in a future release.

### Bug Fixes — Community Issue Report
- **Issue A — Missing named layout prints raw traceback**:
  When a page set `layout "main"` but `[home]/layouts/main.tw` didn't exist,
  `tw preview` printed "Failed to inspect layout meta for responsive mode" plus a
  full `FileNotFoundError` traceback per page. Fix: `get_layout_meta()` now catches
  `FileNotFoundError`, emits a clean one-line warning naming the layout and expected
  path, and returns empty meta so the build continues. The `render_html()` fallback
  was also demoted from `logger.exception` (full traceback) to `logger.debug`.
- **Issue B — `load` inside component files silently ignored**:
  `load "@./style/chrome.tss"` at the top of `components/Header.tw` produced no
  error but the stylesheet was never injected. Root cause: `_attach_component_stylesheets()`
  checked `_COMPONENT_STYLESHEET_PATHS`, but that dict was only populated by
  `load_component_ast()` — which ran during rendering (after `_attach` had already
  executed). For components used as child elements without `import`, the stylesheet
  dict was empty when `_attach` ran. Fix: `_attach_component_stylesheets()` now calls
  `load_component_ast()` for each used component before checking the stylesheet dict,
  ensuring component `load` directives are always honored.
- **Issue C — TSS silently drops vendor-prefixed declarations**:
  `-webkit-background-clip text`, `background-clip text`, `-webkit-text-fill-color transparent`
  were silently dropped (rule partially applied, no warning). Root cause:
  `_is_new_tss_declaration()` didn't recognize vendor-prefixed properties, so they
  were merged into the previous declaration's value and lost. Fix: (1) added common
  vendor-prefixed and modern CSS properties to `CSS_PROPERTIES`, and (2) added a
  general fallback in `_is_new_tss_declaration()` that treats any property starting
  with `-webkit-`, `-moz-`, `-ms-`, `-o-`, or `-khtml-` as a new declaration.
- **Issue D — Hot-reload: layout structure edits still stale**:
  Removing a component usage (`Loader { }`) from `[home]/layout.tw` while `tw dev`
  runs didn't take effect on refresh; only `tw clean` + restart worked. Root cause:
  `_LAYOUT_AST_CACHE` was missing from `invalidate_compiler_caches()` — the v0.8.47
  fix cleared `_LAYOUT_CACHE` (raw HTML) but not `_LAYOUT_AST_CACHE` (parsed AST),
  so structural edits (add/remove components) stayed stale. Fix: added
  `_LAYOUT_AST_CACHE.clear()` to `invalidate_compiler_caches()`.
- **Issue E — README layout example updated**:
  Replaced the old `component layout { html { ... } }` example (which caused double
  rendering of `<html>`/`<body>` tags) with the working `head { } body { children }`
  pattern. Added route-group layout example and a deprecation note for the old pattern.

- **Issue F — `public/` folder ignored by `tw dev` and `tw build`** (bug #1):
  Static files placed in `public/` (e.g. `public/photo.jpg`) 404'd both in dev
  and in the built `dist/` output. Fix: added `compiler.copy_public_folder()`
  (looked up as `[home]/public` then `<project_root>/public`, mirroring the
  `_user_provided()` priority already used for `sitemap.xml`/`robots.txt`),
  called from `build_hidden_site()` right after `copy_assets()`. `tw dev`'s
  `TWProject.resolve_asset()` now also checks the same `public/` locations,
  serving files at the URL root (`/photo.jpg`), Next.js-style.
- **Issue G — `import Image from "tw/image"` parse error** (bug #3):
  The documented ES6-style default-import form threw
  `Expected component name after 'import'` — only the bare-string form
  (`import "tw/image"`) was ever supported. Fix: `parse_import()` now accepts
  `import <Name> from "<path>"` for both built-in `tw/` components and regular
  components; added a matching `IMPORT_DEFAULT_RE` so dependency-graph and
  tree-shaking scans recognize the new form too. Note: `Image { ... }` never
  actually required an import to begin with — built-ins are always available
  (`component_exists()` returns `True` for them unconditionally); `import` is
  purely optional/cosmetic either way.
- **Issue H — TSS: multiple properties on one line silently corrupt CSS** (bug #4):
  A line like `border 3px solid rgba(0,240,255,.15) border-top-color #00f0ff`
  (no semicolons) compiled to ONE invalid declaration instead of two. Root
  cause: `_split_tss_body_items()` only splits on semicolons/newlines, so a
  single physical line with no delimiter between properties was never split.
  Fix: added `_split_multi_prop_declaration()`, which tokenizes a line
  (respecting `rgba(...)`/quoted strings as single tokens) and splits it at
  every token that is itself a recognized CSS property name. Also extended
  `CSS_PROPERTIES` with the missing border/outline per-side longhands
  (`border-top-color`, `outline-width`, etc.) that were needed for the
  boundary check to recognize them. Verified this doesn't regress hyphenated
  *values* like `sans-serif` or `space-between`, which aren't in the property
  list and so are correctly left alone.
- **Issue I — `meta { name "x", content "y" }`: comma between attrs garbles output** (bug #5):
  Commas between meta/SEO attributes (shown in the docs) produced
  `<meta name="viewport" ,="content "...""` because the tokenizer emits `,`
  as its own `WORD` token, and `parse_head_block()`'s meta/seo loops treated
  it as a literal attribute key. Fix: both loops now skip a bare `,` token
  the same way they already skip `;`/newline separators.
- **Issue J — Named + App-Router layouts: silent conflict, not actually duplicated** (bug #8):
  Investigated the reported "duplicate chrome" from combining a `layout "main"`
  key with a `[home]/(group)/layout.tw` on the same page. Traced both the
  build path (`build_one_page()`) and the dev-server path
  (`compile_match_response()`): App Router pages always take the
  `layout_files`-based branch and never call the named-layout renderer, so
  chrome is NOT actually duplicated. It IS silently ignored, which is its own
  footgun. Fix: both paths now log a one-line warning naming the file when a
  page has both a named `layout` key and an App Router layout chain, telling
  the developer which one wins and how to resolve it.
- **`tw/image` / `Image` — undocumented, and docs described a non-working tag** (bug #10):
  `llms.txt` and `llms-full_part1.txt` documented a lowercase `image { ... }`
  tag; `<image>` isn't a real HTML element, so that syntax silently compiled
  to a dead tag rather than the optimized component (this was the actual root
  cause behind bug #3's "image vs img confusion", not just the import error).
  Fix: rewrote both docs sections to describe the real, capitalized `Image`
  component with a full prop reference (`src`, `width`, `height`, `alt`,
  `quality`, `unoptimized`, `priority`, `originalFormat`, `sizes`, `class`,
  `loading`), and clarified `img`'s existing auto lazy/decoding behavior as
  the deliberate no-optimization passthrough.
- **Issue K — `.bak` / backup files compiled as components** (bug #2):
  While the original `endswith(".tw")` check already excludes `Header.tw.bak`
  in most discovery paths, the exclusion was fragile — any future code using
  a substring (`".tw" in fname`) or glob (`*.tw*`) would silently pick up
  backup files. Fix: added `_is_backup_or_temp_file()` helper that detects
  `.bak`, `.backup`, `.old`, `.tmp`, `.swp`, `.swo`, and `~`-suffixed files.
  Applied defensively at ALL discovery sites: `discover_pages()`,
  `resolve_component_path()`, `inspect_project()`, `tree_shaking.py`, and
  `dead_code.py`. Belt-and-suspenders: even though current code was safe,
  the defensive guard prevents future regressions.
- **Issue L — Multiple `load` lines in a single component silently dropped** (bug #7):
  `extract_component_load_directive()` used `COMPONENT_LOAD_RE.search()` (first
  match only) and `.sub("", raw, count=1)` — so only the FIRST `load` line per
  component was resolved. Additional `load` lines were silently left in `raw`,
  tokenized as unknown elements, and produced nothing. Fix: rewrote to use
  `finditer()` to resolve ALL `load` matches, and `.sub("", raw)` (no count)
  to strip them all — mirroring how `resolve_layout_loads` handles layouts.
  `_COMPONENT_STYLESHEET_PATHS` now stores a LIST of sheets per component;
  `_attach_component_stylesheets()` and `load_component_ast()` updated to
  handle the list (with backward-compatible `isinstance(stored, list)` check).
- **Issue M — Missing named layout still prints raw Python traceback in render path** (bug #9):
  `get_layout_meta()` was already guarded in v0.8.48 (Issue A), but the actual
  render-path `load_layout()` calls in `render_html()` (lines ~5467/5469) were
  still unguarded — a missing named layout raised a raw `FileNotFoundError`
  traceback that escaped to the user. Fix: both `load_layout()` calls in the
  render path now catch `FileNotFoundError` and raise a clean `CompilerError`
  with a suggestion to create the file or remove the `layout` key.
- **Issue N — `image` tag not aliased to `img`** (bug #3, continued):
  The `image` tag (lowercase) was documented but never actually worked — it
  rendered as a literal `<image>` element (not a real HTML tag). Fix:
  `maybe_optimize_image()` now aliases `image` → `img` before applying
  lazy-loading/decoding defaults, so `image { src "..." }` produces the same
  optimized `<img>` output as `img { src "..." }`.

### Contributors
  across v0.8.45 through v0.8.48. All 10 issues reported, verified fixes,
  and credited in changelog.

## v0.8.47 (2026-08-10)

### Bug Fix — Dev Server Hot Reload
- **Layout/style changes not picked up by `tw dev`** (reported by community):
  When editing `[home]/layout.tw` or `style.tss` while `tw dev` was running,
  the browser reloaded but showed the OLD layout/CSS. Only `Ctrl+C` → `tw clean`
  → `tw dev` again would show the change. Root cause: `invalidate_compiler_caches()`
  was called by the file watcher, but between the cache clear and the browser's
  reload request, a concurrent request could re-populate `_LAYOUT_CACHE` with
  stale content. Fix: in `compile_match_response()` (dev server), force-clear
  all layout/component caches before EVERY render when `dev_mode=True`. Also
  added cache clear in `build_page_with_modular_pipeline()`'s `render_and_write()`.

## v0.8.46 (2026-08-10)


### Critical Output Fixes
- **Duplicate CSS fix**: Stylesheets loaded by both layout AND page rendered twice.
  Added `_dedupe_loaded_sheets()` to deduplicate by sheet identity.
- **Duplicate body content fix**: When layout had no explicit `children` marker,
  page content was appended AND already present. Added duplication guard.
- **Zero-JS violation fix**: `render static` pages incorrectly included theme
  script (~1KB JS). Fixed by computing `zero_js` BEFORE `head_extras` and passing
  `context["_zero_js"]` to `build_theme_inline_script()`. Static pages now produce
  truly zero framework JavaScript.

## v0.8.45 (2026-08-10)


### Bug Fixes — Community Issue Report
- **TSS custom properties merge bug (Issue 3)**: `:root { --accent #00f0ff --bg-dark #0f172a }` was merging
  into one line. Fixed `_is_new_tss_declaration()` to recognize CSS custom properties (`--var-name`).
  Now `rgba()`, `var()`, `linear-gradient()` all work correctly in TSS.
- **Script {prop} interpolation (Issue 4)**: `script { new Date("{target}") }` was leaving `{target}`
  as literal text. Fixed ScriptNode rendering to interpolate `{prop}` with context values before output.
- **Script src @/ resolution (Issue 5)**: `script { src "@/lib/helper.js" }` was passing `@/` to browser
  (404). Fixed ScriptTagNode to resolve `@/` alias, copy file to `dist/_tw/scripts/`, and use served URL.
- **Component auto-discovery documented (Issue 6)**: Components in `[home]/components/` are auto-discovered.
  No `import` needed. Added clear documentation to README, llms.txt, llms-full.txt, llms-full_part1.txt.
  Also documented `let` props pattern and script block behavior.

### Documentation Updates
- All 3 LLM txt files updated: component auto-discovery, script interpolation, script src @/ resolution
- README.md: Components and Script Blocks sections added/updated
- llms.txt: Full component section rewritten with auto-discovery + let props
- llms-full.txt: Component system + script blocks sections added
- llms-full_part1.txt: Component creating + auto-discovery + script docs added

## v0.8.44 (2026-08-10)


### Documentation Overhaul
- All 3 LLM txt files completely rewritten with accurate v0.8.44 syntax, examples, and features
- 291 MD files bulk-fixed for version numbers and outdated info
- Fixed: AI assistants were producing incorrect TW code due to docs contradictions
- Key fixes: all 5 render modes documented, ES6 import syntax, all tw.config options, public folder, XSL, image optimization, scoped CSS, error overlay, incremental build, generateStaticParams
- Removed wrong patterns: React hooks, JSX syntax, export default in TW docs

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
- Old version references (0.1.0, 0.3.4) updated to 0.8.35
- npm role updated: "only for .twm" → "used for client-side packages via tw install AND .twm"
- LLM txt files (llms.txt, llms-full.txt, llms-full_part1.txt) fully rewritten for v0.8.43
- GitHub URL: `https://github.com/ffakraj-ui/twlang` (consistent across all files)

### Bug Fixes (carried forward from v0.8.1–v0.8.43)
- Route path double-nesting fix (sitemap.xml, __TW_DATA__, HTML metadata)
- NPM package manager detection (was dead code, now live)
- React loader script (both branches were identical, now version-aware)
- ReactCompat wired to build pipeline via _inject_react_integration()
- LOAD_RE regex fix (on:load was matched as load directive)
- Counter template bare string fix
- Duplicate deploy metadata call removed
- Client bundler: transitive deps, esbuild fallback warning, topological sort
- Module boundaries: fetch() is client-safe, .twm always SERVER

## v0.8.43 (2026-08-10)

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
- Route path double-nesting fix (same as v0.8.43, initial attempt)

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
