# TW Framework

A high-performance, HTML-first web framework with Virtual DOM, App Router, Zero-JS static sites, and **Multi-Runtime Architecture** (V8 Edge, Python, Node.js, WASM).

**v0.9.17** — 700+ bugs fixed across 7 versions. Production-ready for small/medium sites.

---

## Quick Start

```bash
pip install tw-framework
tw create my-site
cd my-site
tw build
```

Your static site is in `dist/` — deploy it anywhere.

### Optional Features

The core framework has **zero hard dependencies** (pure Python stdlib). Install extras as needed:

```bash
pip install tw-framework[image]        # Pillow — image optimization, srcset
pip install tw-framework[compression]  # brotli — production pre-compression
pip install tw-framework[edge-v8]       # py_mini_racer — V8 JS sandbox runtime
pip install tw-framework[redis]        # redis — distributed SSR cache
pip install tw-framework[wasm]         # wasmtime — WebAssembly sandbox runtime
pip install tw-framework[all]           # All optional features combined
```

---

## CLI Commands

| Command | Description | Key Flags |
|---------|-------------|-----------|
| `tw create <name>` | Create new project | `--directory` |
| `tw init [name]` | Initialize in current dir | `--force` |
| `tw dev` | Start dev server (127.0.0.1:3000) | `--host`, `--port`, `--no-open`, `--no-minify`, `--workers` |
| `tw build` | Build to `dist/` | `--prod`, `--watch`, `--analyze`, `--clean`, `--adapter`, `--report`, `--strict` |
| `tw export` | Export static site | `--out-dir`, `--workers`, `--no-minify` |
| `tw preview` | Preview built site (port 4173) | `--host`, `--port`, `--no-build` |
| `tw serve` | Production SSR server (0.0.0.0:8000) | `--host`, `--port`, `--out-dir`, `--no-build` |
| `tw deploy` | Deploy to cloud | `--provider`, `--vercel`, `--cloudflare`, `--prod`, `--dry-run` |
| `tw clean` | Clear cache | — |
| `tw doctor` | Health check | — |
| `tw info` | Project info | — |
| `tw install <pkg>` | Install npm package | `--dev`, `--exact` |
| `tw remove <pkg>` | Remove npm package | — |
| `tw list` | List npm packages | `--detailed` |
| `tw plugin add/list/search` | Plugin management | — |
| `tw ast <file>` | Show AST | `--out`, `--diagnostics` |
| `tw tokens <file>` | Show tokens | `--out` |
| `tw check <file>` | Check syntax | `--include-ast`, `--include-ir` |

Global flags: `--project-root`, `--debug`, `--version`

---

## Project Structure

```
my-site/
  tw.config              # project config (name, site_url, theme, sitemap, etc.)
  .env                   # environment variables
  middleware.tw          # middleware (auth, headers, rate limiting, rewrites)
  [home]/                 # App Router root (literal brackets)
    layout.tw            # root layout (wraps all pages)
    page.tw              # home page (/)
    not-found.tw         # 404 page
    style.tss            # global stylesheet
    about/page.tw        # /about
    blog/page.tw         # /blog (index)
    blog/[slug]/page.tw  # /blog/:slug (dynamic route)
    blog/posts.json      # data for generateStaticParams
    counter/page.tw      # /counter (reactive state)
    contact/page.tw      # /contact (form)
    components/           # reusable components
      Navbar.tw
      Footer.tw
      Button.tw
      Card.tw
    api/                  # API routes
      contact/route.tw   # POST /api/contact
      users/route.tw     # GET /api/users
  dist/                  # build output
  public/                # static files (served as-is)
```

---

## Page Block Directives

```tw
page {
    title "My Page"
    render static          # static | server | edge | interactive | dynamic | csr
    revalidate 60          # ISR: revalidate every 60 seconds
    cache_by "cookie:session"  # cache by cookie/header/query
    cache_size 256         # max cache entries per namespace
    generateStaticParams "../posts.json"  # dynamic route data
    redirect "/new-path"  # redirect this page
    rewrite "/other-page" # rewrite URL
}
```

### Render Modes

| Mode | Description | Output |
|------|-------------|--------|
| `static` | SSG — build-time HTML (default) | Pure HTML, zero JS |
| `server` | SSR — per-request server render | Dynamic HTML on each request |
| `edge` | Edge runtime via V8 sandbox | JS handler in V8 isolate |
| `interactive` | TW native VDOM (~3KB) | Zero-JS by default, reactive on demand |
| `dynamic` | Auto-detect static vs server | Smart routing |
| `csr` | Full React CSR | React ecosystem, client-side hydration |

---

## Component System

```tw
component Button {
    props {
        href: string = ""
        label: string = "Click"
        variant: string = "primary"
    }

    style {
        .btn { padding: 0.5rem 1rem; border-radius: 0.375rem; }
        .btn-primary { background: #3b82f6; color: white; }
        .btn-secondary { background: #6b7280; color: white; }
    }

    body {
        a { class: "btn btn-{{variant}}", href: "{{href}}", text: "{{label}}" }
    }
}
```

Components have scoped CSS (CSS Modules built in), typed props with defaults, and support `children` slot.

---

## Reactive State

```tw
page {
    title "Counter"
    render interactive
}

state {
    count 0
    name "World"
}

body {
    div { class "counter"
        h1 "Hello, {{name}}!"
        p "Count: {{count}}"
        Button { label "Increment", on:click "increment" }
        Button { label "Decrement", on:click "decrement" }
    }
}

actions {
    fn increment(state) {
        state.count = state.count + 1
    }
    fn decrement(state) {
        state.count = state.count - 1
    }
}
```

---

## API Routes (.twm)

```twm
runtime = "nodejs"

fn get(request) {
    return {
        status: 200,
        body: { message: "Hello from API" }
    }
}

fn post(request) {
    const data = request.body
    return {
        status: 201,
        body: { created: true }
    }
}
```

### Multi-Runtime Support

| Runtime | Directive | Engine | Best For |
|---------|-----------|--------|----------|
| **Node.js** | `runtime = "nodejs"` | Persistent Node.js worker | Full npm packages, fs, native modules |
| **Edge V8** | `runtime = "edge"` | V8 Isolate (py_mini_racer) | Fast, lightweight APIs — real JS sandbox |
| **Python** | `runtime = "python"` | Python in-process | Python libraries, ML, no Node.js needed |
| **WASM** | `runtime = "wasm"` | wasmtime sandbox | Untrusted code, maximum isolation |
| **Edge (legacy)** | `runtime = "edge-py"` | Python in-process | Fallback if V8 not installed |

Default is `nodejs`. All runtimes share a common API layer:

```javascript
tw.storage.read("config.json")     // fs on Node, KV on Edge
tw.storage.write("output.txt", data)
tw.http.fetch("https://api.com")   // fetch on Edge, urllib on Python
tw.crypto.hash("sha256", data)     // SHA-256 hashing
tw.crypto.uuid()                   // UUID v4
tw.cache.set("key", value, 60)    // Cache with 60s TTL
tw.env.get("TW_API_KEY")           // Filtered env vars
```

---

## Middleware System

### Rule-based middleware (`middleware.tw`)

```tw
use {
    match "/dashboard/**"
    header "X-Content-Type-Options" "nosniff"
    header "X-Frame-Options" "DENY"
}

rule "api-rate-limit" {
    match "/api/**"
    rate_limit { requests 100, window 60 }
}

rule "auth-required" {
    match "/admin/**"
    auth { cookie "session" }
}
```

### Function-based middleware

```tw
fn before(ctx) {
    if (ctx.path.startsWith("/admin") && !ctx.session) {
        return { redirect: "/login" }
    }
}

fn after(ctx) {
    ctx.response.headers["X-Response-Time"] = ctx.duration + "ms"
}
```

### Middleware capabilities

- **Path matching**: prefix, contains, extensions, regex, single_segment_max, deny_traversal, deny_null_bytes
- **Headers**: add custom security/response headers
- **Methods**: restrict HTTP methods
- **Auth**: cookie-based, JWT (secret or env var)
- **Rate limiting**: token bucket per IP/identity, configurable window and capacity
- **User agent**: allow/block/empty_is_blocked
- **Origin**: CORS allow/require/allow_referer
- **Redirect/rewrite**: URL redirection and rewriting
- **Custom response**: status, json, html, text, content_type, headers, cookies

---

## Security Features

- **CSP nonce generation** — cryptographically secure per-request nonces
- **Content-Security-Policy** header builder with directive dedup
- **HTML sanitization** — XSS prevention with double-escape protection
- **URL sanitization** — prevents javascript: and data: URL injection
- **Attribute sanitization** — href/src sanitization with double-escape prevention
- **CSRF token** generation and validation
- **Null byte removal** from all user inputs
- **Security headers**: `X-Frame-Options`, `X-Content-Type-Options`, `upgrade-insecure-requests`
- **Request body size limit** (default 10MB, configurable via `TW_MAX_BODY_SIZE`)

---

## Production Server

```bash
tw serve --host 0.0.0.0 --port 8000
```

Features:
- SSR for `render server` and `render edge` pages
- Static file serving from `dist/` with ETag and Cache-Control
- Brotli/gzip pre-compressed file negotiation
- API route execution (Node.js, Edge V8, Python, WASM)
- Middleware chain execution
- WebSocket support for realtime features
- Health check at `/__tw/health`
- Graceful SIGTERM/SIGINT shutdown
- AST cache with TTL (`TW_AST_CACHE_MAX`, `TW_AST_CACHE_TTL`)
- SSR cache (in-memory LRU or Redis via `TW_REDIS_URL`)
- Configurable max fetch passes (`TW_MAX_FETCH_PASSES`)
- V8 execution timeout (30s default)

---

## Build Pipeline

```bash
tw build --prod --analyze --report
```

The compiler pipeline:
1. **Lexing** — tokenize `.tw` source
2. **Parsing** — build AST (page, element, component, if, for, each, let, script blocks)
3. **Semantic analysis** — type checking, scope resolution
4. **IR lowering** — intermediate representation
5. **HTML rendering** — generate static HTML
6. **CSS rendering** — scoped stylesheets, TSS compilation
7. **JS bundling** — client-side runtime, code splitting
8. **Dead code detection** — unused pages, components, APIs
9. **Tree shaking** — remove unused exports
10. **Minification** — HTML, CSS, JS minification
11. **Output** — write to `dist/`

Build options: `--workers` (parallel compilation), `--watch` (rebuild on change), `--analyze` (bundle analysis), `--report` (build report), `--strict` (treat warnings as errors), `--adapter` (vercel/netlify/cloudflare output).

---

## Deployment

### Zero-config deployment

```bash
tw deploy --provider vercel --prod
```

Auto-detects and generates configs for:
- **Vercel** — `vercel.json` with build command and routes
- **Netlify** — `netlify.toml` with build and redirects
- **Cloudflare** — `_redirects` and headers
- **GitHub Pages** — `.nojekyll` and base path
- **Docker** — `Dockerfile` with Python runtime

Use `--dry-run` to preview deployment config without deploying.

---

## Plugin System

```bash
tw plugin add seo-booster    # Install plugin
tw plugin list               # List installed plugins
tw plugin search             # Search registry
```

Plugins use `.twp` format with 5 lifecycle hooks:
- `beforeBuild` — modify build config before compilation
- `afterBuild` — post-build transformations
- `beforeRoute` — route-level modifications
- `afterRoute` — post-route processing
- `beforeRequest` — per-request hooks

---

## Configuration (`tw.config`)

```yaml
name: My TW Site
site_url: https://example.com
description: A modern TW App Router project
theme: system              # system | light | dark
pretty_urls: true          # /about/ instead of /about.html
search: true                # built-in search index
modular_pipeline: true     # modular compilation
allow_raw_script: true      # allow <script> tags
sitemap: true               # generate sitemap.xml
robots: true                # generate robots.txt
rss: true                   # generate RSS feed
auto_image_alt: true        # auto-generate alt text
```

---

## Environment Variables

| Variable | Default | Description |
|----------|---------|-------------|
| `TW_REDIS_URL` | — | Redis URL for distributed SSR cache |
| `TW_MAX_FETCH_PASSES` | 10 | Max HTTP fetch calls per Edge V8 request (1-50) |
| `TW_SSR_CACHE_MAX` | 512 | Max SSR cache entries |
| `TW_AST_CACHE_MAX` | 128 | Max AST cache entries |
| `TW_AST_CACHE_TTL` | 300 | AST cache TTL in seconds |
| `TW_MAX_BODY_SIZE` | 10MB | Max request body size |

Env vars are filtered for Edge runtime — only `TW_`, `PUBLIC_`, `EDGE_` prefixed vars and `NODE_ENV` are exposed.

---

## Testing

```bash
pip install tw-framework[dev]
pytest tests/ --tb=short -q
```

Current: 610 passed, 9 skipped, 0 failed.

---

## License

MIT — see [LICENSE](LICENSE).

## Author

**KANISHK KUMAR** (mlkraj290@gmail.com)

---

## Links

- [PyPI](https://pypi.org/project/tw-framework/)
- [GitHub](https://github.com/ffakraj-ui/twlang)
- [CHANGELOG](CHANGELOG.md)
- [Documentation](DOCUMENTATION.md)
