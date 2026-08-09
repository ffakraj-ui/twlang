# App Router (v0.7.0+)

TW Framework's App Router is a file-system based routing and layout system
inspired by Next.js App Router. Layouts are **TW components**, not raw HTML
templates. They nest automatically based on your directory structure.

## Quick Start

### 1. Directory Structure

```
[home]/
├── layout.tw              ← Root layout (wraps everything)
├── page.tw                ← Home page (URL: /)
├── (main)/                ← Route group (excluded from URL)
│   ├── layout.tw          ← Layout for all (main) pages
│   ├── page.tw             ← URL: / (route group doesn't add to URL)
│   ├── blog/
│   │   ├── page.tw         ← URL: /blog
│   │   └── [slug]/          ← Dynamic route
│   │       ├── layout.tw   ← Nested layout for blog posts
│   │       └── page.tw      ← URL: /blog/:slug
│   └── about/
│       └── page.tw         ← URL: /about
├── admin/                  ← Separate layout tree
│   ├── layout.tw           ← Admin layout (no (main) wrapper)
│   └── page.tw             ← URL: /admin
└── api/                    ← API routes
    └── apps/
        └── route.tw        ← URL: /api/apps
```

### 2. Root Layout

The root layout is the outermost wrapper. It provides `<html>`, `<head>`,
`<body>` structure, global styles, and fonts.

```
// [home]/layout.tw

page {
    title "My Site"
    render static
}

head {
    meta { charset "utf-8" }
    meta { name "viewport", content "width=device-width, initial-scale=1" }
}

body {
    children
}
```

### 3. Nested Layout

Layouts in subdirectories wrap all pages inside them.

```
// [home]/(main)/layout.tw

page {
    title "Main"
    render static
}

body {
    nav { class "navbar"
        a "Home" { href "/", class "nav-link" }
        a "Blog" { href "/blog", class "nav-link" }
        a "About" { href "/about", class "nav-link" }
    }
    main { class "content"
        children
    }
    footer { class "footer"
        p "© 2026 My Site"
    }
}
```

### 4. Page

Pages are `.tw` files named `page.tw`. They contain the actual page content.

```
// [home]/(main)/about/page.tw

page {
    title "About Us"
    render static
}

body {
    div { class "about-page"
        h1 "About Us"
        p "This is the about page."
    }
}
```

### 5. Dynamic Routes

Folder names in square brackets become dynamic URL segments.

```
// [home]/(main)/blog/[slug]/page.tw

page {
    title "Blog Post"
    render static
}

body {
    article { class "blog-post"
        h1 "Blog Post Title"
        p "The slug parameter is available in context."
    }
}
```

URL: `/blog/my-first-post` → `slug = "my-first-post"`

### 6. Blog Post Nested Layout

You can add a layout specific to a section.

```
// [home]/(main)/blog/[slug]/layout.tw

page {
    title "Blog Post"
    render static
}

body {
    article { class "blog-post-wrapper"
        children
    }
}
```

## The `children` Keyword

The `children` keyword marks where page content gets injected in a layout.
It can appear:

### At the top level of body

```
body {
    children
}
```

### Inside an element

```
body {
    div { class "wrapper"
        children
    }
}
```

### Mixed with other content

```
body {
    nav { class "navbar"
        a "Home" { href "/" }
    }
    main { class "content"
        children
    }
    footer { class "footer"
        p "© 2026"
    }
}
```

## Route Groups `(folder)`

Folders wrapped in parentheses are **route groups** — they organize pages for
layout sharing without affecting the URL.

```
[home]/
├── (main)/              ← URL: / (not /main)
│   ├── layout.tw        ← Shared layout (navbar, footer)
│   ├── page.tw          ← URL: /
│   └── about/page.tw    ← URL: /about
├── (auth)/              ← URL: / (not /auth)
│   ├── layout.tw        ← Different layout (no navbar)
│   └── login/page.tw    ← URL: /login
```

Both `(main)/page.tw` and `(auth)/login/page.tw` have different layouts but
their URLs don't include the group name.

## Dynamic Routes `[slug]`

### Single parameter

```
[home]/blog/[slug]/page.tw  →  URL: /blog/:slug
[home]/app/[id]/page.tw     →  URL: /app/:id
```

### Catch-all

```
[home]/[...path]/page.tw  →  URL: /*path
```

Catch-all matches any number of segments:
- `/foo` → `path = "foo"`
- `/foo/bar/baz` → `path = "foo/bar/baz"`

## Layout Composition

When building a page, layouts compose from outermost to innermost:

**Example: Building `/blog/my-post`**

Given this structure:
```
[home]/
├── layout.tw                          ← Root layout
├── (main)/
│   ├── layout.tw                      ← Main layout
│   └── blog/
│       └── [slug]/
│           ├── layout.tw              ← Blog post layout
│           └── page.tw               ← Page content
```

Composition order:
1. Page body is rendered
2. Blog post layout wraps it (adds `<article>`)
3. Main layout wraps that (adds `<nav>` + `<footer>`)
4. Root layout wraps everything (adds `<html>`, `<head>`, `<body>`)

Result:
```html
<!DOCTYPE html>
<html>
<head>
    <meta charset="utf-8">
    <title>Blog Post</title>
</head>
<body>
    <nav class="navbar">...</nav>
    <main class="content">
        <article class="blog-post-wrapper">
            <h1>Blog Post Title</h1>
            <p>Page content here.</p>
        </article>
    </main>
    <footer class="footer">...</footer>
</body>
</html>
```

## Special Files

| File | Purpose |
|------|---------|
| `page.tw` | A page route — creates a URL |
| `layout.tw` | A layout wrapper — wraps child pages |
| `loading.tw` | Loading state — shown during navigation (discovered, runtime pending) |
| `not-found.tw` | 404 page — shown when route not found (discovered, runtime pending) |
| `error.tw` | Error boundary — shown on errors (discovered, runtime pending) |
| `route.tw` | API route — creates an API endpoint (discovered, execution pending) |

## Layouts Can Import

Layout files are full TW components. They can import stylesheets and components:

```
// [home]/(main)/layout.tw

load "@./style/global.tss"
load "@./components/Header.tw"
load "@./components/Footer.tw"

page {
    title "Main Layout"
    render static
}

body {
    Header { }
    main { class "content"
        children
    }
    Footer { }
}
```

## Stylesheet Scoping

Each layout can load its own stylesheets. Styles from all layouts in the
chain are merged and included in the final HTML:

```
// [home]/layout.tw
load "@./style/global.tss"     ← Global styles (reset, body, etc.)

// [home]/(main)/layout.tw
load "@./style/navbar.tss"     ← Navbar styles

// [home]/(main)/blog/[slug]/layout.tw
load "@./style/blog-post.tss"   ← Blog post styles
```

All three stylesheets appear in the final HTML output.

## Zero-JS Compatibility

App Router pages fully support the Zero-JS feature. If a page has no state,
events, router links, client components, or reactivity, the output HTML
contains zero framework JavaScript.

Static pages with `let`, `each`, `if`, and `{var}` interpolation still
qualify for Zero-JS.

## Backward Compatibility

The App Router is fully backward compatible with the legacy structure:

- If `[home]/page.tw` or `[home]/layout.tw` exists → App Router mode
- If `[home]/pages/` or `[home]/layouts/` exists → Legacy mode
- The framework auto-detects which system to use

You can migrate gradually — start by adding a `layout.tw` to your existing
project, then move pages one by one.

## Comparison: Legacy vs App Router

| Feature | Legacy (v0.6.x) | App Router (v0.7.0) |
|---------|------------------|---------------------|
| Layout format | Raw HTML template | TW component |
| Layout slot | `{slot}` placeholder | `children` keyword |
| Nested layouts | Manual chain | Automatic by directory |
| Route groups | Not supported | `(folder)` syntax |
| Dynamic routes | Data file based | `[slug]` folder syntax |
| Layout imports | Limited (`load` directive) | Full TW component support |
| Head management | `{head}` placeholder | `head { }` block in layout |
| Backward compatible | — | ✅ Yes |

## Client-Side Navigation (v0.7.1+)

TW Framework v0.7.1 adds SPA-style client-side navigation. When a page uses
the `link` router key, the framework ships a lightweight client-side router
that intercepts link clicks and fetches the next page via `fetch()` instead
of doing a full page reload.

### How It Works

1. **`link` keyword** in a TW element produces an `<a data-tw-link="/path">` anchor
2. The router runtime JS intercepts clicks on `[data-tw-link]` anchors
3. It fetches the target page via `fetch()`, parses the HTML with `DOMParser`,
   and swaps the `<body>` content
4. Browser URL is updated via `history.pushState()` (no full reload)
5. Browser back/forward buttons work via `popstate` listener

### Usage

```
// In any .tw element:
div {
    link "/about"
    "About Page"
}
```

This produces:
```html
<a href="/about" data-tw-link="/about">About Page</a>
```

### Programmatic Navigation

You can navigate programmatically from any client-side JavaScript:

```javascript
// Navigate to a new page
window.__twNavigate("/blog/my-post");

// Or use the goto router key
// In TW: button { goto "/blog" on:click "noop" }
```

### Page Cache

The router caches fetched page HTML. Subsequent visits to the same page
load instantly from cache without a network request.

### Loading Callbacks

The router exposes optional callbacks for loading states:

```javascript
// Called when navigation starts
window.__twOnLoading = function() {
    // Show loading indicator
};

// Called when navigation completes
window.__twOnLoaded = function() {
    // Hide loading indicator
};
```

### Fallback

If `fetch()` fails (network error, 404, etc.), the router automatically
falls back to a full page navigation (`window.location.href = path`).

### Zero-JS Compatibility

Pages without `link` or `goto` router keys remain Zero-JS — no router
runtime is shipped. Only pages that use client-side navigation get the
~2KB router runtime.

## generateStaticParams (v0.7.1+)

The `generateStaticParams` directive lets you pre-render dynamic routes
at build time from a JSON data file.

### Usage

```
// [home]/blog/[slug]/page.tw

page {
    title "Blog Post"
    render static
    generateStaticParams "./posts.json"
}

body {
    h1 "Blog Post: {slug}"
    p "This page was pre-rendered at build time."
}
```

### JSON Data File

The JSON file should be a list of objects, where each object provides
the params for one route:

```json
[
    {"slug": "my-first-post"},
    {"slug": "another-post"},
    {"slug": "third-post"}
]
```

Or an object with `"items"`:

```json
{
    "items": [
        {"slug": "my-first-post"},
        {"slug": "another-post"}
    ]
}
```

### Path Resolution

The path in `generateStaticParams` is resolved **relative to the page's
directory**. For example:

```
[home]/
├── blog/
│   └── [slug]/
│       ├── page.tw          ← generateStaticParams "./posts.json"
│       └── posts.json        ← Resolved relative to [slug]/ directory
```

Absolute paths are also supported:

```
page {
    generateStaticParams "/absolute/path/to/posts.json"
}
```

### Build Output

For each item in the JSON file, the framework generates a static HTML
page at build time:

```
dist/
├── blog/
│   ├── my-first-post/
│   │   └── index.html       ← Generated from {"slug": "my-first-post"}
│   ├── another-post/
│   │   └── index.html       ← Generated from {"slug": "another-post"}
│   └── third-post/
│       └── index.html       ← Generated from {"slug": "third-post"}
```

### Backward Compatibility

If `generateStaticParams` is not specified, the framework falls back to
the legacy `load_dynamic_items` behavior (loading a JSON file with the
same name as the `.tw` file, e.g. `[slug].json` → `[slug].tw`).

## route.tw — API Routes (v0.7.1+)

In App Router mode, `route.tw` files create API endpoints. They use the
same `.twm` module syntax as legacy `route.twm` files.

### Directory Structure

```
[home]/
├── page.tw                     ← Home page (/)
└── api/
    ├── apps/
    │   └── route.tw            ← GET /api/apps
    ├── users/
    │   └── route.tw            ← GET /api/users, POST /api/users
    └── apps/
        └── [id]/
            └── route.tw        ← GET /api/apps/:id
```

### Syntax

`route.tw` files use `.twm` module syntax:

```javascript
// [home]/api/apps/route.tw

export function get(request) {
    return {
        status: 200,
        json: { apps: ["app1", "app2"] }
    };
}

export function post(request) {
    const body = request.body;
    return {
        status: 201,
        json: { created: true, id: body.id }
    };
}
```

### Supported HTTP Methods

| Method | Export Function |
|--------|----------------|
| GET | `get(request)` |
| POST | `post(request)` |
| PUT | `put(request)` |
| PATCH | `patch(request)` |
| DELETE | `delete(request)` |
| OPTIONS | `options(request)` |

### Request Object

The `request` object passed to handler functions contains:

```javascript
{
    method: "GET",
    path: "/api/apps",
    query: { search: "test" },
    body: {},
    headers: { "Content-Type": "application/json" },
    cookies: { session: "abc123" },
    env: { API_KEY: "..." }
}
```

### Response Shapes

```javascript
// JSON response
return { status: 200, json: { key: "value" } };

// Text response
return { status: 200, text: "Hello world" };

// HTML response
return { status: 200, html: "<h1>Hello</h1>" };

// Redirect
return { status: 302, redirect: "/new-path" };

// Custom headers
return {
    status: 200,
    json: { ok: true },
    headers: { "X-Custom-Header": "value" }
};
```

### Dynamic API Routes

`route.tw` in dynamic route directories get URL params:

```
[home]/api/apps/[id]/route.tw  →  /api/apps/:id
```

```javascript
export function get(request) {
    const id = request.params.id;  // "123" for /api/apps/123
    return { status: 200, json: { id: id } };
}
```

### Legacy Compatibility

Legacy `route.twm` files in `[home]/api/` continue to work unchanged.
The framework discovers both `route.twm` (legacy) and `route.tw`
(App Router) files.
