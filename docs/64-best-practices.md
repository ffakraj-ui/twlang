# Best Practices

## File Organization

### One component per file

```tw
// [home]/components/Hero.tw - only Hero component
div { class "hero", h1 "{title}" }
```

### Group related pages

```
[home]/pages/
├── blog/
│   ├── index.tw
│   ├── [slug].tw
│   └── category/
│       └── [name].tw
├── docs/
│   ├── index.tw
│   └── [section].tw
└── index.tw
```

### Shared styles

```
[home]/style/
├── base.tss         # Reset, variables, globals
├── typography.tss   # Headings, paragraphs
├── components.tss   # Buttons, cards, forms
└── pages/
    ├── home.tss
    └── blog.tss
```

## Performance Best Practices

### 1. Default to static

```tw
page { render static }
```

Only use render server when you need per-request data.

### 2. Lazy load below the fold

```tw
img { src "/hero.webp", loading "eager" }
img { src "/feature.webp", loading "lazy" }
```

### 3. Minimize JavaScript

```tw
// Bad: adds JS runtime for a simple alert
button "Click" { on:click "alert('hi')" }

// Better: use a plain link if no JS needed
a "Click" { href "/page" }
```

### 4. Use CSS variables

```css
:root {
    --primary #22c55e
    --radius 8px
    --shadow 0 2px 8px rgba(0,0,0,0.1)
}
```

### 5. Compress images before build

```bash
cwebp -q 80 image.jpg -o image.webp
```

## Security Best Practices

### 1. Never expose secrets

```
env {
  public "API_URL"        // OK - public URL
  // Don't add DATABASE_URL, JWT_SECRET here!
}
```

### 2. Always validate input

```js
export function POST(request) {
    const { name, email } = request.body;
    if (!name || !email) {
        return { status: 400, json: { error: "Missing fields" } };
    }
}
```

### 3. Use middleware for auth

```tw
rule "protect" {
    match "/admin/**"
    auth { cookie "session", redirect "/login" }
}
```

### 4. Rate limit API routes

```tw
rule "api-limit" {
    match "/api/**"
    rate_limit { requests 100, window 60 }
}
```

## Code Style

### Consistent indentation

Use 4 spaces:

```tw
body {
    div {
        class "card"
        h1 "Title"
    }
}
```

### Descriptive variable names

```tw
// Good
let userCount = 0
let isActive = true

// Bad
let n = 0
let a = true
```

### Comment complex logic

```tw
// Calculate total price including 18% GST
let basePrice = 1000
let gstRate = 0.18
let total = basePrice + (basePrice * gstRate)
```
