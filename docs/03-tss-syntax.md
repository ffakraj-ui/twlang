# TSS Stylesheet Syntax

TSS (TW Style Sheets) is CSS without semicolons, with extra aliases.

## Basic Syntax

```css
.selector {
    property value
    property value
}
```

No semicolons needed. Each property on its own line.

## Selectors

```css
.classname { }
#id { }
element { }
.parent .child { }
.parent > .child { }
&:hover { }
@media (max-width: 768px) { }
```

## CSS Aliases

| Alias | Maps to |
|---|---|
| `bg` | `background` |
| `radius` | `border-radius` |
| `shadow` | `box-shadow` |
| `font` | `font-size` |

Example:
```css
.card {
    bg #fff
    radius 12px
    shadow 0 2px 8px rgba(0,0,0,0.1)
    font 16px
}
```

Compiles to:
```css
.card {
    background: #fff;
    border-radius: 12px;
    box-shadow: 0 2px 8px rgba(0,0,0,0.1);
    font-size: 16px;
}
```

## Full CSS Property List

`display`, `position`, `top`, `right`, `bottom`, `left`, `float`, `clear`, `overflow`, `overflow-x`, `overflow-y`, `z-index`, `visibility`, `width`, `height`, `min-width`, `max-width`, `min-height`, `max-height`, `margin`, `margin-top`, `margin-right`, `margin-bottom`, `margin-left`, `padding`, `padding-top`, `padding-right`, `padding-bottom`, `padding-left`, `border`, `border-top`, `border-right`, `border-bottom`, `border-left`, `border-width`, `border-style`, `border-color`, `border-radius`, `box-sizing`, `box-shadow`, `outline`, `background`, `background-color`, `background-image`, `background-size`, `background-position`, `background-repeat`, `background-attachment`, `color`, `font`, `font-size`, `font-family`, `font-weight`, `font-style`, `font-variant`, `line-height`, `letter-spacing`, `word-spacing`, `text-align`, `text-decoration`, `text-transform`, `text-shadow`, `white-space`, `word-break`, `word-wrap`, `flex`, `flex-direction`, `flex-wrap`, `flex-flow`, `justify-content`, `align-items`, `align-self`, `align-content`, `flex-grow`, `flex-shrink`, `flex-basis`, `order`, `gap`, `grid`, `grid-template`, `grid-template-columns`, `grid-template-rows`, `grid-column`, `grid-row`, `grid-gap`, `column-gap`, `row-gap`, `transition`, `animation`, `transform`, `opacity`, `cursor`, `list-style`, `pointer-events`, `user-select`, `content`, `radius`, `shadow`, `bg`

## Animations

```css
@keyframes fadeIn {
    0% { opacity 0 }
    100% { opacity 1 }
}

.element {
    animation fadeIn 0.3s ease-in
}
```

## Variables (CSS custom properties)

```css
:root {
    --primary #22c55e
    --bg #fff
}

.button {
    bg var(--primary)
    color var(--bg)
}
```

## Multi-line Values (v0.4.3+)

```css
.hero {
    background-image:
        linear-gradient(rgba(0,0,0,0.5), rgba(0,0,0,0.5)),
        url('/hero.jpg')
}
```

Before v0.4.3, multi-line values broke — keep on one line.
