# Performance

## Zero JS by Default

Static pages ship 0 bytes of JavaScript. The browser loads pure HTML + CSS — nothing to parse, nothing to execute.

## Reactive Runtime (~2KB)

Pages with interactivity (`on:click`, `bind:value`) load a tiny ~2KB reactive runtime. This is the only JS shipped.

## Build Optimizations (--prod)

| Optimization | Description |
|---|---|
| HTML minification | Whitespace, comments removed |
| CSS minification | Shortened property values, removed whitespace |
| JS minification | Variable mangling, dead code removal |
| Gzip precompression | `.gz` files generated at build time |
| Brotli precompression | `.br` files generated at build time |
| Content hashing | Filenames include hash for cache-busting |
| Tree shaking | Unused exports removed from .twm modules |

## Code Splitting

- Shared runtime chunk: loaded once, cached by browser
- Page chunks: loaded per-route, only when needed
- Static pages: no JS chunks at all

## Incremental Cache

TW caches compiled pages in `.tw/` directory:

- Unchanged pages load from cache (instant)
- Only modified pages recompile
- `tw build --force` bypasses cache

## Performance Tips

### 1. Use `render static` by default

```tw
page { render static }
```

Static pages are pre-rendered at build time — fastest possible load.

### 2. Lazy-load interactivity

Only add `on:click` where needed:

```tw
// This page ships 0 JS:
page { render static }
body { h1 "Hello", p "No JS needed" }

// This page ships ~2KB JS:
page { render static }
body {
    button "Click" { on:click "alert('hi')" }
}
```

### 3. Use CSS aliases for smaller source

```css
.card {
    bg #fff          /* instead of background */
    radius 8px       /* instead of border-radius */
    shadow 0 2px 4px rgba(0,0,0,0.1)  /* instead of box-shadow */
}
```

### 4. Compress images externally

TW doesn't process images. Use pre-compressed images:

```tw
img { src "/hero.webp" alt "Hero" loading "lazy" }
```

### 5. Cache static assets

In `tw.config`:

```
headers {
  rule {
    source "/_tw/**"
    set "Cache-Control" "public, max-age=31536000, immutable"
  }
}
```

### 6. Use `revalidate` for semi-dynamic pages

```tw
page {
    render static
    revalidate 3600  // Regenerate at most once per hour
}
```

## Build Report

```bash
tw build --prod --report
```

Shows:
- Total output size
- Per-page sizes
- JS/CSS chunk sizes
- Cache hit/miss ratio
- Build duration

## Analyze Bundle

```bash
tw build --prod --analyze
```

Shows dependency graph and detailed size breakdown.
