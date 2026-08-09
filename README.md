# TW Framework

**Write `.tw` files. Ship complete websites. Zero JavaScript by default.**

A custom language + framework for building websites — with its own lexer, parser, and compiler pipeline. No React, no Virtual DOM, no runtime framework. Just clean HTML, CSS, and JS that the browser actually needs.

---

## Quick Start

```bash
pip install tw-framework
tw create my-site
cd my-site
tw dev
```

Open `http://127.0.0.1:3000` — live-reloading dev server is running.

### Your first App Router page

`tw create` generates an App Router project:

```
[home]/
├── layout.tw          ← Root layout (wraps every page)
├── page.tw            ← Home page (URL: /)
├── about/
│   └── page.tw        ← URL: /about
├── counter/
│   └── page.tw        ← URL: /counter (interactive, uses state)
├── contact/
│   └── page.tw        ← URL: /contact
├── not-found.tw       ← 404 page
├── api/
│   ├── contact/route.tw   ← POST /api/contact
│   └── users/route.tw      ← GET /api/users
└── style.tss          ← Global stylesheet
```

### Add interactivity — only when you need it

```tw
page {
    title "Counter"
    render static
}

state {
    count 0
}

body {
    p "Count: {count}"
    button {
        on:click "__tw.set('count', __tw.get('count') + 1)"
        class "button"
        "+"
    }
}
```

TW ships a tiny reactive runtime (~2KB) only for pages that use `on:` or `bind:` directives. Static pages stay at 0KB JS.

---

## App Router

The App Router is TW Framework's file-system based routing system. Layouts are **TW components**, not HTML templates. Routes come from `page.tw` files in nested directories.

### Key Concepts

- **`page.tw`** — defines a page route (creates a URL)
- **`layout.tw`** — wraps all child pages with shared structure
- **`children` keyword** — marks where page content goes inside a layout
- **`(folder)`** — route group: organizes pages without affecting URL
- **`[slug]`** — dynamic route: URL segment becomes a parameter
- **`route.tw`** — API endpoint (uses `.twm` module syntax)
- **`not-found.tw`** — custom 404 page

### Layout Example

```tw
// [home]/layout.tw

page {
    title "My Site"
    render static
}

body {
    nav { class "navbar"
        a "Home" { href "/", class "nav-link" }
        a "About" { href "/about", class "nav-link" }
    }
    main { class "content"
        children
    }
    footer { class "footer"
        p "Built with TW"
    }
}
```

The `children` keyword injects page content. Every page inside this directory tree gets the navbar and footer automatically.

### Route Groups

```
[home]/
├── (main)/              ← URL: / (not /main)
│   ├── layout.tw        ← Shared layout (navbar, footer)
│   ├── page.tw          ← URL: /
│   └── about/page.tw    ← URL: /about
├── (auth)/              ← Different layout (no navbar)
│   ├── layout.tw
│   └── login/page.tw    ← URL: /login
```

### Dynamic Routes

```
[home]/blog/[slug]/page.tw  →  URL: /blog/:slug
```

Pre-render at build time with `generateStaticParams`:

```tw
page {
    title "Blog Post"
    render static
    generateStaticParams "./posts.json"
}

body {
    h1 "Post: {slug}"
}
```

### Client-Side Navigation

Use the `link` keyword for SPA-style navigation (no full page reload):

```tw
div {
    link "/about"
    "About Page"
}
```

This produces `<a href="/about" data-tw-link="/about">` and the router runtime intercepts the click, fetches the page via `fetch()`, and swaps the body content. Page cache, back/forward support, and fallback to full navigation included.

See `docs/app-router-guide.md` for the complete guide.

---

## Built-in Icons

60+ SVG icons with zero external dependency. No icon font, no external CSS, no JS.

```tw
import "Icon"

body {
    nav { class "navbar"
        Icon { name "home", class "icon" }
        a "Home" { href "/" }
    }
    footer {
        Icon { name "github", size 20 }
        Icon { name "twitter", size 20 }
    }
}
```

Icons render as inline SVG — no client-side JavaScript needed. Supports `name`, `size` (default 24), and `class` props.

Available icons: home, search, menu, close, arrow-right, arrow-left, check, chevron-down, chevron-up, user, settings, heart, star, github, twitter, mail, phone, calendar, clock, download, upload, plus, minus, edit, trash, eye, lock, unlock, sun, moon, external-link, copy, code, book, zap, globe, image, link, filter, bell, tag, folder, file, play, pause, refresh, wifi, camera, map-pin, shopping-cart, and more.

---

## Zero JS by Default

Write a page with `render static` and you get pure HTML + CSS. No runtime framework. No hydration. No Virtual DOM.

- Page has no `state`, `on:click`, `bind:value`, or `link` → **0KB JS**
- Page uses `let`, `each`, `if`, `{var}` interpolation → still **0KB JS** (rendered at build time)
- Page uses `state` or `on:click` → ships ~2KB reactive runtime
- Page uses `link` → ships ~2KB client-side router

---

## CLI Commands

| Command | Description |
|---|---|
| `tw create <name>` | Scaffold a new App Router project |
| `tw dev` | Start dev server with live reload |
| `tw build` | Production build (HTML/CSS/JS) |
| `tw build --prod` | Minified + compressed build |
| `tw build --force` | Bypass incremental cache |
| `tw build --clean` | Clean cache before build |
| `tw export` | Static export (HTML/CSS/JS only) |
| `tw preview` | Preview production build locally |
| `tw deploy` | Deploy to Vercel / Netlify / Cloudflare |
| `tw doctor` | Run project health checks |
| `tw dead` | Detect unused pages, components, layouts |
| `tw check <file>` | Print diagnostics for a .tw file |
| `tw info` | Show project summary |
| `tw ast <file>` | Print AST JSON for a source file |
| `tw clean` | Clean dist and cache folders |

---

## Language

- **`.tw` files** — markup + logic in one file. HTML-like syntax that compiles to clean HTML
- **`.tss` files** — CSS with a friendlier syntax. No semicolons required. CSS aliases (`bg` → `background`)
- **`.twm` modules** — server-side JavaScript modules for API routes and data fetching
- **Lib directory** — shared server-side functions via `lib/` folder
- **Type safety** — optional type annotations: `let count: number = 5`
- **Custom lexer + parser** — TW has its own tokenizer, parser, AST, IR, and code generator

---

## Project Structure

```
my-site/
├── tw.config              # Project configuration
├── package.json
├── [home]/                # Project root (literal square brackets)
│   ├── layout.tw           # Root layout
│   ├── page.tw             # Home page (/)
│   ├── style.tss           # Global stylesheet
│   ├── about/
│   │   └── page.tw         # /about
│   ├── counter/
│   │   └── page.tw         # /counter
│   ├── contact/
│   │   └── page.tw         # /contact
│   ├── not-found.tw        # 404 page
│   ├── api/
│   │   ├── contact/route.tw  # POST /api/contact
│   │   └── users/route.tw    # GET /api/users
│   ├── components/         # Reusable components
│   └── lib/                # Server-side functions
├── public/                 # Static assets
├── tests/                  # Test files
├── docs/                   # Documentation
├── pyproject.toml
└── vercel.json
```

---

## Build Optimizations

- HTML/CSS/JS minification (`--prod`)
- Gzip + Brotli precompression
- Content-hashed filenames for cache-busting
- Per-page code splitting with shared runtime chunk
- Zero-JS detection — static pages ship no framework JS
- Incremental cache — only rebuild changed pages

---

## Deploy

```bash
tw deploy
```

Vercel, Netlify, Cloudflare Pages — all supported. Or export static files and host anywhere. GitHub Pages, Docker, and Kubernetes configs included.

---

## Editor Support

**VS Code** — `vscode-tw/` extension provides syntax highlighting, autocomplete, live diagnostics, and hover docs for `.tw`, `.tss`, and `.twm` files.

**ACode (Android)** — `tw-language-acode.zip` plugin for Android code editor.

**LSP Server** — Built-in Language Server Protocol server works with any LSP-compatible editor.

---

## Backward Compatibility

The App Router is fully backward compatible with the legacy `[home]/pages/` + `[home]/layouts/` structure. The framework auto-detects which system to use:

- If `[home]/page.tw` or `[home]/layout.tw` exists → **App Router mode**
- If `[home]/pages/` exists → **Legacy mode**

Both modes work. You can migrate gradually.

---

## Documentation

- [App Router Guide](docs/app-router-guide.md) — Complete guide with examples
- [App Router Reference](docs/app-router.md) — Quick reference
- [TW Syntax](docs/02-tw-syntax.md) — Language reference
- [TSS Syntax](docs/03-tss-syntax.md) — Stylesheet syntax
- [CLI Reference](docs/05-cli-reference.md) — All CLI commands
- [Routing](docs/06-routing.md) — Legacy + App Router routing
- [Layouts](docs/08-layouts.md) — Legacy + App Router layouts

---

## Contributing

See [CONTRIBUTING.md](CONTRIBUTING.md). Run `tw doctor` to check your project health.

---

## License

MIT
