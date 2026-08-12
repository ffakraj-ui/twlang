# Cache Strategies

## Page-Level Caching

### Static with revalidate

```tw
page {
    render static
    revalidate 3600
}
```

Page generated at build time, re-generated after TTL expires.

### Cache by key

```tw
page {
    render server
    cache_by "user:role"
    cache_size 1000
}
```

Different cache entries for different user roles.

## HTTP Cache Headers

In tw.config:

```
headers {
  rule {
    source "/_tw/**"
    set "Cache-Control" "public, max-age=31536000, immutable"
  }

  rule {
    source "/api/**"
    set "Cache-Control" "no-store, no-cache, private"
  }

  rule {
    source "/**"
    set "Cache-Control" "public, s-maxage=3600, stale-while-revalidate=86400"
  }
}
```

## Cache Header Values

| Value | Description |
|---|---|
| max-age=3600 | Browser caches for 1 hour |
| s-maxage=3600 | CDN caches for 1 hour |
| stale-while-revalidate=86400 | Serve stale while revalidating |
| immutable | File will never change |
| no-cache | Always revalidate |
| no-store | Never cache |
| private | Only browser cache |
| public | Browser and CDN can cache |

## Incremental Build Cache

TW caches compiled pages in .tw/ directory:

- Unchanged pages: loaded from cache
- Modified pages: recompiled
- Use --force to bypass: tw build --force

## Cache Busting

In --prod mode, TW adds content hashes to filenames:

```
runtime.96b447cb8c15.js
ae1f0c3a.d364c7e5d24b.css
```

When content changes, hash changes, forcing browsers to fetch new version.
