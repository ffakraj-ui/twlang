# TW Framework

A Python-based full-stack web framework with App Router, Zero-JS static sites, multi-runtime API routes, and a custom DSL for pages, components, and layouts.

## Quick Start

```bash
pip install tw-framework
tw create my-site
cd my-site
tw build
```

## Features

- Custom DSL: `.tw` pages/components/layouts, `.tss` stylesheets, `.twm` API routes
- App Router with nested layouts, dynamic routes, catch-all, route groups
- Zero-JS static sites
- Multi-Runtime: Node.js, Edge V8, Python, WASM
- Reactive state management with Virtual DOM
- Streaming SSR with skeleton loaders
- Incremental Static Regeneration (ISR)
- Partial Prerendering
- Server Actions with CSRF support
- Plugin system with `.twp` format
- CLI: create, dev, build, export, preview, serve, deploy

## Installation

```bash
pip install tw-framework
pip install tw-framework[dev]
pip install tw-framework[image]
```

## License

MIT

## Authors

See `pyproject.toml` for the full list of contributors.
