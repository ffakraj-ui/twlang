# Accessibility Guide

Building accessible websites with TW Framework is straightforward when you follow these practices.

## Semantic HTML

Always use the correct HTML element for the content:

```tw
// Good
nav {
    ul {
        li { a "Home" { href "/" } }
        li { a "About" { href "/about" } }
    }
}

main {
    article {
        h1 "Blog Post Title"
        time "2024-01-15" { datetime "2024-01-15" }
        p "Post content..."
    }
}

footer {
    p "Copyright 2024"
}
```

### Landmark Elements

Use these for screen reader navigation:

| Element | Purpose |
|---------|---------|
| `header` | Banner |
| `nav` | Navigation |
| `main` | Primary content |
| `article` | Self-contained content |
| `section` | Thematic grouping |
| `aside` | Sidebar |
| `footer` | Footer |

## Images

Always provide meaningful `alt` text:

```tw
// Good — descriptive alt
img {
    src "/assets/team-photo.jpg"
    alt "TW Framework core team at the 2024 conference"
    width "800"
    height "600"
}

// Good — decorative image
img {
    src "/assets/decorative-wave.svg"
    alt ""
    role "presentation"
}

// Avoid — missing alt
img { src "/assets/photo.jpg" }
```

## Forms

### Labels

Every input needs a label:

```tw
// Good
label "Email Address" { for "email" }
input {
    id "email"
    type "email"
    name "email"
    required "true"
    aria-describedby "email-help"
}
span { id "email-help" class "help-text" "We'll never share your email." }

// Avoid — placeholder as label
input { type "email" placeholder "Email" }
```

### Error Messages

```tw
div {
    class "field"
    label "Password" { for "password" }
    input {
        id "password"
        type "password"
        aria-invalid "true"
        aria-describedby "password-error"
    }
    span {
        id "password-error"
        class "error"
        role "alert"
        "Password must be at least 8 characters."
    }
}
```

### Fieldsets

Group related fields:

```tw
fieldset {
    legend "Shipping Address"

    div {
        class "field"
        label "Street" { for "street" }
        input { id "street" name "street" }
    }

    div {
        class "field"
        label "City" { for "city" }
        input { id "city" name "city" }
    }
}
```

## Keyboard Navigation

### Focus Indicators

Ensure focus is visible:

```css
/* In your .tss file */
a:focus,
button:focus,
input:focus {
    outline: 2px solid var(--color-primary)
    outline-offset: 2px
}
```

### Skip Links

Add a skip-to-content link:

```tw
a "Skip to main content" {
    href "#main"
    class "skip-link"
}

main {
    id "main"
    tabindex "-1"
    // Content here
}
```

```css
.skip-link {
    position: absolute
    top: -40px
    left: 0
    background: var(--color-primary)
    color: white
    padding: 8px 16px
    z-index: 100
}

.skip-link:focus {
    top: 0
}
```

### Tab Order

Ensure logical tab order. Avoid positive `tabindex` values:

```tw
// Good — natural order
form {
    input { name "first" }
    input { name "second" }
    button "Submit"
}

// Avoid — confusing order
input { name "second" tabindex "2" }
input { name "first" tabindex "1" }
```

## ARIA Attributes

Use ARIA when HTML semantics are insufficient:

### Live Regions

```tw
div {
    id "status"
    role "status"
    aria-live "polite"
    aria-atomic "true"
    // Content updated dynamically
}
```

### Modals

```tw
div {
    id "modal"
    role "dialog"
    aria-modal "true"
    aria-labelledby "modal-title"
    aria-describedby "modal-desc"

    h2 { id "modal-title" "Confirm Action" }
    p { id "modal-desc" "Are you sure you want to delete this item?" }

    button "Cancel" { on:click "closeModal()" }
    button "Delete" { on:click "confirmDelete()" }
}
```

### Navigation

```tw
nav {
    aria-label "Main navigation"
    ul {
        li { a "Home" { href "/" aria-current "page" } }
        li { a "About" { href "/about" } }
    }
}
```

## Color and Contrast

### Minimum Contrast Ratios

| Text Size | WCAG AA | WCAG AAA |
|-----------|---------|----------|
| Normal (< 18px) | 4.5:1 | 7:1 |
| Large (>= 18px bold or 24px) | 3:1 | 4.5:1 |

### Testing Tools

- WebAIM Contrast Checker
- Browser DevTools (Lighthouse)
- axe DevTools extension

### Don't Rely on Color Alone

```tw
// Avoid — color-only indication
span { class "status-red" } "Error"

// Good — color + icon + text
span { class "status-error" }
    svg { aria-hidden "true" /* error icon */ }
    " Error: Invalid input"
```

## Motion and Animation

### Respect `prefers-reduced-motion`

```css
@media (prefers-reduced-motion: reduce) {
    *,
    *::before,
    *::after {
        animation-duration: 0.01ms !important
        animation-iteration-count: 1 !important
        transition-duration: 0.01ms !important
    }
}
```

### Avoid Auto-Playing Content

```tw
video {
    src "/assets/demo.mp4"
    controls "true"
    // Never use autoplay without user consent
}
```

## Testing Accessibility

### Automated Testing

```bash
# Run TW diagnostics
tw check [home]/pages/index.tw

# Use Lighthouse in Chrome DevTools
# Or install axe-core
```

### Manual Testing

1. **Keyboard only**: Navigate entire site using only Tab, Enter, Space, Arrow keys.
2. **Screen reader**: Test with NVDA (Windows), VoiceOver (macOS), or TalkBack (Android).
3. **Zoom**: Test at 200% and 400% zoom levels.
4. **Color blindness**: Test with simulators for protanopia, deuteranopia, tritanopia.

## Accessibility Checklist

- [ ] All images have appropriate `alt` text
- [ ] Form inputs have associated labels
- [ ] Focus indicators are visible
- [ ] Skip link is present
- [ ] Heading hierarchy is logical (h1 → h2 → h3)
- [ ] Color contrast meets WCAG AA
- [ ] Interactive elements are keyboard accessible
- [ ] ARIA labels are used where needed
- [ ] Reduced motion is respected
- [ ] Tested with keyboard-only navigation
- [ ] Tested with a screen reader
