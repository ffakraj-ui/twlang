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

BODY {
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

## CLI Commands

| Command | Description |
|---|---|
| `tw create <name>` | Scaffold a new TW project |
| `tw dev` | Start the dev server with live reload |
| `tw build` | Generate a production build |
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

**Vercel** — connect your GitHub repo, TW's `vercel.json` handles the rest.
**GitHub Pages** — enable Pages (Source → GitHub Actions) and push; the included workflow builds and deploys automatically.

See [Deploying](#deploying) in the docs for provider-specific notes.

## Contributing

Issues and pull requests are welcome. If you find a bug, please open an issue with a minimal reproduction.

## License

[MIT](./LICENSE)
