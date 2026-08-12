# Layout Inheritance and Chains

## Basic Layout Chain

Chain layouts with `>` or `,`:

```tw
page {
    layout "base > docs"
}
```

This means:
1. `base.tw` wraps the page
2. `docs.tw` wraps the content inside `base.tw`
3. The actual page content is inside `docs.tw`

## Layout Order

```
base.tw
  -> docs.tw
       -> page content
```

## Example: Base Layout

`[home]/layouts/base.tw`:

```tw
html {
    head {
        meta { name "viewport" content "width=device-width, initial-scale=1" }
        load "@./style/global.tss"
    }
    body {
        header { nav { a "Home" { href "/" } } }
        {children}
        footer { p "Copyright 2024" }
    }
}
```

## Example: Docs Layout

`[home]/layouts/docs.tw`:

```tw
div {
    class "docs-layout"
    aside {
        class "sidebar"
        a "Getting Started" { href "/docs/getting-started" }
    }
    main {
        class "docs-content"
        {children}
    }
}
```

## Page Using Chain

```tw
page {
    title "Syntax Docs"
    layout "base > docs"
    render static
}

body {
    h1 "TW Syntax"
    p "Learn the .tw file format..."
}
```

## Comma Syntax

Equivalent to `>`:

```tw
page { layout "base,docs" }
```

## Multiple Layout Keys

```tw
page {
    layout "base"
    layout "docs"
}
```

All three syntaxes produce the same result.
