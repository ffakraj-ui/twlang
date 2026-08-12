# Build Pipeline

## Overview

The TW Framework compiler is a 11-stage pipeline that transforms `.tw` and `.tss` source files into static HTML, CSS, and JS in `dist/`.

## Stages

### 1. Lexing (lexer.py)
Tokenizes `.tw` source code into tokens (keywords, strings, identifiers, operators).

### 2. Parsing (parser.py)
Builds an AST from tokens. Supports:
- Page blocks (`page { ... }`)
- Elements (`div { ... }`)
- Components (`component Name { ... }`)
- Conditionals (`if`/`else`)
- Loops (`each items as item { ... }`)
- Let bindings (`let x = 42`)
- Script blocks
- Head blocks (meta, seo)

### 3. Semantic Analysis (semantic.py)
Type checking, scope resolution, error detection.

### 4. IR Lowering (lowering.py)
Converts AST to intermediate representation (IR) for optimization.

### 5. HTML Rendering (render_html.py)
Generates static HTML from IR.

### 6. CSS Rendering
Compiles TSS stylesheets, applies scoped CSS to components.

### 7. JS Bundling (client_bundler.py)
Bundles client-side JavaScript, code splitting, tree shaking.

### 8. Dead Code Detection (dead_code.py)
Finds unused pages, components, APIs, middleware.

### 9. Tree Shaking (tree_shaking.py)
Removes unused exports from client bundles.

### 10. Minification
HTML, CSS, and JS minification for production.

### 11. Output
Writes final files to `dist/`.

## Build Commands

```bash
tw build                    # Default build
tw build --prod             # Production optimizations (brotli, SRI)
tw build --watch            # Rebuild on change (HMR)
tw build --analyze          # Bundle analysis
tw build --report           # Build report
tw build --strict           # Treat warnings as errors
tw build --adapter vercel   # Vercel output format
tw build --workers 4        # Parallel compilation
```

## Build Constants

- `BUILD_MANIFEST_VERSION = 2`
- `DEPENDENCY_GRAPH_VERSION = 2`
- `CHUNKS_URL_PREFIX = "/_tw/static/chunks/"`
- `DEFAULT_WORKERS = max(1, min(32, os.cpu_count() or 1))`

## Production Optimizations

With `--prod`:
- Brotli pre-compression of static assets (requires `pip install tw-framework[compression]`)
- SRI (Subresource Integrity) hashes for CSS/JS
- HTML/CSS/JS minification
- Dead code elimination
- Tree shaking
