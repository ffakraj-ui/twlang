# Advanced TSS

## Responsive Design

```css
.grid {
    display grid
    grid-template-columns repeat(3, 1fr)
    gap 20px

    @media (max-width: 768px) {
        grid-template-columns 1fr
    }

    @media (max-width: 480px) {
        gap 12px
    }
}
```

## Pseudo-classes

```css
.btn {
    bg #22c55e
    color white
    transition all 0.2s

    &:hover {
        bg #16a34a
        transform translateY(-2px)
    }

    &:active {
        transform translateY(0)
    }

    &:focus {
        outline 2px solid #22c55e
        outline-offset 2px
    }

    &:disabled {
        bg #ccc
        cursor not-allowed
    }
}
```

## Pseudo-elements

```css
.card {
    position relative

    &::before {
        content ""
        position absolute
        top 0
        left 0
        width 100%
        height 4px
        bg linear-gradient(90deg, #22c55e, #3b82f6)
    }

    &::after {
        content "New"
        position absolute
        top 8px
        right 8px
        bg #ef4444
        color white
        padding 2px 8px
        radius 4px
        font 10px
    }
}
```

## Complex Selectors

```css
.card .title { font 20px }
.list > .item { border-bottom 1px solid #eee }
h1 + p { margin-top 0 }
h1 ~ p { color #666 }
input[type="checkbox"] { width 20px, height 20px }
.btn-primary, .btn-secondary { padding 12px 24px }
```

## CSS Grid

```css
.layout {
    display grid
    grid-template-columns 200px 1fr 300px
    grid-template-areas "header header header" "sidebar main aside" "footer footer footer"
    min-height 100vh
}

.header { grid-area header }
.sidebar { grid-area sidebar }
.main { grid-area main }
```

## Animations

```css
@keyframes slideIn {
    0% { opacity 0, transform translateX(-20px) }
    100% { opacity 1, transform translateX(0) }
}

.element {
    animation slideIn 0.3s ease-out
}
```

## Dark Mode

```css
:root {
    --bg #ffffff
    --text #1a1a1a
}

@media (prefers-color-scheme: dark) {
    :root {
        --bg #1a1a1a
        --text #ffffff
    }
}

body {
    bg var(--bg)
    color var(--text)
}
```

## Print Styles

```css
@media print {
    .no-print { display none }
    body { color black, bg white }
}
```
