# Themes and Dark Mode

## CSS Variables for Theming

```css
:root {
    --bg #ffffff
    --text #1a1a1a
    --primary #22c55e
    --surface #f8f9fa
    --border #e5e7eb
    --radius 8px
    --shadow 0 2px 8px rgba(0,0,0,0.1)
}

@media (prefers-color-scheme: dark) {
    :root {
        --bg #1a1a1a
        --text #ffffff
        --primary #22c55e
        --surface #2d2d2d
        --border #404040
        --shadow 0 2px 8px rgba(0,0,0,0.3)
    }
}

body {
    bg var(--bg)
    color var(--text)
    transition background 0.3s, color 0.3s
}

.card {
    bg var(--surface)
    radius var(--radius)
    shadow var(--shadow)
    border 1px solid var(--border)
}
```

## Manual Theme Toggle

```tw
let theme = "light"

script {
    function toggleTheme() {
        theme = theme === "light" ? "dark" : "light";
        document.documentElement.setAttribute("data-theme", theme);
        localStorage.setItem("theme", theme);
    }

    const saved = localStorage.getItem("theme");
    if (saved) {
        document.documentElement.setAttribute("data-theme", saved);
        theme = saved;
    }
}

button "Toggle Theme" {
    on:click "toggleTheme()"
    class "theme-toggle"
}
```

## Data-attribute Based Theming

```css
[data-theme="dark"] {
    --bg #1a1a1a
    --text #ffffff
    --surface #2d2d2d
    --border #404040
}

[data-theme="light"] {
    --bg #ffffff
    --text #1a1a1a
    --surface #f8f9fa
    --border #e5e7eb
}
```
