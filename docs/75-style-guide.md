# TW Style Guide

## Naming Conventions

### Files

- Pages: lowercase, kebab-case: about.tw, blog-post.tw
- Components: PascalCase: Hero.tw, ProductCard.tw
- Layouts: lowercase: main.tw, default.tw
- Styles: lowercase: site.tss, blog.tss
- API routes: route.twm (standard) or descriptive: hello.twm

### Variables

```tw
// Good - descriptive
let userCount = 0
let isActive = true
let productList = []

// Bad - ambiguous
let n = 0
let a = true
let p = []
```

### CSS Classes

```css
// BEM-like naming
.card { }
.card__title { }
.card__body { }
.card--featured { }

// Or utility-based
.btn { }
.btn-primary { }
.btn-large { }
```

## Indentation

Use 4 spaces consistently.

## Element Order

Place attributes first, then children:

```tw
div {
    class "card"
    id "main-card"
    data-id "123"

    h1 "Title"
    p "Description"
}
```

## Page Structure

```tw
page {
    title "..."
    layout "..."
    render static
}

load "@./style/site.tss"

head {
    seo { description "..." }
}

body {
    // Content here
}
```

## CSS Structure

```css
/* 1. Variables */
:root {
    --primary #22c55e
    --radius 8px
}

/* 2. Base styles */
body {
    bg var(--bg)
    color var(--text)
    font 16px
}

/* 3. Layout */
.container {
    max-width 1200px
    margin 0 auto
}

/* 4. Components */
.card { }
.btn { }

/* 5. Utilities */
.text-center { text-align center }
.mt-4 { margin-top 16px }

/* 6. Responsive */
@media (max-width: 768px) {
    .container { padding 0 16px }
}
```
