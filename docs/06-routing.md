# Routing

TW Framework uses file-based routing — your folder structure determines the URLs.

## Static Routes

| File | URL |
|---|---|
| `[home]/pages/index.tw` | `/` |
| `[home]/pages/about.tw` | `/about` |
| `[home]/pages/contact.tw` | `/contact` |
| `[home]/pages/blog/index.tw` | `/blog` |
| `[home]/pages/blog/post.tw` | `/blog/post` |

## Dynamic Routes

Use `[param]` syntax for dynamic segments:

| File | URL | Param |
|---|---|---|
| `[home]/pages/[slug].tw` | `/hello` | `slug = "hello"` |
| `[home]/pages/blog/[slug].tw` | `/blog/my-post` | `slug = "my-post"` |
| `[home]/pages/users/[id].tw` | `/users/123` | `id = "123"` |

## Nested Dynamic Routes

```
[home]/pages/
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
⚠ Route collision: /blog detected from both [home]/pages/blog/index.tw and [home]/pages/blog.tw
```

Fix by removing one of the conflicting files.

## 404 Pages

Create `[home]/pages/404.tw` for a custom 404 page:

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
