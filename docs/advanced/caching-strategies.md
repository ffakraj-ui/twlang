# Caching Strategies

Speed up your TW Framework site with smart caching at every layer.

## Why Cache?

| Without Cache | With Cache |
|---------------|------------|
| Database query every request | Serve from memory |
| External API call every page load | Reuse previous response |
| Full page rebuild on every visit | Serve pre-built HTML |
| Slow TTFB | Instant response |

## Types of Caching

### 1. Page-Level Caching

Cache entire HTML pages for static routes:

```tw
page {
    title "Products"
    layout "main"
    render static
    revalidate 3600  // Rebuild every hour
}
```

For server-rendered pages:

```tw
page {
    title "Dashboard"
    layout "main"
    render server
    cache 300  // Cache for 5 minutes
}
```

### 2. API Response Caching

```twm
function get_products(request):
    cache_key = "api:products:all"

    # Try cache first
    cached = redis.get(cache_key)
    if cached:
        return json_response(json.loads(cached))

    # Fetch from database
    conn = get_db()
    products = conn.execute("SELECT * FROM products").fetchall()
    conn.close()

    # Store in cache
    redis.setex(cache_key, 300, json.dumps(products))
    return json_response(products)
```

### 3. Database Query Caching

Cache expensive queries:

```python
# [home]/db/cache_queries.py
from functools import wraps
import json
from db.cache import cache_get, cache_set

def cached_query(ttl=300):
    def decorator(func):
        @wraps(func)
        def wrapper(*args, **kwargs):
            cache_key = f"query:{func.__name__}:{hash(str(args))}"
            cached = cache_get(cache_key)
            if cached:
                return cached
            result = func(*args, **kwargs)
            cache_set(cache_key, result, ttl)
            return result
        return wrapper
    return decorator

@cached_query(ttl=600)
def get_popular_posts(limit=10):
    conn = get_db()
    posts = conn.execute(
        "SELECT * FROM posts ORDER BY views DESC LIMIT ?",
        (limit,)
    ).fetchall()
    conn.close()
    return [dict(p) for p in posts]
```

### 4. Asset Caching

TW Framework automatically hashes asset filenames:

```
/assets/style.abc123.css
/assets/main.def456.js
```

Configure your CDN or web server:

```nginx
# Nginx
location ~* \.(css|js|png|jpg|webp|avif|woff2)$ {
    expires 1y;
    add_header Cache-Control "public, immutable";
}

location ~* \.html$ {
    expires 1h;
    add_header Cache-Control "public, must-revalidate";
}
```

### 5. CDN Caching

For Cloudflare:

1. Set Page Rule: `*.html` → Cache Level: Cache Everything
2. Set Edge TTL: 2 hours for HTML, 1 year for assets
3. Enable Always Online for fallback

### 6. Stale-While-Revalidate

Serve stale content while refreshing in background:

```twm
function get_data(request):
    cache_key = "data:latest"
    cached = cache_get(cache_key)

    if cached:
        # Serve immediately, refresh in background
        if is_stale(cached):
            threading.Thread(target=refresh_cache, args=(cache_key,)).start()
        return json_response(cached["data"])

    data = fetch_fresh_data()
    cache_set(cache_key, {"data": data, "timestamp": time.time()}, ttl=3600)
    return json_response(data)
```

### 7. Cache Invalidation

Invalidate cache when data changes:

```twm
function create_post(request):
    data = request.json()
    conn = get_db()
    conn.execute("INSERT INTO posts ...", (...))
    conn.commit()
    conn.close()

    # Invalidate related caches
    cache_delete("api:posts:all")
    cache_delete("query:get_popular_posts:*")
    cache_delete("feed:rss")

    return json_response({"success": True}, status=201)
```

## Cache Warming

Pre-populate cache after deployment:

```python
# [home]/scripts/warm_cache.py
import requests

ROUTES = ["/", "/blog", "/products", "/about"]

def warm_cache():
    for route in ROUTES:
        try:
            response = requests.get(f"http://localhost:3000{route}")
            print(f"Warmed: {route} ({response.status_code})")
        except Exception as e:
            print(f"Failed: {route} ({e})")

if __name__ == "__main__":
    warm_cache()
```

## Cache Headers Reference

| Header | Meaning |
|--------|---------|
| `Cache-Control: no-cache` | Always revalidate |
| `Cache-Control: no-store` | Never cache |
| `Cache-Control: public, max-age=3600` | Cache for 1 hour |
| `Cache-Control: private` | Browser only, no CDN |
| `ETag: "abc123"` | Content version identifier |
| `Last-Modified: Wed, 21 Oct 2024 07:28:00 GMT` | Modification time |
| `Vary: Accept-Encoding` | Cache separately per encoding |

## Best Practices

1. **Cache at the highest level**: CDN > Page > API > Database.
2. **Set appropriate TTLs**: Static assets = 1 year, API = minutes, HTML = hours.
3. **Invalidate on write**: Don't wait for TTL expiry.
4. **Monitor cache hit rates**: Aim for > 80% on static assets.
5. **Use cache-busting**: Hash filenames for immutable assets.
6. **Handle cache misses gracefully**: Don't crash if Redis is down.
