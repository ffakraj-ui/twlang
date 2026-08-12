# Dark Mode and Theming

## CSS Variables for Theming

```css
:root {
    --bg #ffffff
    --text #1a1a1a
    --primary #22c55e
    --card-bg #f9fafb
    --border #e5e7eb
}

[data-theme="dark"] {
    --bg #0f1115
    --text #e6edf3
    --primary #22c55e
    --card-bg #1a1f2e
    --border #2a3340
}

body {
    background var(--bg)
    color var(--text)
    transition background 0.3s ease, color 0.3s ease
}

.card {
    background var(--card-bg)
    border 1px solid var(--border)
}
```

## Theme Toggle

```tw
let theme = "light"

button {
    on:click "toggleTheme()"
    class "theme-toggle"
    text "Moon"
}

script {
    function toggleTheme() {
        theme = theme === 'light' ? 'dark' : 'light'
        document.documentElement.setAttribute('data-theme', theme)
        localStorage.setItem('theme', theme)
    }

    const saved = localStorage.getItem('theme')
    if (saved) {
        document.documentElement.setAttribute('data-theme', saved)
        theme = saved
    }
}
```

## Theme in tw.config

```
theme: system
```

Values: `system` (auto), `light`, `dark`
