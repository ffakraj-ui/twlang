# TW App Router — Complete Guide

This guide covers everything you need to know about the TW Framework App Router system.

---

## 1. Getting Started

The App Router is TW Framework's file-system based routing system. Your folder structure determines your URLs. Layouts are TW components, not HTML templates.

### Create a New Project

```bash
tw create my-site
cd my-site
tw dev
```

This generates:

```
[home]/
├── layout.tw           ← Root layout (wraps every page)
├── index.tw (or index.tw / page.tw)             ← Home page (URL: /)
├── about/index.tw / page.tw       ← URL: /about
├── counter/index.tw / page.tw     ← URL: /counter
├── contact/index.tw / page.tw     ← URL: /contact
├── not-found.tw        ← 404 page
├── api/
│   ├── contact/route.tw   ← POST /api/contact
│   └── users/route.tw      ← GET /api/users
└── style.tss           ← Global stylesheet
```

### Auto-Detection

The framework auto-detects which routing system to use:

- If `[home]/index.tw / page.tw` or `[home]/layout.tw` exists → **App Router mode**
- If `[home]/` exists → **Legacy mode**

Both modes work simultaneously. You can migrate gradually.

---

## 2. Layouts

Layouts are TW components that wrap pages with shared structure. They use the `children` keyword to inject page content.

### Root Layout

```
// [home]/layout.tw

page {
    title "My Site"
    render static
}

load "@./style.tss"

head {
    meta { charset "utf-8" }
    meta { name "viewport", content "width=device-width, initial-scale=1" }
}

body {
    nav { class "navbar"
        a "Home" { href "/", class "nav-link" }
        a "About" { href "/about", class "nav-link" }
    }
    main { class "content"
        children
    }
    footer { class "footer"
        p "Built with TW"
    }
}
```

### The `children` Keyword

The `children` keyword marks where page content goes. It can appear:

**At top level of body:**
```
body {
    children
}
```

**Inside an element:**
```
body {
    main { class "content"
        children
    }
}
```

**Mixed with other content:**
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

### Nested Layouts

Place `layout.tw` in subdirectories — they automatically wrap child pages:

```
[home]/
├── layout.tw              ← Root layout (wraps everything)
├── (main)/
│   ├── layout.tw          ← Main layout (navbar + footer)
│   └── blog/
│       ├── layout.tw      ← Blog layout (article wrapper)
│       └── [slug]/
│           └── index.tw / page.tw    ← Page content
```

Composition order (outermost to innermost):
1. Page body renders
2. Blog post layout wraps it
3. Main layout wraps that
4. Root layout wraps everything

### Layouts Can Import

Layout files are full TW components:

```
// [home]/(main)/layout.tw

load "@./style/navbar.tss"
load "@./components/Header.tw"

page {
    title "Main"
    render static
}

body {
    Header { }
    main { class "content"
        children
    }
}
```

---

## 3. Route Groups `(folder)`

Folders wrapped in parentheses are **route groups** — they organize pages for layout sharing without affecting the URL.

```
[home]/
├── (main)/              ← URL: / (not /main)
│   ├── layout.tw        ← Shared layout (navbar, footer)
│   ├── index.tw / page.tw          ← URL: /
│   └── about/index.tw / page.tw    ← URL: /about
├── (auth)/              ← Different layout (no navbar)
│   ├── layout.tw
│   └── login/index.tw / page.tw    ← URL: /login
```

Both `(main)/index.tw / page.tw` and `(auth)/login/index.tw / page.tw` have different layouts but their URLs don't include the group name.

### When to Use Route Groups

- Share a layout across multiple routes without adding URL segments
- Group related pages (marketing, dashboard, auth) with different chrome
- Keep the URL clean while organizing code

---

## 4. Dynamic Routes `[slug]`

Folder names in square brackets become dynamic URL segments.

### Single Parameter

```
[home]/blog/[slug]/index.tw / page.tw  →  URL: /blog/:slug
[home]/app/[id]/index.tw / page.tw     →  URL: /app/:id
```

### Catch-All Routes

```
[home]/[...path]/index.tw / page.tw  →  URL: /*path
```

Matches any number of segments:
- `/foo` → `path = "foo"`
- `/foo/bar/baz` → `path = "foo/bar/baz"`

### generateStaticParams

Pre-render dynamic routes at build time from a JSON data file:

```
// [home]/blog/[slug]/index.tw / page.tw

page {
    title "Blog Post"
    render static
    generateStaticParams "./posts.json"
}

body {
    h1 "Post: {slug}"
}
```

JSON file format (list of objects):

```json
[
    {"slug": "my-first-post"},
    {"slug": "another-post"},
    {"slug": "third-post"}
]
```

Or with `"items"` key:

```json
{
    "items": [
        {"slug": "my-first-post"},
        {"slug": "another-post"}
    ]
}
```

**Path resolution:** relative to the page's directory. Absolute paths also supported.

**Build output:**

```
dist/
├── blog/
│   ├── my-first-post/index.html
│   ├── another-post/index.html
│   └── third-post/index.html
```

**Backward compatibility:** If `generateStaticParams` is not specified, falls back to legacy behavior (JSON file with same name as `.tw` file).

---

## 5. Client-Side Navigation

The `link` keyword enables SPA-style navigation — no full page reload.

### Usage

```
div {
    link "/about"
    "About Page"
}
```

Produces:

```html
<a href="/about" data-tw-link="/about">About Page</a>
```

### How It Works

1. Click on `[data-tw-link]` anchor is intercepted
2. Target page is fetched via `fetch()`
3. HTML is parsed with `DOMParser`
4. `<body>` content is swapped
5. URL updated via `history.pushState()`
6. Browser back/forward work via `popstate` listener

### Features

- **Page cache** — subsequent visits load from cache, no network request
- **Back/forward** — `popstate` handler restores previous pages
- **Loading callbacks** — `window.__twOnLoading()` and `window.__twOnLoaded()`
- **Fallback** — on fetch error, automatically falls back to full page navigation
- **Programmatic** — `window.__twNavigate("/path")` for manual navigation

### Zero-JS Compatibility

Pages without `link` or `goto` router keys remain Zero-JS. Only pages that use client-side navigation get the ~2KB router runtime.

---

## 6. route.tw — API Routes

In App Router mode, `route.tw` files create API endpoints. They use `.twm` module syntax.

### Directory Structure

```
[home]/
├── api/
│   ├── apps/route.tw           ← /api/apps
│   ├── users/route.tw          ← /api/users
│   └── apps/[id]/route.tw      ← /api/apps/:id
```

### Syntax

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
// JSON
return { status: 200, json: { key: "value" } };

// Text
return { status: 200, text: "Hello world" };

// Redirect
return { status: 302, redirect: "/new-path" };

// Custom headers
return { status: 200, json: { ok: true }, headers: { "X-Custom": "value" } };
```

### Dynamic API Routes

```
[home]/api/apps/[id]/route.tw  →  /api/apps/:id
```

### Legacy Compatibility

Legacy `route.twm` files in `[home]/api/` continue to work unchanged. The framework discovers both.

---

## 7. Built-in Icons

60+ SVG icons with zero external dependency. No icon font, no external CSS, no JavaScript.

### Usage

```tw
import "Icon"

body {
    nav { class "navbar"
        Icon { name "home", class "icon" }
        a "Home" { href "/" }
    }
    footer {
        Icon { name "github", size 20 }
        Icon { name "twitter", size 20 }
    }
}
```

### Props

| Prop | Default | Description |
|------|---------|-------------|
| `name` | (required) | Icon name (e.g. "home", "search") |
| `size` | 24 | SVG width/height in pixels |
| `class` | "" | CSS class name |

### Available Icons

home, search, menu, close, arrow-right, arrow-left, arrow-up, arrow-down, check, check-circle, chevron-down, chevron-up, chevron-right, chevron-left, user, users, settings, heart, star, github, twitter, mail, phone, calendar, clock, download, upload, plus, minus, edit, trash, eye, lock, unlock, sun, moon, external-link, copy, code, book, zap, globe, image, link, filter, bell, tag, folder, file, play, pause, refresh, wifi, camera, map-pin, shopping-cart, and more.

### Zero-JS Compatible

Icons render as inline SVG at build time. No client-side JavaScript is needed. Static pages with icons remain Zero-JS.

---

## 8. Special Files

| File | Purpose |
|------|---------|
| `index.tw / page.tw` | A page route — creates a URL |
| `layout.tw` | A layout wrapper — wraps child pages |
| `not-found.tw` | 404 page — shown when route not found |
| `route.tw` | API route — creates an API endpoint |
| `loading.tw` | Loading state (discovered; developer handles runtime) |
| `error.tw` | Error boundary (discovered; developer handles runtime) |

### not-found.tw

```
// [home]/not-found.tw

page {
    title "Page Not Found"
    render static
}

body {
    div { class "not-found"
        h1 "404"
        p "Page not found."
        a "Go home" { href "/", class "button" }
    }
}
```

---

## 9. Comparison: Legacy vs App Router

| Feature | Legacy (v0.9.x) | App Router (v0.9.30+) |
|---------|------------------|---------------------|
| Layout format | Raw HTML template | TW component |
| Layout slot | `{slot}` placeholder | `children` keyword |
| Nested layouts | Manual chain (`layout "base > docs"`) | Automatic by directory |
| Route groups | Not supported | `(folder)` syntax |
| Dynamic routes | `[slug].tw` file | `[slug]/index.tw / page.tw` folder |
| API routes | `route.twm` | `route.tw` (or `route.twm`) |
| Client-side nav | `link` (redirect) | `link` (SPA navigation) |
| Pre-rendering | JSON file same name | `generateStaticParams` directive |
| Icons | Not available | Built-in 60+ SVG icons |
| Backward compatible | — | Yes |

---

## 10. Migration from Legacy

### Step 1: Add a root layout

Create `[home]/layout.tw` (App Router layout) alongside your existing `[home]/layouts/main.tw` (legacy layout).

### Step 2: Add index.tw / page.tw files

For each page in `[home]/`, create a corresponding `[home]/index.tw / page.tw` or `[home]/about/index.tw / page.tw`.

### Step 3: Use `children` instead of `{slot}`

Replace `{slot}` in your layouts with the `children` keyword.

### Step 4: Move API routes

Rename `route.twm` to `route.tw` (optional — both work).

### Step 5: Remove legacy dirs

Once all pages are migrated, delete `[home]/` and `[home]/layouts/`.

See `MIGRATION_V0.7.0.md` for detailed steps.
