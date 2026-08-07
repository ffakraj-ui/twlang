# Advanced Routing

## Catch-All Routes

Use [...slug] for catch-all routes:

```
[home]/pages/
├── docs/
│   └── [...path].tw     -> /docs/* (catches /docs/a, /docs/a/b, /docs/a/b/c)
```

## Route Priority

TW resolves routes in this order:

1. Exact match (/about -> about.tw)
2. Static nested (/blog/post -> blog/post.tw)
3. Dynamic (/users/123 -> users/[id].tw)
4. Index (/blog -> blog/index.tw)
5. Catch-all (/* -> [...slug].tw)
6. 404 (404.tw)

## Route Params

### Single param

```
[home]/pages/users/[id].tw -> /users/123
```

```tw
page { render server }
body {
    h1 "User ID: {params.id}"
}
```

### Multiple params

```
[home]/pages/blog/[category]/[slug].tw -> /blog/tech/hello-world
```

```tw
page { render server }
body {
    h1 "Category: {params.category}"
    h2 "Slug: {params.slug}"
}
```

## Query Parameters

```tw
page { render server }
body {
    p "Page: {params.page}"
    p "Sort: {params.sort}"
}
```

URL: /products?page=2&sort=price

## Special Pages

| File | Purpose |
|---|---|
| [home]/pages/404.tw | Custom 404 page |
| [home]/pages/500.tw | Custom 500 error page |

## Redirects and Rewrites

In tw.config:

```
redirects {
  rule {
    source "/old/:slug"
    destination "/new/:slug"
    permanent true
  }
}

rewrites {
  rule {
    source "/api"
    destination "/api/health"
  }
}
```
