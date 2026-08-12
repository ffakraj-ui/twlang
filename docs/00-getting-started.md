# Getting Started with TW Framework

## Install

```bash
pip install tw-framework
```

Optional features (zero hard dependencies in core):
```bash
pip install tw-framework[image]        # Pillow — image optimization
pip install tw-framework[compression]  # brotli — pre-compression
pip install tw-framework[edge-v8]       # py_mini_racer — V8 sandbox
pip install tw-framework[redis]        # redis — SSR cache
pip install tw-framework[wasm]         # wasmtime — WASM runtime
pip install tw-framework[all]           # All combined
```

## Create a Project

```bash
tw create my-site
cd my-site
```

This creates:
```
my-site/
  tw.config              # project config
  .env                   # environment variables
  middleware.tw          # middleware
  [home]/                 # App Router root
    layout.tw            # root layout
    page.tw              # home page
    not-found.tw         # 404 page
    style.tss            # global stylesheet
    about/page.tw        # /about
    blog/page.tw         # /blog
    blog/[slug]/page.tw  # /blog/:slug
    blog/posts.json      # blog data
    counter/page.tw      # reactive counter
    contact/page.tw      # contact form
    components/           # Navbar, Footer, Button, Card
    api/                  # contact, users API routes
```

## Dev Server

```bash
tw dev
```

Starts at `http://127.0.0.1:3000` with HMR (Hot Module Replacement).
Save a `.tw` file → browser updates instantly.

Flags: `--host`, `--port`, `--no-open`, `--no-minify`, `--workers`

## Build

```bash
tw build --prod
```

Outputs to `dist/` — deploy anywhere.

Flags: `--watch`, `--analyze`, `--report`, `--strict`, `--adapter`, `--workers`

## Preview

```bash
tw preview
```

Previews built site at `http://127.0.0.1:4173`.

## Production Server

```bash
tw serve
```

Runs SSR server at `http://0.0.0.0:8000`.

## Deploy

```bash
tw deploy --provider vercel --prod
```

Supports: vercel, netlify, cloudflare, github-pages, docker.
Use `--dry-run` to preview.
