# Routing

TW Framework uses file-based routing — your folder structure determines the URLs.

## Static Routes

| File | URL |
|---|---|
| `[home]/index.tw` | `/` |
| `[home]/about.tw` | `/about` |
| `[home]/contact.tw` | `/contact` |
| `[home]/blog/index.tw` | `/blog` |
| `[home]/blog/post.tw` | `/blog/post` |

## Dynamic Routes

Use `[param]` syntax for dynamic segments:

| File | URL | Param |
|---|---|---|
| `[home]/[slug].tw` | `/hello` | `slug = "hello"` |
| `[home]/blog/[slug].tw` | `/blog/my-post` | `slug = "my-post"` |
| `[home]/users/[id].tw` | `/users/123` | `id = "123"` |

## Nested Dynamic Routes

```
[home]/
├── [slug].tw                    → /:slug
├── blog/
│   ├── index.tw                 → /blog
│   └── [slug].tw               → /blog/:slug
└── users/
    ├── index.tw                 → /users
    └── [id]/
        ├── index.tw             → /users/:id
        └── settings.tw          → /users/:id/settings
```

## Accessing Route Params

In `.tw` files:

```tw
page { render server }

body {
    h1 "Post: {params.slug}"
    p "User ID: {params.id}"
}
```

In `.twm` API handlers:

```js
export function GET(request) {
    const slug = request.params.slug;
    return { status: 200, json: { slug } };
}
```

---

## App Router (v0.9.30+)

TW Framework v0.9.30 introduces the **App Router** — a file-system based routing
system where layouts are TW components (not HTML templates) and routes are
defined by `page.tw` files in nested directories.

### Structure

```
[home]/
├── page.tw                ← URL: /
├── about/
│   └── page.tw            ← URL: /about
├── blog/
│   ├── page.tw            ← URL: /blog
│   └── [slug]/
│       └── page.tw        ← URL: /blog/:slug
└── api/
    └── apps/
        └── route.tw       ← API: /api/apps
```

### Route Groups `(folder)`

Folders in parentheses are excluded from the URL:

```
[home]/(main)/about/page.tw  →  URL: /about (not /main/about)
```

### Dynamic Routes `[slug]`

```
[home]/blog/[slug]/page.tw  →  URL: /blog/:slug
[home]/[...path]/page.tw    →  URL: /*path (catch-all)
```

### Auto-Detection

The framework auto-detects which routing system to use:

- If `[home]/page.tw` or `[home]/layout.tw` exists → **App Router mode**
- If `[home]/` exists → **Legacy mode**

Both modes are fully supported. See `docs/app-router.md` for the full guide.

## Redirects and Rewrites

Configure in `tw.config`:

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
    source "/games"
    destination "/category/games"
  }
}
```

### Redirect vs Rewrite

- **Redirect** — sends a 301/302 to the browser, URL changes
- **Rewrite** — serves different content internally, URL stays the same

## Pretty URLs

Enabled by default in `tw.config`:

```
pretty_urls: true
```

- `/about` serves `about.tw` (no `.html` extension)
- Trailing slashes are stripped

## Route Collisions

TW detects route collisions during build and warns:

```
⚠ Route collision: /blog detected from both [home]/blog/index.tw and [home]/blog.tw
```

Fix by removing one of the conflicting files.

## 404 Pages

Create `[home]/404.tw` for a custom 404 page:

```tw
page { title "Not Found" }

body {
    div {
        class "error-page"
        h1 "404 - Page Not Found"
        a "Go Home" { href "/" }
    }
}
```
