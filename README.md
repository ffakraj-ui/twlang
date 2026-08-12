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

- **Custom DSL**: `.tw` pages/components/layouts, `.tss` stylesheets, `.twm` API routes
- **App Router**: File-based routing with nested layouts, dynamic routes, catch-all, route groups
- **Zero-JS Static Sites**: Pages without state/events ship no JavaScript
- **Multi-Runtime**: Node.js, Edge V8, Python, WASM runtimes for API routes
- **Reactive State**: Built-in state management with Virtual DOM
- **Streaming SSR**: Server-side rendering with skeleton loaders
- **ISR**: Incremental Static Regeneration for stale-while-revalidate
- **Partial Prerendering**: Component-level static/dynamic boundaries
- **Server Actions**: Progressive enhancement with CSRF support
- **Plugin System**: `.twp` format with lifecycle hooks
- **CLI**: create, init, dev, build, export, preview, serve, deploy commands

## Installation

```bash
pip install tw-framework
pip install tw-framework[dev]     # With pytest
pip install tw-framework[image]   # With Pillow
```

## License

MIT

## Authors

See `pyproject.toml` for the full list of contributors.
