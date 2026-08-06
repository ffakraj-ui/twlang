<div align="center">

<img src="./tw-logo.svg" alt="TW logo" width="100" height="100">

# TW Framework

**A custom language + framework for building websites — write `.tw` / `.tss`, ship a full site.**

[![PyPI version](https://img.shields.io/pypi/v/tw-framework.svg?color=22c55e)](https://pypi.org/project/tw-framework/)
[![PyPI downloads](https://img.shields.io/pypi/dm/tw-framework.svg?color=3b82f6)](https://pypi.org/project/tw-framework/)
[![License: MIT](https://img.shields.io/badge/License-MIT-yellow.svg)](./LICENSE)
[![GitHub stars](https://img.shields.io/github/stars/ffakraj-ui/twlang?style=social)](https://github.com/ffakraj-ui/twlang/stargazers)

[Getting Started](#getting-started) •
[CLI Commands](#cli-commands) •
[Features](#features) •
[Deploying](#deploying) •
[Contributing](#contributing)

</div>

---

## What is TW?

TW is both a **language** and a **framework**, in one package — comparable to TypeScript + Next.js combined:

- **Language** — `.tw` files (markup + logic) and `.tss` files (styles) compile down to plain HTML, CSS, and JS. TW has its own lexer, parser, and compiler pipeline.
- **Framework** — file-based routing, API routes, middleware, authentication helpers, a dev server with live reload, and one-command deploys to Vercel, Netlify, and Cloudflare Pages.

```tw
page {
    title "Home"
    layout "main"
    render static
}

body {
    h1 "Hello from TW"
    p "Write .tw and .tss files. Run tw dev. Ship fast."
}
```

## Getting Started

```bash
pip install tw-framework

tw create my-site
cd my-site
tw dev
```

Open `http://127.0.0.1:3000` — you now have a live-reloading dev server.

## Project Structure

A valid TW project must have this layout:

```
my-site/
├── tw.config
├── package.json
├── vercel.json              (for Vercel deployments)
├── [home]/
│   ├── index.tw
│   ├── style.tss
│   ├── pages/
│   ├── components/
│   ├── layouts/
│   └── api/
```

**Critical:** The `[home]` directory (with literal square brackets) is required. The `tw.config` file is required. Both must exist at the project root. Without `[home]/`, the build fails with: `RuntimeError: TW project root not found.`

The root page must be `[home]/pages/index.tw` for the site to load at `/`.

## CLI Commands

| Command | Description |
|---|---|
| `tw create <name>` | Scaffold a new TW project |
| `tw dev` | Start the dev server with live reload |
| `tw build` | Generate a production build |
| `tw build --prod` | Production build with minification, compression, cache-busting |
| `tw preview` | Preview the production build locally |
| `tw doctor` | Run project health checks |
| `tw deploy` | Build and deploy to a hosting provider |
| `tw check <file>` | Print diagnostics for a `.tw` file |

## Features

- 📄 **File-based routing** — pages and dynamic routes (`[slug].tw`) from your folder structure
- ⚡ **Reactive bindings** — `on:click`, `bind:value` for interactivity without writing raw JS
- 🔌 **API routes** — `.twm` server functions for GET/POST/etc., colocated with your pages
- 🛡️ **Middleware** — auth, rate limiting, origin checks, custom headers — all declarative
- 🎨 **`.tss` stylesheets** — CSS with a friendlier syntax, animations, and variables
- 🔍 **Built-in search** — automatic search index generation, no extra setup
- 🚀 **Zero-config deploys** — Vercel, Netlify, and Cloudflare Pages adapters included

## Deploying

### Vercel (recommended)

Create a `vercel.json` in your project root:

```json
{
  "buildCommand": "pip install --break-system-packages tw-framework && python -m tw_framework.cli build --prod",
  "outputDirectory": "dist"
}
```

**Why each part:**
- `--break-system-packages` — Vercel's Python is managed by `uv`; bare `pip install` is rejected without this.
- `python -m tw_framework.cli` — the `tw` CLI entry-point is not always on PATH after install on Vercel. Using `python -m` is reliable.
- `--prod` — enables minification, gzip/brotli precompression, and cache-busting (safe on v0.4.3+).

Then connect your GitHub repo to Vercel — it reads `vercel.json` automatically and serves the `dist/` folder.

### Netlify

Create a `netlify.toml`:

```toml
[build]
command = "pip install tw-framework && python -m tw_framework.cli build --prod"
publish = "dist"
```

### Cloudflare Pages

**Build command:** `pip install tw-framework && python -m tw_framework.cli build --prod`
**Build output directory:** `dist`

### GitHub Pages

Enable Pages (Source → GitHub Actions) and push. The included workflow builds and deploys automatically.

For full deployment details, see [DEPLOYMENT.md](./DEPLOYMENT.md).

## Important Version Notes

### v0.4.3+ (current)

- `--prod` flag is safe and recommended — HTML references are automatically updated after filename hashing.
- Multi-line CSS values in `.tss` files work correctly.
- Environment variables are only exposed to pages if explicitly allow-listed in `tw.config` via `env: public: "VAR_NAME"`.

### Before v0.4.3

- `--prod` has a bug: CSS/JS filenames are hashed but HTML `<link>`/`<script>` references are not updated, causing 404s and broken styles. Use `--dev` as a workaround.
- Multi-line CSS values in `.tss` break — keep all property values on a single line.

## Contributing

Issues and pull requests are welcome. If you find a bug, please open an issue with a minimal reproduction.

## License

[MIT](./LICENSE)
