# TSS (TW Style Sheets) Syntax Deep Dive

Complete reference for `.tss` file syntax, selectors, properties, and common mistakes.

## Basic Syntax Rules

### Property: Value Format

```css
/* CORRECT */
.selector {
    property: value
    another-property: another-value
}
```

```css
/* WRONG — Missing colon or semicolon (TSS uses neither) */
.selector {
    property value;  /* No semicolon in TSS */
    property = value /* No equals sign */
}
```

### No Semicolons

TSS does NOT use semicolons. Each property is on its own line.

```css
/* CORRECT */
.card {
    display: flex
    padding: 24px
    background: white
}
```

```css
/* WRONG — CSS syntax, not TSS */
.card {
    display: flex;
    padding: 24px;
    background: white;
}
```

## Selectors

### Element Selectors

```css
h1 {
    font-size: 2rem
    color: #333
}

p {
    line-height: 1.6
    margin-bottom: 16px
}
```

### Class Selectors

```css
.card {
    background: white
    border: 1px solid #e5e7eb
}

.btn-primary {
    background: #22c55e
    color: white
}
```

### ID Selectors

```css
#header {
    position: fixed
    top: 0
}
```

### Common Mistake: Wrong Selector Format

```css
/* WRONG — Dot before element name */
div.card {
    padding: 20px
}
```

**Fix:** Use `.class` for classes, `element` for elements.

```css
/* CORRECT */
.card {
    padding: 20px
}

/* Or if you need element + class */
div {
    padding: 20px
}
```

## Pseudo-Classes

```css
.btn:hover {
    background: #16a34a
}

.input:focus {
    border-color: #22c55e
    outline: none
}

.link:active {
    color: #15803d
}

.item:first-child {
    margin-top: 0
}

.item:last-child {
    margin-bottom: 0
}

.item:nth-child(odd) {
    background: #f9fafb
}
```

## Pseudo-Elements

```css
.quote::before {
    content: '"'
    font-size: 2rem
    color: #ccc
}

.quote::after {
    content: '"'
    font-size: 2rem
    color: #ccc
}
```

## Combinators

```css
/* Descendant */
.card p {
    color: #666
}

/* Child */
.nav > li {
    display: inline-block
}

/* Adjacent sibling */
h2 + p {
    margin-top: 8px
}

/* General sibling */
h2 ~ p {
    color: #666
}
```

## Media Queries

```css
/* Mobile-first approach */
.container {
    padding: 16px
}

@media (min-width: 768px) {
    .container {
        padding: 24px
    }
}

@media (min-width: 1024px) {
    .container {
        padding: 32px
        max-width: 1200px
        margin: 0 auto
    }
}
```

### Common Mistake: Wrong Media Query Syntax

```css
/* WRONG */
@media screen and (min-width: 768px) {
    .container {
        padding: 24px
    }
}
```

**Fix:** TSS uses simplified media query syntax.

```css
/* CORRECT */
@media (min-width: 768px) {
    .container {
        padding: 24px
    }
}
```

## CSS Variables (Custom Properties)

```css
:root {
    --primary: #22c55e
    --primary-dark: #16a34a
    --text: #1f2937
    --bg: #ffffff
    --border: #e5e7eb
    --radius: 8px
    --shadow: 0 4px 6px rgba(0,0,0,0.1)
}

.btn {
    background: var(--primary)
    color: white
    padding: 12px 24px
    radius: var(--radius)
}
```

### Common Mistake: Wrong Variable Syntax

```css
/* WRONG */
.btn {
    background: $primary
}
```

**Fix:** Use CSS custom property syntax with `--` prefix.

```css
/* CORRECT */
.btn {
    background: var(--primary)
}
```

## Shorthand Properties

TSS supports these shorthand properties:

```css
.box {
    /* Margin shorthand */
    margin: 16px                    /* all sides */
    margin: 16px 24px               /* vertical horizontal */
    margin: 8px 16px 24px           /* top horizontal bottom */
    margin: 8px 16px 24px 32px      /* top right bottom left */

    /* Padding shorthand */
    padding: 16px

    /* Border shorthand */
    border: 1px solid #e5e7eb

    /* Radius shorthand */
    radius: 8px                     /* all corners */
    radius: 8px 16px                /* top-left/bottom-right top-right/bottom-left */
}
```

## Flexbox

```css
.container {
    display: flex
    flex-direction: row
    justify-content: center
    align-items: center
    gap: 16px
    flex-wrap: wrap
}

.item {
    flex: 1
    flex-shrink: 0
    flex-basis: 300px
}
```

### Common Mistake: Invalid Flex Values

```css
/* WRONG */
.item {
    flex: auto
}
```

**Fix:** Use valid flex values.

```css
/* CORRECT */
.item {
    flex: 1
    /* or */
    flex: 0 0 300px
}
```

## Grid

```css
.grid {
    display: grid
    grid-template-columns: repeat(3, 1fr)
    grid-template-rows: auto
    gap: 24px
}

.grid-item {
    grid-column: span 2
    grid-row: 1
}
```

## Animation

```css
@keyframes fadeIn {
    from {
        opacity: 0
    }
    to {
        opacity: 1
    }
}

.fade-in {
    animation: fadeIn 0.3s ease-in-out
}
```

### Common Mistake: Wrong Animation Syntax

```css
/* WRONG */
.fade-in {
    animation: fadeIn 0.3s
}
```

**Fix:** Include timing function.

```css
/* CORRECT */
.fade-in {
    animation: fadeIn 0.3s ease-in-out
}
```

## TSS Property Reference

| TSS Property | CSS Equivalent | Notes |
|-------------|----------------|-------|
| `display` | `display` | flex, grid, block, inline, none |
| `position` | `position` | static, relative, absolute, fixed, sticky |
| `width` | `width` | px, %, rem, vw |
| `height` | `height` | px, %, rem, vh |
| `padding` | `padding` | Supports shorthand |
| `margin` | `margin` | Supports shorthand |
| `background` | `background` | color, image, gradient |
| `color` | `color` | Text color |
| `font-size` | `font-size` | px, rem, em |
| `font-weight` | `font-weight` | 400, 500, 700 |
| `line-height` | `line-height` | Unitless or px |
| `text-align` | `text-align` | left, center, right, justify |
| `text-decoration` | `text-decoration` | none, underline |
| `border` | `border` | width style color |
| `radius` | `border-radius` | TSS shorthand |
| `shadow` | `box-shadow` | x y blur color |
| `opacity` | `opacity` | 0 to 1 |
| `z-index` | `z-index` | Integer |
| `overflow` | `overflow` | hidden, scroll, auto |
| `cursor` | `cursor` | pointer, default |
| `transition` | `transition` | property duration timing |
| `transform` | `transform` | translate, rotate, scale |
| `gap` | `gap` | Flex/grid gap |
| `object-fit` | `object-fit` | cover, contain |

## TSS Error Codes

| Code | Error | Fix |
|------|-------|-----|
| TW4001 | Unknown property | Check property name |
| TW4002 | Invalid value for property | Check value syntax |
| TW4003 | Missing closing brace | Add `}` |
| TW4004 | Invalid selector | Check selector syntax |
| TW4005 | Nested media query error | Check media query syntax |

## Best Practices

1. **Mobile-first**: Write base styles for mobile, use `@media` for larger screens.
2. **Use variables**: Define colors, spacing, radius in `:root`.
3. **BEM naming**: `.block__element--modifier` for clarity.
4. **Avoid `!important`**: Use specificity instead.
5. **Group related properties**: Layout, then box model, then typography, then visual.
6. **Comment sections**: Use `/* Section Name */` for organization.
