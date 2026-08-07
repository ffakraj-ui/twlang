# CSS Properties and Aliases

## Full Property List

### Layout

`display`, `position`, `top`, `right`, `bottom`, `left`, `float`, `clear`, `overflow`, `overflow-x`, `overflow-y`, `z-index`, `visibility`

### Sizing

`width`, `height`, `min-width`, `max-width`, `min-height`, `max-height`

### Spacing

`margin`, `margin-top`, `margin-right`, `margin-bottom`, `margin-left`, `padding`, `padding-top`, `padding-right`, `padding-bottom`, `padding-left`

### Border

`border`, `border-top`, `border-right`, `border-bottom`, `border-left`, `border-width`, `border-style`, `border-color`, `border-radius`, `box-sizing`, `box-shadow`, `outline`

### Background

`background`, `background-color`, `background-image`, `background-size`, `background-position`, `background-repeat`, `background-attachment`

### Typography

`color`, `font`, `font-size`, `font-family`, `font-weight`, `font-style`, `font-variant`, `line-height`, `letter-spacing`, `word-spacing`, `text-align`, `text-decoration`, `text-transform`, `text-shadow`, `white-space`, `word-break`, `word-wrap`

### Flexbox

`flex`, `flex-direction`, `flex-wrap`, `flex-flow`, `justify-content`, `align-items`, `align-self`, `align-content`, `flex-grow`, `flex-shrink`, `flex-basis`, `order`, `gap`

### Grid

`grid`, `grid-template`, `grid-template-columns`, `grid-template-rows`, `grid-column`, `grid-row`, `grid-gap`, `column-gap`, `row-gap`

### Effects & Animation

`transition`, `animation`, `transform`, `opacity`, `cursor`

### Other

`list-style`, `pointer-events`, `user-select`, `content`

## CSS Aliases

| Alias | Compiles To |
|---|---|
| `bg` | `background` |
| `radius` | `border-radius` |
| `shadow` | `box-shadow` |
| `font` | `font-size` |

### Usage

```css
.card {
    bg #ffffff
    radius 12px
    shadow 0 4px 12px rgba(0,0,0,0.1)
    font 16px
}
```

Compiles to:

```css
.card {
    background: #ffffff;
    border-radius: 12px;
    box-shadow: 0 4px 12px rgba(0,0,0,0.1);
    font-size: 16px;
}
```

## Units

TW supports all standard CSS units: `px`, `em`, `rem`, `vh`, `vw`, `%`, `s`, `ms`, `deg`, `fr`, `ch`, `ex`, `pt`, `cm`, `mm`, `in`

## Colors

- Hex: `#fff`, `#22c55e`, `#ff000080`
- Named: `red`, `blue`, `transparent`
- RGB: `rgb(255, 0, 0)`
- RGBA: `rgba(255, 0, 0, 0.5)`
- HSL: `hsl(120, 100%, 50%)`
- CSS variables: `var(--primary)`
