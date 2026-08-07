# Build Pipeline

## Overview

When you run `tw build`, TW Framework:

1. Reads `tw.config`
2. Discovers all pages in `[home]/pages/`
3. Tokenizes each `.tw` file (lexer)
4. Parses tokens into AST (parser)
5. Resolves layouts and components
6. Compiles AST to HTML
7. Compiles `.tss` files to CSS
8. Compiles `.twm` modules to JS
9. Generates route manifest
10. Generates search index
11. Applies production optimizations
12. Writes output to `dist/`

## --prod Flag

`tw build --prod` enables:

- HTML minification
- CSS minification
- JS minification
- Gzip precompression (`.gz` files)
- Brotli precompression (`.br` files)
- Content-hashed filenames
- HTML references auto-updated to match hashed filenames (v0.4.3+)

## Code Splitting

TW automatically splits JavaScript:

- **Runtime chunk** — shared reactive runtime (~2KB), loaded once
- **Page chunks** — per-page JS (event handlers, bindings)
- **API chunks** — `.twm` module handlers

Only pages that use `on:` or `bind:` directives get JS chunks. Static pages get zero JS.

## Incremental Cache

TW caches compiled pages in `.tw/` directory. On subsequent builds:

- Unchanged pages are loaded from cache
- Only modified pages are recompiled
- Use `--force` to bypass cache

## Dead Code Detection

During build, TW can detect:
- Orphaned pages (not linked anywhere)
- Unused components
- Unused layouts
- Unused middleware rules

Use `tw dead` to run detection separately.

## Tree Shaking

Unused exports from `.twm` modules are removed during production builds.

## Build Report

Use `--report` flag to generate a build report:

```bash
tw build --prod --report
```

Report includes:
- Pages compiled
- Build duration
- Output size breakdown
- Cache hit/miss ratio
- Performance metrics

## Build Analyze

Use `--analyze` for detailed analysis:

```bash
tw build --prod --analyze
```

Shows:
- Bundle sizes per page
- Dependency graph
- Code splitting chunks
- Performance score

## Parallel Workers

Use `--workers <n>` for parallel compilation:

```bash
tw build --prod --workers 4
```

Default: number of CPU cores.
