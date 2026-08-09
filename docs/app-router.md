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

## Migration

See `MIGRATION_V0.7.0.md` for a step-by-step migration guide.
