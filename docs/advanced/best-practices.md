# Best Practices

This guide covers recommended patterns and conventions for building production-grade websites with TW Framework.

## File Organization

Keep your project structure predictable:

```
[home]/
  pages/          # Route files only
  components/     # Reusable UI pieces
  layouts/        # Page wrappers
  style/          # Component-scoped styles
  assets/         # Static files
  api/            # Server modules (.twm)
```

Avoid putting business logic in `.tw` files. Use `.twm` modules and `load` them.

## Naming Conventions

| Entity | Convention | Example |
|--------|-----------|---------|
| Pages | kebab-case | `about-us.tw`, `blog/[slug].tw` |
| Components | PascalCase | `Hero.tw`, `NavBar.tw` |
| Layouts | kebab-case | `main.tw`, `docs-sidebar.tw` |
| Styles | kebab-case matching component | `hero.tss`, `nav-bar.tss` |
| API routes | kebab-case | `contact/route.twm` |

## Page Block Rules

Always declare these three first:

```tw
page {
    title "Descriptive Title | Site Name"
    layout "main"
    render static
}
```

- `title`: Include site name for SEO. Keep under 60 characters.
- `layout`: Always specify, even if you have only one.
- `render`: Be explicit. Defaulting to `static` is safest.

## Component Design

### Props with Defaults

```tw
let title "Default Title"
let subtitle ""

section {
    class "hero-section"
    h1 "{title}"
    if subtitle {
        p "{subtitle}"
    }
}
```

### Slot Usage

Components that wrap content should use `slot`:

```tw
// Card.tw
article {
    class "card"
    slot {}
}
```

```tw
// Usage
Card {
    h2 "Card Title"
    p "Card content here."
}
```

## Style Guidelines

### Prefer Component Styles

Instead of one giant `style.tss`, split styles:

```
style/
  global.tss      # CSS variables, reset, utilities
  header.tss
  footer.tss
  hero.tss
```

Load them in components:

```tw
load "@./style/hero.tss"
```

### CSS Variable Tokens

Define a token system in `global.tss`:

```css
:root {
    --color-primary: #22c55e
    --color-text: #1f2937
    --space-sm: 8px
    --space-md: 16px
    --space-lg: 32px
    --radius: 8px
}
```

Reference them everywhere:

```css
.btn-primary {
    background: var(--color-primary)
    padding: var(--space-md)
    radius: var(--radius)
}
```

## Performance

1. **Use `render static`** for 90% of pages. Only use `server` or `edge` when you need dynamic data per request.
2. **Lazy load below-fold images**: TW auto-adds `loading="lazy"` to `img` tags, but verify your markup.
3. **Minimize reactive state**: Only use `on:click` / `bind:` when necessary. Each reactive page ships ~2KB JS.
4. **Split large `.tw` files**: If a page exceeds 500 lines, extract sections into components.

## SEO Checklist

Every public page should have:

```tw
head {
    seo {
        description "Unique description under 160 chars."
        og_title "Social Title"
        og_image "/assets/og-image.png"
        twitter_card "summary_large_image"
    }
}
```

## Security

- Never expose secrets in `.tw` files. Use `env:` in `tw.config` with `public:` allow-list.
- Validate all API inputs in `.twm` routes.
- Use `middleware.tw` for rate limiting on public endpoints.
- Set `Content-Security-Policy` headers via middleware.

## Accessibility (a11y)

- Use semantic HTML: `nav`, `main`, `article`, `section`, `footer`.
- Every `img` needs an `alt` attribute.
- Form inputs need associated `label` elements.
- Ensure color contrast ratios meet WCAG AA (4.5:1 for normal text).
- Test keyboard navigation on interactive components.

## Error Handling

Always provide fallback content:

```tw
if products {
    each products as product {
        ProductCard { props product }
    }
} else {
    p "No products found." {
        class "empty-state"
    }
}
```

## Version Control

- Commit `tw.config` and `[home]/` structure.
- Do not commit `dist/`, `.tw_cache/`, or `.tw_manifest/`.
- Add a `README.md` at project root explaining how to run `tw dev`.

---

Following these practices ensures your TW projects are maintainable, fast, and suitable for deployment.
