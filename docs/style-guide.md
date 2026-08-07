# Style Guide

Consistent code style makes TW projects readable and maintainable.

## General Principles

- **Readability first**: Code is read more than it is written.
- **Consistency**: Pick a style and apply it project-wide.
- **Minimal nesting**: Avoid deeply nested blocks. Extract components when indentation exceeds 4 levels.

## .tw File Formatting

### Indentation

Use 4 spaces per indent level. Do not use tabs.

```tw
body {
    section {
        class "container"
        div {
            class "grid"
            article {
                class "card"
                h2 "Title"
                p "Description"
            }
        }
    }
}
```

### Blank Lines

Separate logical sections with a single blank line:

```tw
page {
    title "Home"
    layout "main"
    render static
}

load "@./style/home.tss"

head {
    seo { description "Welcome to my site" }
}

body {
    Hero {}
    Features {}
    CTA {}
    Footer {}
}
```

### Line Length

Keep lines under 100 characters. Break long attribute lists:

```tw
// Good
img {
    src "/assets/hero.jpg"
    alt "Mountain landscape at sunset"
    class "hero-image"
    loading "lazy"
}

// Avoid
img { src "/assets/hero.jpg" alt "Mountain landscape at sunset" class "hero-image" loading "lazy" }
```

### Attribute Ordering

Order attributes consistently:

1. `id`
2. `class`
3. `src` / `href`
4. `alt` / `title`
5. Event handlers (`on:click`, etc.)
6. Data attributes
7. ARIA attributes

```tw
a {
    id "cta-button"
    class "btn btn-primary"
    href "/signup"
    title "Create your account"
    on:click "trackSignup()"
    data-track "signup-header"
    aria-label "Sign up for a free account"
}
```

## .tss File Formatting

### Property Ordering

Group properties logically:

1. Layout (display, position, float)
2. Box model (width, height, margin, padding)
3. Typography (font, line-height, color)
4. Visual (background, border, radius)
5. Animation (transition, animation)

```css
.card {
    display: flex
    flex-direction: column
    position: relative
    width: 100%
    max-width: 400px
    margin: 0 auto
    padding: 24px
    font-size: 16px
    line-height: 1.5
    color: var(--text-color)
    background: white
    border: 1px solid var(--border-color)
    radius: 12px
    transition: transform 0.2s ease
}
```

### Units

- Use `px` for fixed sizes (borders, breakpoints).
- Use `rem` for typography and spacing when possible.
- Use `%` or `fr` for fluid layouts.

```css
// Good
h1 {
    font-size: 2.5rem
    margin-bottom: 1.5rem
}

// Avoid
h1 {
    font-size: 40px
    margin-bottom: 24px
}
```

### Comments

Use block comments for sections:

```css
/* ========================================
   HEADER COMPONENT
   ======================================== */

.header {
    position: fixed
    top: 0
    width: 100%
    z-index: 1000
}

/* Navigation links */
.nav-link {
    color: var(--text-muted)
    text-decoration: none
    transition: color 0.2s
}

.nav-link:hover {
    color: var(--primary)
}
```

## .twm File Formatting

### Function Naming

Use `snake_case` for handler names:

```twm
function get_users(request):
    return json_response({"users": []})

function create_user(request):
    data = request.json()
    return json_response({"id": 1}, status=201)
```

### Error Responses

Always return consistent error shapes:

```twm
function handle_error(message, status=400):
    return json_response({
        "error": True,
        "message": message,
        "status": status
    }, status=status)
```

### Route Organization

One route per file. Name the file `route.twm` inside a folder matching the endpoint:

```
api/
  users/
    route.twm
  users/[id]/
    route.twm
```

## Naming Conventions Summary

| Context | Convention | Example |
|---------|-----------|---------|
| Variables | snake_case | `user_name`, `item_count` |
| Components | PascalCase | `UserCard`, `NavMenu` |
| CSS classes | kebab-case | `user-card`, `nav-menu` |
| File names | kebab-case | `user-card.tw`, `nav-menu.tss` |
| Constants | UPPER_SNAKE_CASE | `MAX_ITEMS`, `API_BASE` |
| Event handlers | camelCase | `handleClick`, `onSubmit` |

## Anti-Patterns to Avoid

### Inline Styles

Avoid `style` attributes. Use `.tss` files:

```tw
// Avoid
div { style "color: red; font-size: 20px" }

// Good
div { class "error-message" }
```

### Deep Nesting

```tw
// Avoid
body {
    div {
        div {
            div {
                div {
                    div { p "Too deep" }
                }
            }
        }
    }
}

// Good
body {
    PageWrapper {
        Content {}
    }
}
```

### Magic Strings

```tw
// Avoid
if role == "admin" { ... }

// Good
let ADMIN_ROLE = "admin"
if role == ADMIN_ROLE { ... }
```
