# Components

Components are reusable `.tw` files stored in `[home]/components/`.

## Creating a Component

`[home]/components/Hero.tw`:

```tw
div {
    class "hero"
    h1 "{title}"
    p "{subtitle}"
}
```

## Using a Component

Import and use in any page:

```tw
import "Hero"

body {
    Hero {
        title "Welcome to TW"
        subtitle "Build fast, ship faster"
    }
}
```

## Component Props

Props are passed as attributes:

```tw
import "Button"

body {
    Button {
        text "Click Me"
        variant "primary"
        href "/signup"
    }
}
```

Inside the component, access props as variables:

```tw
// Button.tw
button "{text}" {
    class "btn btn-{variant}"
    onclick "window.location.href='{href}'"
}
```

## Nested Components

Components can import other components:

```tw
// Card.tw
import "Button"

div {
    class "card"
    h3 "{title}"
    p "{description}"
    Button {
        text "Learn More"
        variant "secondary"
        href "/learn"
    }
}
```

## Component Organization

```
[home]/components/
├── Header.tw
├── Footer.tw
├── Hero.tw
├── Button.tw
├── Card.tw
└── nav/
    ├── Breadcrumb.tw
    └── Pagination.tw
```

Components can be organized in subfolders. Import path is relative to `[home]/components/`.

## Component Resolution

TW searches for components in this order:

1. `[home]/components/{name}.tw`
2. `[home]/components/{name}/index.tw`
3. Subfolders within `components/`

## Error: Component Not Found

```
CompilerError: Component `Hero` not found
```

Check:
- File exists at `[home]/components/Hero.tw`
- Import name matches filename (case-insensitive)
- No typos in import statement
