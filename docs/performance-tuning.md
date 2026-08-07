# Performance Tuning

This guide covers advanced techniques to make your TW Framework sites blazing fast.

## Build-Time Optimizations

### Production Builds

Always use `--prod` for production:

```bash
tw build --prod
```

This enables:
- HTML/CSS/JS minification
- Gzip and Brotli precompression
- Content-hashed filenames for cache busting
- Dead code elimination

### Incremental Builds

TW caches build results. Only changed pages are rebuilt:

```bash
tw build
```

To force a full rebuild:

```bash
tw build --force
```

### Parallel Compilation

Use multiple workers for faster builds:

```bash
tw build --workers 4
```

## Asset Optimization

### Image Optimization

1. **Use modern formats**: Prefer WebP or AVIF over PNG/JPEG.
2. **Responsive images**: Use `srcset` for different screen sizes.
3. **Lazy loading**: TW auto-adds `loading="lazy"` to images.

```tw
picture {
    source { srcset "/assets/hero.avif" type "image/avif" }
    source { srcset "/assets/hero.webp" type "image/webp" }
    img {
        src "/assets/hero.jpg"
        alt "Hero image"
        width "1200"
        height "600"
    }
}
```

### Font Optimization

1. **Use `font-display: swap`**: Prevent invisible text during load.
2. **Subset fonts**: Only include characters you need.
3. **Preload critical fonts**:

```tw
head {
    link { rel "preload" href "/fonts/inter.woff2" as "font" type "font/woff2" crossorigin "anonymous" }
}
```

### CSS Optimization

1. **Split styles**: Load only what each page needs.
2. **Use CSS variables**: Reduce repetition.
3. **Avoid `@import`**: Use `load` directives instead.

```tw
// Good — page-specific styles
load "@./style/product-detail.tss"

// Avoid — global styles for every page
// (Only put truly global styles in style.tss)
```

## Runtime Optimizations

### Zero JavaScript Pages

Use `render static` for content pages:

```tw
page {
    title "About Us"
    render static
}
```

These pages ship **0 KB JavaScript**.

### Selective Reactivity

Only add interactivity where needed:

```tw
// This page ships ~2KB JS (just the counter)
page {
    title "Counter Demo"
    render static
}

body {
    h1 "Counter"
    p "Count: {count}"
    button "+" { on:click "count++" }
    button "-" { on:click "count--" }
}
```

### Router Optimization

Use `goto` for client-side navigation instead of full page loads:

```tw
a "Dashboard" {
    href "/dashboard"
    goto "/dashboard"
}
```

This prevents full page reloads and preserves state.

## Caching Strategies

### Page-Level Caching

```tw
page {
    title "Products"
    render server
    revalidate 3600  // Cache for 1 hour
}
```

### Static Asset Caching

TW generates hashed filenames. Configure your CDN:

```
/assets/*.[hash].css    →  Cache 1 year
/assets/*.[hash].js     →  Cache 1 year
/*.html                 →  Cache 1 hour (or revalidate)
```

### API Response Caching

```twm
function get_products(request):
    cache_key = "products:all"
    cached = cache.get(cache_key)
    if cached:
        return json_response(cached)

    products = db.products.all()
    cache.set(cache_key, products, ttl=300)  // 5 minutes
    return json_response(products)
```

## Bundle Analysis

### Check Bundle Size

```bash
tw build --prod
du -sh dist/
ls -la dist/assets/js/
```

### Identify Heavy Pages

```bash
tw info
```

Shows per-page bundle sizes and dependencies.

## Database Optimization

### Connection Pooling

```python
# In your .twm module
from db_pool import get_connection

def get_users(request):
    with get_connection() as conn:
        users = conn.query("SELECT * FROM users LIMIT 100")
        return json_response(users)
```

### Query Optimization

1. **Select only needed columns**.
2. **Use indexes** on frequently queried fields.
3. **Paginate large result sets**:

```twm
function list_posts(request):
    page = int(request.args.get("page", 1))
    per_page = int(request.args.get("per_page", 20))
    offset = (page - 1) * per_page

    posts = db.posts.limit(per_page).offset(offset).all()
    total = db.posts.count()

    return json_response({
        "posts": posts,
        "page": page,
        "per_page": per_page,
        "total": total
    })
```

## Monitoring Performance

### Core Web Vitals

Track these metrics:

| Metric | Target | TW Default |
|--------|--------|------------|
| LCP (Largest Contentful Paint) | < 2.5s | Usually < 1s (static) |
| FID (First Input Delay) | < 100ms | 0ms (no JS) |
| CLS (Cumulative Layout Shift) | < 0.1 | Low (explicit dimensions) |
| TTFB (Time to First Byte) | < 600ms | Depends on hosting |

### Build Performance Report

```bash
tw build --prod
tw build-report
```

Generates a report showing:
- Build duration per page
- Total bundle size
- Asset breakdown
- Cache hit rate

## Checklist

- [ ] Using `--prod` for production builds
- [ ] Images are optimized and lazy-loaded
- [ ] Fonts use `font-display: swap`
- [ ] Static pages use `render static`
- [ ] Reactive features are minimal
- [ ] API responses are cached
- [ ] CDN is configured for hashed assets
- [ ] Database queries are indexed and paginated
- [ ] Core Web Vitals are monitored
