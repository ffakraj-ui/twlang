# TW Framework Improved v5

Implemented in this pass:

- Stronger routing
  - nested routes
  - route groups via folders like `(marketing)`
  - catch-all routes `[...slug].tw`
  - optional catch-all routes `[[...slug]].tw`
  - page-level `redirect`
  - page-level `rewrite`
  - custom `404.tw` and `500.tw` remain supported

- Static hosting quality-of-life
  - `pretty_urls: true` in `tw.config` → `/about` outputs as `dist/about/index.html` (clean URLs on static hosts)
  - dev server also accepts `/about/index.html` requests

- Nested layouts (multi-layer)
  - `layout "base > docs"` or repeated `layout` directives
  - first layout = outer document, remaining layouts = inner wrappers (fragments around `{slot}`)
  - **App Router (v0.7.0+)**: layouts are TW components (`layout.tw` files), nest automatically by directory structure, use `children` keyword instead of `{slot}`. See `docs/app-router.md`

- App Router (v0.7.0+)
  - File-system based routing with `page.tw` files
  - Route groups `(folder)` excluded from URL
  - Dynamic routes `[slug]` as folder names
  - Catch-all routes `[...slug]`
  - Layouts as TW components with `children` keyword
  - Nested layout composition (root → innermost)
  - Special files: `loading.tw`, `not-found.tw`, `error.tw`, `route.tw`
  - Auto-detection: App Router mode vs Legacy mode
  - Fully backward compatible with `[home]/` + `[home]/layouts/`

- Theme (Dark/Light/System)
  - `theme: system|dark|light` in `tw.config`
  - adds `data-theme` on `<html>` + `window.__twToggleTheme()` / `window.__twSetTheme(mode)`

- Search (static-friendly)
  - `search: true` in `tw.config`
  - build outputs `dist/_tw/search-index.json`
  - pages auto-include a small search runtime exposing `window.__twSearch(query)`

- Components improvements
  - components can live in nested folders under `[home]/components/**`
  - component resolver will auto-find `Button.tw` even if it's in a subfolder (best with unique names)
  - recursive component rendering now throws a clear compiler error (prevents `maximum recursion depth exceeded`)
  - Capitalized HTML tags like `Section {}` are now auto-treated as `<section>` (compiler won't assume missing `components/Section.tw`)
  - component load/recursion errors now report the callsite file + line/column when possible

- DX / error-proofing
  - placeholders now support moustache style: `{{brandName}}` (gets interpolated same as `{brandName}`)
  - writing `<nav>` style tags now shows a clear compiler error + fix hint
  - `.tss` numeric shorthands like `padding 12 18` now become `padding: 12px 18px;`

- Rendering metadata
  - `page { render static | server | edge }`
  - `page { revalidate 60 }`
  - route manifest output in `dist/_tw/route-manifest.json`

- API routes
  - automatic `/api/*` endpoint mapping from `[home]/api/*.tw`
  - method blocks: `GET`, `POST`, `PUT`, `PATCH`, `DELETE`, `OPTIONS`
  - response directives: `status`, `json`, `text`, `html`, `redirect`, `header`, `cookie`

- Middleware
  - `middleware.tw`
  - `use { match ... }`
  - `auth`, `redirect`, `rewrite`, `header`, `cookie`

- Environment variables
  - `.env`
  - `.env.local`
  - `.env.production`
  - exposed in templates/API as `env.KEY`
  - `.twm` runtime helpers: `env.get()`, `env.require()`, `secrets.get()`, `secrets.require()`

- Server-side `.twm` runtime helpers
  - `async fn` handlers supported
  - built-in `http.get/post/put/patch/delete`
  - `pkg.require("package-name")` for project-installed npm packages
  - Firebase Admin helper via `firebase.app()/firestore()/auth()`

- Performance and output
  - HTML/CSS minify
  - JS chunk minify
  - route manifest
  - API manifest
  - asset fingerprinting for copied assets
  - gzip output
  - brotli output when `brotli` package is available

- SEO output
  - `sitemap.xml`
  - `robots.txt`
  - `rss.xml`
  - canonical auto-generation when `site_url` exists
  - JSON-LD via `head.seo.json_ld`

- Deploy support
  - Vercel
  - Cloudflare Pages
  - Netlify
  - GitHub Pages workflow file
  - Dockerfile

- CLI
  - `tw build --watch`
  - `tw build --analyze`
  - `tw build --clean`
  - `tw build --prod`

Important notes:

- `render server` and `render edge` are implemented as framework-level route metadata plus dev/runtime behavior. Static export still emits HTML output for compatibility.
- API routes are fully available in the dev server. Static build emits API manifests, but dynamic APIs still require a runtime host.
- Middleware is active in the dev server and designed around route guarding, rewrites, headers, and cookies.


## ES6 Import Syntax (v0.8.43+)

TW supports ES6-style named imports for client-side JavaScript libraries in `.tw` files:

\`\`\`tw
import { startCountdown } from "@/lib/countdown"
import { formatData, parseJSON } from "@/lib/utils"
\`\`\`

### Supported Features
- Named imports: `import { fn1, fn2 } from "@/lib/file"`
- File extensions: `.js`, `.ts`, `.mjs` (auto-detected)
- Path alias: `@/` maps to `[home]/`
- Works alongside component imports (`import "Navbar"`)
- Imported functions usable in `script` blocks

### Not Supported
- `.twm` files in ES6 imports (use `load` directive instead)
- Default imports (`import fn from "..."`)
- Namespace imports (`import * as ns from "..."`)

### Implementation
- `IMPORT_ES6_RE` regex in `compiler.py` matches the syntax
- `_parse_es6_import()` function parses named imports and resolves file paths
- `_ES6_IMPORTS` list tracks imported functions for dependency graph
- `extract_directives_from_source` updated to track ES6 imports
