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
