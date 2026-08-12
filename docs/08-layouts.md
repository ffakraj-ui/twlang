# Layouts

Layouts wrap pages with shared structure (header, footer, navigation).

## Creating a Layout

`[home]/layouts/main.tw`:

```tw
html {
    head {
        meta { name "viewport" content "width=device-width, initial-scale=1" }
        load "@./style/global.tss"
    }
    body {
        header {
            nav {
                a "Home" { href "/" }
                a "About" { href "/about" }
            }
        }
        {children}
        footer {
            p "© 2024 My Site"
        }
    }
}
```

The `{children}` placeholder is where page content renders.

## Using a Layout

In a page file:

```tw
page {
    title "About"
    layout "main"
    render static
}

body {
    h1 "About Us"
    p "We are awesome."
}
```

## Layout Chains

Chain multiple layouts with `>` or `,`:

```tw
page {
    layout "base > docs"
}
```

This renders: `base` wraps `docs` wraps page content.

Or comma-separated:

```tw
page {
    layout "base,docs"
}
```

## Multiple Layout Keys

You can also specify multiple layouts with repeated keys:

```tw
page {
    layout "base"
    layout "docs"
}
```

## Layout Resolution

Layouts are searched in `[home]/layouts/`:

1. `[home]/layouts/{name}.tw`
2. `[home]/layouts/{name}/index.tw`

## Default Layout

If no layout is specified, TW looks for `[home]/layouts/default.tw`. If not found, the page renders without a wrapper.

## Error: Layout Not Found

```
CompilerError: Layout `main` not found
```

Check:
- File exists at `[home]/layouts/main.tw`
- Layout name matches filename
- No file extension in layout name (use `main` not `main.tw`)

---

## App Router Layouts (v0.7.0+)

The App Router introduces **TW-component layouts** — layouts are `.tw` files
written in TW syntax (not raw HTML templates) and use the `children` keyword
instead of `{children}`.

### Creating an App Router Layout

```
// [home]/layout.tw (root layout)

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

### Nested Layouts

Place `layout.tw` files in subdirectories — they automatically wrap all
child pages:

```
[home]/
├── layout.tw              ← Root layout (wraps everything)
├── (main)/
│   ├── layout.tw          ← Main layout (navbar + footer)
│   └── blog/
│       ├── layout.tw      ← Blog layout (article wrapper)
│       └── [slug]/
│           └── page.tw    ← Page content
```

### The `children` Keyword

The `children` keyword marks where page content gets injected:

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

### Legacy vs App Router Layouts

| Feature | Legacy (`[home]/layouts/`) | App Router (`layout.tw`) |
|---------|---------------------------|--------------------------|
| Format | Raw HTML template | TW component |
| Slot syntax | `{children}` placeholder | `children` keyword |
| Nesting | Manual (`layout "base > docs"`) | Automatic by directory |
| Imports | Limited | Full TW component support |
| Route groups | Not supported | `(folder)` syntax |

See `docs/app-router.md` for the full guide.
