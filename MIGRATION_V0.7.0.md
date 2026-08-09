# Migration Guide: v0.6.x → v0.7.0 (App Router)

## Overview

TW Framework v0.7.0 introduces the **App Router** — a Next.js-style file-system
based routing and layout system. Layouts are now **TW components**, not raw HTML
templates. They support nesting, route groups, dynamic routes, and a `children`
slot for page content injection.

**This is a major release but is fully backward compatible.** Existing projects
using `[home]/` + `[home]/layouts/` will continue to work unchanged.

---

## What Changed

### 1. Layouts: HTML Templates → TW Components

**Before (v0.6.x):**
```
[home]/layouts/main.tw    ← Raw HTML with {slot}, {title} placeholders
```

```html
<!DOCTYPE html>
<html>
<head>{head}<title>{title}</title>{styles}</head>
<body>{slot}{scripts}</body>
</html>
```

**After (v0.7.0):**
```
[home]/layout.tw          ← Root layout (TW component)
[home]/(main)/layout.tw    ← Nested layout (TW component)
```

```
page {
    title "My Site"
    render static
}

head {
    meta { charset "utf-8" }
    meta { name "viewport", content "width=device-width, initial-scale=1" }
}

body {
    div { class "wrapper"
        children
    }
}
```

### 2. `{slot}` → `children` keyword

The old `{slot}` placeholder in HTML-template layouts is replaced by the
`children` keyword in TW-component layouts. The `children` keyword can appear:

- At the top level of `body { }` — content goes in the body flow
- Inside an element block — content goes inside that element

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

### 3. Flat Pages → Nested File System Routes

**Before (v0.6.x):**
```
[home]/
├── pages/
│   ├── index.tw        ← /
│   ├── about.tw        ← /about
│   ├── blog.tw         ← /blog
│   └── blog-post.tw    ← /blog-post (dynamic via data file)
├── layouts/
│   └── main.tw         ← HTML template
└── style/
    └── global.tss
```

**After (v0.7.0):**
```
[home]/
├── layout.tw           ← Root layout (wraps everything)
├── page.tw             ← Home page (/)
├── (main)/             ← Route group (excluded from URL)
│   ├── layout.tw       ← Main layout (Header/Footer)
│   ├── blog/
│   │   ├── page.tw     ← /blog
│   │   └── [slug]/     ← Dynamic route
│   │       ├── layout.tw  ← Blog post layout
│   │       └── page.tw    ← /blog/:slug
│   └── about/
│       └── page.tw     ← /about
├── admin/              ← Separate layout tree
│   ├── layout.tw       ← Admin layout
│   └── page.tw         ← /admin
└── style/
    └── global.tss
```

### 4. New Directory Conventions

| Pattern | Meaning | URL Impact |
|---------|---------|------------|
| `page.tw` | A page route | Creates a URL route |
| `layout.tw` | A layout wrapper | No URL, wraps child pages |
| `loading.tw` | Loading state | No URL, shown during navigation |
| `not-found.tw` | 404 page | No URL, shown on 404 |
| `error.tw` | Error boundary | No URL, shown on errors |
| `route.tw` | API route | Creates an API endpoint |
| `(folder)` | Route group | Excluded from URL |
| `[slug]` | Dynamic segment | `:slug` in URL |
| `[...slug]` | Catch-all | `*slug` in URL |

### 5. Nested Layout Composition

Layouts compose automatically based on directory nesting:

```
[home]/layout.tw              ← Outermost (root)
[home]/(main)/layout.tw       ← Middle (wraps (main) pages)
[home]/(main)/blog/[slug]/layout.tw  ← Innermost (wraps blog posts)
```

When building `/blog/my-post`:
1. Page body is rendered
2. Blog post layout wraps it (adds `<article>`)
3. (main) layout wraps that (adds `<nav>` + `<footer>`)
4. Root layout wraps everything (adds `<html>`, `<head>`, `<body>`)

### 6. Route Groups

Folders wrapped in parentheses like `(main)`, `(auth)`, `(marketing)` are
**route groups** — they group pages for layout sharing without affecting the URL.

```
[home]/
├── (main)/              ← URL: / (not /main)
│   ├── layout.tw        ← Shared layout for main pages
│   ├── page.tw          ← URL: /
│   └── about/page.tw    ← URL: /about
├── (auth)/              ← URL: / (not /auth)
│   ├── layout.tw        ← Different layout for auth pages
│   └── login/page.tw    ← URL: /login
```

### 7. Dynamic Routes

Folder names in square brackets become dynamic URL segments:

```
[home]/blog/[slug]/page.tw  →  /blog/:slug
[home]/app/[id]/page.tw     →  /app/:id
[home]/[...path]/page.tw    →  /*path (catch-all)
```

Dynamic params are accessible in the page context during data loading.

---

## How to Migrate

### Step 1: Check if you need to migrate

If your project uses `[home]/` and `[home]/layouts/`, it will continue
to work as-is. You only need to migrate if you want the new features.

### Step 2: Create the App Router structure

1. Create `[home]/layout.tw` (root layout)
2. Create `[home]/page.tw` (home page)
3. Move pages from `[home]/` to nested directories
4. Convert layouts from HTML templates to TW components

### Step 3: Convert layout files

**Old `main.tw` (HTML template):**
```html
<!DOCTYPE html>
<html>
<head>{head}<title>{title}</title>{styles}</head>
<body>{slot}{scripts}</body>
</html>
```

**New `layout.tw` (TW component):**
```
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

### Step 4: Replace `{slot}` with `children`

In all layout files, replace `{slot}` with the `children` keyword.

### Step 5: Delete old structure

Once migrated, remove `[home]/` and `[home]/layouts/` directories.

---

## Backward Compatibility

- Legacy `[home]/` + `[home]/layouts/` projects work unchanged
- Old `{slot}`, `{title}`, `{head}`, `{styles}`, `{scripts}` placeholders still work
- The framework auto-detects which system to use via `has_app_router_structure()`
- No configuration changes needed

---

## What's NOT Included Yet (Future)

- `loading.tw` and `not-found.tw` are discovered but not fully integrated
  into the runtime (will be in v0.7.1)
- `route.tw` API routes are discovered but not executed (will be in v0.7.2)
- Client-side navigation between App Router pages (will be in v0.8.0)
- `generateStaticParams` for dynamic route pre-rendering (will be in v0.7.1)
