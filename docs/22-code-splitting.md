# Code Splitting

TW Framework automatically splits JavaScript into chunks for optimal loading.

## How It Works

During build, TW:

1. Scans each page for `on:*` and `bind:*` directives
2. Extracts event handlers and reactive state into a page-specific JS chunk
3. Generates a shared runtime chunk (~2KB) with the reactive engine
4. Injects chunk references into HTML

## Chunk Structure

```
dist/
├── _tw/
│   ├── chunks/
│   │   ├── runtime.96b447cb8c15.js    # Shared reactive runtime (~2KB)
│   │   ├── ae1f0c3a.d364c7e5d24b.js   # Page-specific chunk
│   │   └── ...
│   └── static/
│       └── chunks/
│           ├── ae1f0c3a.css            # Page-specific CSS
│           └── ...
```

## When JS Is Generated

- **Static pages with no interactivity** → 0 KB JS
- **Pages with `on:click`** → ~2KB runtime + page chunk
- **Pages with `bind:value`** → ~2KB runtime + page chunk
- **Pages with `script {}` blocks** → bundled into page chunk

## Hashed Filenames

In `--prod` mode, filenames are content-hashed:

```
runtime.96b447cb8c15.js
ae1f0c3a.d364c7e5d24b.css
```

HTML references are automatically updated (v0.4.3+) to point to the correct hashed files.

## Cache Strategy

The shared runtime chunk is loaded once and cached by the browser. Page chunks are loaded on-demand per route.

## Precompression

In `--prod` mode, `.gz` and `.br` versions are generated:

```
runtime.96b447cb8c15.js
runtime.96b447cb8c15.js.gz
runtime.96b447cb8c15.js.br
```

The hosting platform (Vercel/Netlify/Cloudflare) serves the compressed version automatically.
