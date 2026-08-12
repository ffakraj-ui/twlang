# Advanced Components

## Component Composition

Components can compose other components:

```tw
// Card.tw
import "Button"
import "Badge"

div {
    class "card"
    Badge { text "New", variant "success" }
    h3 "{title}"
    p "{description}"
    Button { text "Learn More", href "/learn" }
}
```

## Slots (children)

Pass children to components using `{children}`:

```tw
// Layout.tw
div {
    class "layout"
    header { h1 "{title}" }
    main { {children} }
    footer { p "© 2024" }
}
```

## Conditional Props

```tw
// Alert.tw
div {
    class "alert alert-{variant}"
    if dismissible {
        button "x" { on:click "close()", class "close" }
    }
    p "{message}"
}
```

## Default Prop Values

```tw
// Button.tw
let variant = variant || "primary"
let size = size || "medium"

button "{text}" {
    class "btn btn-{variant} btn-{size}"
}
```
