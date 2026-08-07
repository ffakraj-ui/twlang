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
