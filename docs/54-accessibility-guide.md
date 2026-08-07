# Accessibility Guide

## Semantic HTML

```tw
header { nav { a "Home" { href "/" } } }
main { h1 "Page Title", p "Content" }
footer { p "2024 My Site" }
```

## ARIA Attributes

```tw
button "Toggle Menu" {
    aria-label "Toggle navigation menu"
    aria-expanded "false"
    on:click "toggleMenu()"
}

div {
    role "alert"
    aria-live "polite"
    p "Form submitted successfully"
}
```

## Alt Text

```tw
img { src "/photo.webp", alt "A sunset over the mountains", width 800, height 600 }
img { src "/icon.svg", alt "", role "presentation" }
```

## Form Labels

```tw
label "Email address" { for "email" }
input { type "email", name "email", id "email", aria-required "true" }
```

## Keyboard Navigation

```tw
div {
    tabindex "0"
    on:keydown "handleKey(event)"
    p "Focusable element"
}
```

## Skip Links

```tw
body {
    a "Skip to content" { href "#main", class "skip-link" }
    main { id "main", h1 "Content" }
}
```

## Focus Management

```css
.skip-link {
    position absolute
    top -40px
    left 0
    bg #22c55e
    color white
    padding 8px 16px
    z-index 100
    transition top 0.2s

    &:focus {
        top 0
    }
}

*:focus-visible {
    outline 2px solid #22c55e
    outline-offset 2px
}
```
