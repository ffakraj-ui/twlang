# HTTP Caching Strategies

## Cache-Control Headers

In `tw.config`:

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

## Cache Strategies

| Strategy | Header | Use Case |
|---|---|---|
| No cache | no-store, no-cache, private | API responses, auth |
| Short cache | max-age=60 | News, frequently updated |
| Medium cache | max-age=3600 (1 hour) | Blog posts |
| Long cache | max-age=86400 (1 day) | Static assets |
| Immutable | max-age=31536000, immutable | Hashed JS/CSS chunks |

## Stale-While-Revalidate

```
set "Cache-Control" "public, s-maxage=3600, stale-while-revalidate=86400"
```

Serves cached content immediately while revalidating in the background.

## Revalidation in Pages

```tw
page {
    render static
    revalidate 3600
}
```

## Cache by User

```tw
page {
    render static
    cache_by "user:role"
    cache_size 100
}
```

Creates separate cached versions per user role.

## CDN Caching

For Vercel/Cloudflare, `s-maxage` controls CDN caching:

```
set "Cache-Control" "public, s-maxage=3600, stale-while-revalidate=86400"
```
