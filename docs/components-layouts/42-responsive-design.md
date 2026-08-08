# Responsive Design

## Media Queries

```css
.container {
    width 100%
    padding 16px
}

@media (min-width: 768px) {
    .container {
        max-width 720px
        padding 24px
    }
}

@media (min-width: 1024px) {
    .container {
        max-width 960px
        padding 32px
    }
}
```

## Common Breakpoints

| Breakpoint | Width | Target |
|---|---|---|
| Mobile | < 640px | Phones |
| min-width: 640px | >= 640px | Large phones |
| min-width: 768px | >= 768px | Tablets |
| min-width: 1024px | >= 1024px | Laptops |
| min-width: 1280px | >= 1280px | Desktops |

## Flexbox Layouts

```css
.nav {
    display flex
    flex-direction column
    gap 8px
}

@media (min-width: 768px) {
    .nav {
        flex-direction row
        justify-content space-between
        align-items center
    }
}
```

## Grid Layouts

```css
.gallery {
    display grid
    grid-template-columns 1fr
    gap 16px
}

@media (min-width: 640px) {
    .gallery { grid-template-columns 1fr 1fr }
}

@media (min-width: 1024px) {
    .gallery { grid-template-columns 1fr 1fr 1fr }
}
```

## Responsive Typography

```css
h1 {
    font-size 24px
}

@media (min-width: 768px) {
    h1 { font-size 36px }
}

@media (min-width: 1024px) {
    h1 { font-size 48px }
}
```

## Viewport Meta Tag

Always include in head:

```tw
head {
    meta { name "viewport" content "width=device-width, initial-scale=1" }
}
```
