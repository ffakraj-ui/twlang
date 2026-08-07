<div align="center">

<img src="./tw.png" alt="TW LANGUAGE" width="100" height="100">

# TW Framework

**Write `.tw` and `.tss`. Ship a full website. Zero JavaScript by default.**

A custom language + framework for building websites — with its own lexer, parser, and compiler pipeline. No React, no Virtual DOM, no runtime framework. Just clean HTML, CSS, and JS that the browser actually needs.

[![PyPI version](https://img.shields.io/pypi/v/tw-framework.svg?color=22c55e)](https://pypi.org/project/tw-framework/)
[![PyPI downloads](https://img.shields.io/pypi/dm/tw-framework.svg?color=3b82f6)](https://pypi.org/project/tw-framework/)
[![License: MIT](https://img.shields.io/badge/License-MIT-yellow.svg)](./LICENSE)
[![GitHub stars](https://img.shields.io/github/stars/ffakraj-ui/twlang?style=social)](https://github.com/ffakraj-ui/twlang/stargazers)

[Why TW?](#why-tw) •
[Quick Start](#quick-start) •
[Features](#features) •
[Comparison](#how-tw-compares) •
[VS Code / ACode](#editor-support) •
[Deploying](#deploying) •
[Contributing](#contributing)

</div>

---

## Why TW?

The modern web is bloated. A typical Next.js landing page ships 90KB+ of JavaScript — for a page that could be pure HTML. React's Virtual DOM, hydration, and client-side routing add layers the browser never asked for.

**TW Framework takes a different stance:**

### 1. Zero JS by default

Write a page with `render static` and you get pure HTML + CSS. No runtime framework. No hydration. No Virtual DOM. The page loads instantly because there's nothing to execute.

Need interactivity? Add `on:click` or `bind:value` — TW ships only the exact JavaScript needed for that one interaction. Not a single byte more.

### 2. One language, one file

In Next.js you write `.jsx` + `.css` + `.ts` + `next.config.js` + `package.json`. In TW you write one `.tw` file — page config, markup, and logic together. Styles go in `.tss` files with a friendlier CSS syntax. That's it.

### 3. Built from scratch

TW has its own lexer, parser, AST, IR, and code generator. It's not a wrapper around React or Vue. It's not "React under the hood". When you write `div { class "hero" }`, TW compiles it to `<div class="hero">` — directly. No intermediate abstraction layer.

### 4. Build on your phone

TW Framework runs on Python. Python runs on Termux. Termux runs on Android. You can scaffold, develop, build, and deploy a full website from a ₹10,000 phone — no laptop required. No other framework offers this.

### 5. Deploy in one command

```bash
tw deploy
```

Vercel, Netlify, Cloudflare Pages — all supported. Or export static files and host anywhere. No CI/CD pipeline to configure.

---

## Quick Start

```bash
pip install tw-framework

tw create my-site
cd my-site
tw dev
```

Open `http://127.0.0.1:3000` — live-reloading dev server is running.

### Your first page

Create `[home]/pages/index.tw`:

```tw
page {
    title "Hello World"
    layout "main"
    render static
}

body {
    div {
        class "hero"

        h1 "Built with TW Framework"
        p "Zero JavaScript. Pure HTML. Lightning fast."

        a "Get Started" {
            href "/docs"
            class "btn btn-primary"
        }
    }
}
```

### Add styles in `[home]/style.tss`:

```css
.hero {
    text-align: center
    padding: 80px 20px
}

.btn {
    display: inline-block
    padding: 12px 28px
    border-radius: 8px
    font-weight: 600
    text-decoration: none
}

.btn-primary {
    background: #22c55e
    color: white
}
```

### Add interactivity — only when you need it:

```tw
button "Count: {count}" {
    on:click "count++"
    class "counter-btn"
}
```

TW ships a tiny reactive runtime (~2KB) only for pages that use `on:` or `bind:` directives. Static pages stay at 0KB JS.

---

## How TW Compares

| Feature | TW Framework | Next.js | Astro | SvelteKit |
|---|---|---|---|---|
| **JS shipped (static page)** | 0 KB | ~90 KB | 0 KB | ~45 KB |
| **JS shipped (interactive page)** | ~2 KB (per-component) | ~90 KB+ | ~4 KB+ | ~45 KB |
| **Language** | `.tw` / `.tss` (custom) | JSX / TS | `.astro` (HTML+) | `.svelte` |
| **Files per page** | 1 (`.tw`) | 3+ (`.jsx` + `.css` + `.ts`) | 2 (`.astro` + `.css`) | 2 (`.svelte` + `.ts`) |
| **Runtime framework** | None | React | None (islands) | Svelte |
| **Virtual DOM** | No | Yes | No | No |
| **Hydration** | Optional | Always (full or partial) | Optional (islands) | Always |
| **File-based routing** | Yes | Yes | Yes | Yes |
| **Dynamic routes** | `[slug].tw` | `[slug].tsx` | `[slug].astro` | `[slug].svelte` |
| **API routes** | `.twm` modules | API routes | Endpoints | Endpoints |
| **Middleware** | Built-in (`middleware.tw`) | Edge middleware | Integrations | Hooks |
| **SEO (meta/OG tags)** | Built-in (`seo {}`) | Needs `next-seo` | Built-in | Needs `svelte-seo` |
| **Built-in search** | Yes (auto-indexed) | Manual | Manual | Manual |
| **Code splitting** | Automatic (per-page) | Automatic | Automatic | Automatic |
| **Dead code detection** | `tw dead` (built-in) | Manual | Manual | Manual |
| **Deploy** | `tw deploy` (one command) | Vercel CLI | Vercel CLI | Adapter config |
| **Build on mobile** | Yes (Termux + Python) | No | No | No |
| **Learning curve** | Low (HTML-like syntax) | High (React + hooks + SSR) | Medium | Medium |
| **Install size** | `pip install` (~164 KB) | `npx create-next-app` (~500 MB+) | `npm create astro` (~200 MB+) | `npm create` (~300 MB+) |

### The key difference

Next.js, SvelteKit, and Remix are **application frameworks** — they assume you're building a complex web app with state, auth, databases, and client-side routing. They ship JavaScript because they need it.

Astro is close to TW's philosophy (zero JS by default), but it still lives in the Node/npm ecosystem — 200MB+ of `node_modules`, config files, and build tooling.

**TW Framework is a site framework.** It assumes you're building a website — landing pages, blogs, portfolios, docs, catalogs, marketing sites. For 80% of websites, that's all you need. And when you do need interactivity, you opt in per-component, not per-page.

---

## Features

### Language

- **`.tw` files** — markup + logic in one file. HTML-like syntax that compiles to clean HTML
- **`.tss` files** — CSS with a friendlier syntax. No semicolons required. CSS aliases (`bg` → `background`, `radius` → `border-radius`)
- **`.twm` modules** — server-side JavaScript modules for API routes and data fetching
- **Type safety** — optional TypeScript-style type annotations on `let` and `state` variables: `let count: number = 5`. Validated at parse time. Types: `string`, `number`, `boolean`, `array`, `object`, `null`, `any`
- **Custom lexer + parser** — TW has its own tokenizer, parser, AST, IR, and code generator. Not a wrapper around any existing framework

### Framework

- **File-based routing** — pages and dynamic routes (`[slug].tw`) from your folder structure
- **Layouts** — reusable layout chains: `layout "base > docs"`
- **Components** — colocated in `[home]/components/`, imported with `import "Hero"`
- **Reactive bindings** — `on:click`, `bind:value`, `bind:checked` for interactivity without writing raw JS
- **API routes** — `.twm` server functions for GET/POST/etc., colocated with your pages
- **Middleware** — auth, rate limiting, origin checks, custom headers — all declarative in `middleware.tw`
- **Built-in SEO** — `seo { description "..." og_title "..." }` — no plugins needed
- **Built-in search** — automatic search index generation, no extra setup
- **Environment variables** — `env: public: "API_KEY"` — only allow-listed vars reach page context (server-only by default)
- **Code splitting** — automatic per-page JS chunks with shared runtime
- **Dead code detection** — `tw dead` finds unused pages, components, layouts, and middleware

### CLI

| Command | Description |
|---|---|
| `tw create <name>` | Scaffold a new TW project |
| `tw dev` | Start the dev server with live reload |
| `tw build` | Generate a production build |
| `tw build --prod` | Minified, compressed, cache-busted build |
| `tw export` | Static export (HTML/CSS/JS only) |
| `tw preview` | Preview the production build locally |
| `tw deploy` | Build and deploy to Vercel / Netlify / Cloudflare |
| `tw doctor` | Run project health checks |
| `tw dead` | Detect unused pages, components, layouts |
| `tw check <file>` | Print diagnostics for a `.tw` file |
| `tw info` | Show project summary |
| `tw ast <file>` | Print the AST JSON for a source file |
| `tw clean` | Clean dist and cache folders |

### Build optimizations

- HTML/CSS/JS minification (`--prod`)
- Gzip + Brotli precompression (`.gz`, `.br` files generated at build time)
- Content-hashed filenames for cache-busting
- HTML references automatically updated to match hashed filenames (v0.4.3+)
- Per-page code splitting with shared runtime chunk

---

## Editor Support

### VS Code

The `vscode-tw/` extension provides:

- **Syntax highlighting** for `.tw`, `.twm`, and `.tss` files
- **Autocomplete** — HTML tags, TW keywords, CSS properties, event handlers, render modes
- **Live diagnostics** — real-time error checking as you type (unclosed braces, parser errors)
- **Hover info** — documentation on hover for HTML tags, CSS properties, and TW keywords

Install: copy `vscode-tw/` to your VS Code extensions folder, or build a `.vsix`.

### ACode (Android)

The `tw-language-acode.zip` plugin registers `.tw`, `.twm`, `.tss` file extensions in ACode with syntax highlighting and LSP integration.

Install: ACode → Settings → Plugins → Install from local → select `tw-language-acode.zip`.

### LSP Server

TW Framework includes a built-in Language Server Protocol server (`tw_framework/lsp_server.py`) that works with any LSP-compatible editor:

- Autocomplete for `.tw` (HTML tags, TW keywords, page directives) and `.tss` (CSS properties, aliases, values)
- Live diagnostics with exact error positions (underlines the exact token, not the whole line)
- Hover documentation for HTML tags, CSS properties, and TW keywords
- No false positives — understands `page {}` blocks, suppresses file-resolution errors in LSP context

Requires `tw-framework` installed via `pip install tw-framework`.

---

## Project Structure

```
my-site/
├── tw.config              # Project configuration
├── package.json
├── vercel.json            # Vercel deployment config
├── [home]/                # Project root (literal square brackets)
│   ├── index.tw           # Root page (renders at /)
│   ├── style.tss          # Global stylesheet
│   ├── pages/             # File-based routes
│   │   ├── about.tw
│   │   ├── contact.tw
│   │   └── [slug].tw      # Dynamic route
│   ├── components/        # Reusable components
│   │   ├── Hero.tw
│   │   └── Button.tw
│   ├── layouts/           # Layout templates
│   │   └── main.tw
│   ├── api/               # API routes (.twm modules)
│   └── middleware.tw      # Middleware (auth, rate limit, etc.)
```

**Critical:** The `[home]` directory (with literal square brackets) and `tw.config` file are required at the project root. Without `[home]/`, the build fails with: `RuntimeError: TW project root not found.`

---

## Deploying

### Vercel (recommended)

Create `vercel.json` in your project root:

```json
{
  "buildCommand": "pip install --break-system-packages tw-framework && python -m tw_framework.cli build --prod",
  "outputDirectory": "dist"
}
```

Then connect your GitHub repo to Vercel — it reads `vercel.json` automatically and serves the `dist/` folder.

### Netlify

```toml
[build]
command = "pip install tw-framework && python -m tw_framework.cli build --prod"
publish = "dist"
```

### Cloudflare Pages

**Build command:** `pip install tw-framework && python -m tw_framework.cli build --prod`
**Output directory:** `dist`

### Static export

```bash
tw export
```

Outputs pure HTML/CSS/JS to `dist/`. Host on GitHub Pages, S3, Netlify drop, or any static host.

### One-command deploy

```bash
tw deploy
```

Builds and deploys to your configured provider in one step.

For full deployment details, see [DEPLOYMENT.md](./DEPLOYMENT.md).

---

## Important Version Notes

### v0.4.5+ (current)

- LSP server with autocomplete and live diagnostics
- `--prod` flag is safe and recommended (HTML references auto-updated after filename hashing)
- Multi-line CSS values in `.tss` files work correctly
- Environment variables only exposed if explicitly allow-listed in `tw.config`
- Auto-closing braces disabled in VS Code extension (was causing `{}` insertion issues)

### Before v0.4.3

- `--prod` had a bug: CSS/JS filenames were hashed but HTML references were not updated, causing 404s
- Multi-line CSS values in `.tss` broke (parser split on every newline)

---

## Contributing

Issues and pull requests are welcome. If you find a bug, please open an issue with a minimal reproduction.

```bash
git clone https://github.com/ffakraj-ui/twlang.git
cd twlang
pip install -e .
tw create test-site
cd test-site
tw dev
```

---

## License

[MIT](./LICENSE)

---

<div align="center">

**Built with TW Framework. Zero JS by default. Ship fast.**

</div>
