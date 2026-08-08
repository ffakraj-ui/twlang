# Router Internals

## Route Discovery

TW discovers routes by scanning `[home]/pages/`:
1. Walk all .tw files in pages/
2. Convert file paths to URL routes
3. Detect dynamic segments ([slug])
4. Build route manifest

## Route Matching

When a request comes in:
1. Normalize URL path (strip trailing slash)
2. Check exact match (static routes)
3. Check dynamic routes ([slug] patterns)
4. Check API routes (/api/...)
5. Check special pages (404, 500)
6. Return 404 if no match

## Route Manifest

Generated at build time as `dist/_tw/route-manifest.json`:

```json
{
    "routes": [
        { "path": "/", "file": "pages/index.tw", "dynamic": false },
        { "path": "/about", "file": "pages/about.tw", "dynamic": false },
        { "path": "/blog/:slug", "file": "pages/blog/[slug].tw", "dynamic": true }
    ]
}
```

## Route Priority

1. Exact static match - /about matches about.tw
2. Nested static - /blog/post matches blog/post.tw
3. Dynamic segment - /blog/hello matches blog/[slug].tw
4. API routes - /api/* matches .twm files
5. 404 page - [home]/pages/404.tw

## Route Collisions

If two pages produce the same route:

```
Warning: Route collision: /blog detected from:
  - [home]/pages/blog/index.tw
  - [home]/pages/blog.tw
```

Fix by removing one file.

## API Route Discovery

```
api/hello.twm          -> /api/hello
api/users/route.twm    -> /api/users
api/users/[id]/route.twm -> /api/users/:id
```
