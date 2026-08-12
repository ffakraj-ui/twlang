# Theme Customization

TW Framework includes a powerful theme system supporting light, dark, and system modes.

## Basic Setup

Enable themes in `tw.config`:

```
name: "My Site"
theme: system
theme_storage_key: "my_site_theme"
```

Options for `theme`:
- `"system"` — follows OS preference (default)
- `"dark"` — always dark
- `"light"` — always light
- `"off"` — disables theme switching

## How It Works

When enabled, TW injects a small inline script that:

1. Reads the saved preference from `localStorage`
2. Falls back to `prefers-color-scheme` media query
3. Applies `data-theme` and `class` attributes to `<html>`
4. Exposes `window.__twSetTheme(mode)` and `window.__twToggleTheme()`

## CSS Implementation

Use CSS custom properties for theming:

```css
/* In global.tss */
:root {
    --bg: #ffffff
    --text: #1f2937
    --primary: #22c55e
    --border: #e5e7eb
    --card-bg: #f9fafb
}

:root[data-theme="dark"],
.dark {
    --bg: #0f172a
    --text: #f1f5f9
    --primary: #4ade80
    --border: #334155
    --card-bg: #1e293b
}

body {
    background: var(--bg)
    color: var(--text)
}

.card {
    background: var(--card-bg)
    border: 1px solid var(--border)
}
```

## Toggle Button

Add a theme switcher to your header:

```tw
// Header.tw
button {
    id "theme-toggle"
    class "theme-btn"
    aria-label "Toggle dark mode"
    on:click "window.__twToggleTheme()"

    span { id "theme-icon" "🌙" }
}
```

```javascript
// Update icon based on current theme
function updateThemeIcon() {
  const isDark = document.documentElement.getAttribute('data-theme') === 'dark';
  document.getElementById('theme-icon').textContent = isDark ? '☀️' : '🌙';
}

// Listen for theme changes
window.addEventListener('storage', (e) => {
  if (e.key === 'my_site_theme') updateThemeIcon();
});

updateThemeIcon();
```

## Multiple Themes

You can define more than two themes:

```css
:root[data-theme="blue"] {
    --bg: #eff6ff
    --text: #1e3a5f
    --primary: #3b82f6
}

:root[data-theme="sepia"] {
    --bg: #f5e6d3
    --text: #5c4033
    --primary: #d97706
}
```

```javascript
// Switch to custom theme
window.__twSetTheme('blue');
```

## Component-Level Themes

Some components can have their own theme overrides:

```tw
// Card.tw
let theme = "default"

article {
    class "card card-theme-{theme}"
    slot {}
}
```

```css
.card-theme-blue {
    --card-bg: #dbeafe
    --card-border: #3b82f6
}

.card-theme-danger {
    --card-bg: #fee2e2
    --card-border: #ef4444
}
```

## Theme in .twm API

Return theme-aware data:

```twm
function get_theme_settings(request):
    return json_response({
        "default": "system",
        "available": ["light", "dark", "blue", "sepia"],
        "storage_key": "my_site_theme"
    })
```

## Best Practices

1. **Always define both themes**: Don't leave dark mode half-implemented.
2. **Test contrast**: Ensure text is readable in both modes.
3. **Respect system preference**: Default to `system` mode.
4. **Avoid flashing**: The inline script runs before paint to prevent FOUC.
5. **Persist choice**: Use `localStorage` so users don't have to re-select.

## Common Theme Variables

```css
:root {
    /* Backgrounds */
    --bg: #ffffff
    --bg-secondary: #f9fafb
    --bg-tertiary: #f3f4f6

    /* Text */
    --text: #111827
    --text-secondary: #6b7280
    --text-muted: #9ca3af

    /* Brand */
    --primary: #22c55e
    --primary-hover: #16a34a
    --primary-text: #ffffff

    /* Borders */
    --border: #e5e7eb
    --border-hover: #d1d5db

    /* Shadows */
    --shadow-sm: 0 1px 2px rgba(0,0,0,0.05)
    --shadow-md: 0 4px 6px rgba(0,0,0,0.1)
    --shadow-lg: 0 10px 15px rgba(0,0,0,0.1)

    /* Radius */
    --radius-sm: 4px
    --radius-md: 8px
    --radius-lg: 12px
}
```
