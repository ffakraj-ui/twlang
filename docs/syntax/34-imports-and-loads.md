# Imports and Loads

## Import (Components)

Import components from `[home]/components/`:

```tw
import "Hero"
import "Button"
import "Footer"

body {
    Hero { title "Welcome" }
    Button { text "Click" }
    Footer {}
}
```

### Import Resolution

TW searches in this order:
1. `[home]/components/{name}.tw`
2. `[home]/components/{name}/index.tw`
3. Subfolders within `components/`

### Import from Subfolder

```tw
import "nav/Breadcrumb"

body {
    Breadcrumb { trail ["Home", "Products", "Details"] }
}
```

Resolves to `[home]/components/nav/Breadcrumb.tw`.

## Load (Stylesheets, JSON, Modules)

Use `load` for non-component files:

### Stylesheets

```tw
load "@./style/site.tss"
load "@./style/homepage.tss"
```

### JSON Data

```tw
load "@./data/products.json"
```

JSON data is available as a variable in the page context.

### TWM Modules

```tw
load "@./api/handler.twm"
```

### Path Resolution

- `@./` — relative to `[home]/` directory
- `@/../` — relative to parent of `[home]/` (e.g., project root)

## Load in Page Block vs Top-Level

### Top-level load (applies to entire page)

```tw
page { title "Home", render static }

load "@./style/site.tss"

body {
    div { class "hero" }
}
```

### Inside body (scoped)

```tw
body {
    load "@./style/homepage.tss"
    div { class "hero" }
}
```

## Multiple Loads

```tw
load "@./style/base.tss"
load "@./style/typography.tss"
load "@./style/homepage.tss"
```

Styles are concatenated in order. Later files override earlier ones.

## Error: Load Path Not Found

```
Error: load: file not found for `@./style/missing.tss`
```

**Fix:**
- Verify path relative to `[home]/`
- Check file extension
- Use `@./` prefix for paths within `[home]/`

## Error: Component Not Found

```
Error: Component `Hero` not found
```

**Fix:**
- Create `[home]/components/Hero.tw`
- Check spelling
- Check import name matches filename
