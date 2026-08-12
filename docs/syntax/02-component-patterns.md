# Component Patterns and Anti-Patterns

Master component syntax in TW Framework with these proven patterns and common mistakes to avoid.

## Pattern 1: Basic Component Structure

### Correct Structure

```tw
// [home]/components/Button.tw
let label = "Click me"
let variant = "primary"
let disabled = "false"

button {
    class "btn btn-{variant}"
    disabled "{disabled}"
    on:click "handleClick()"
    "{label}"
}
```

### Usage

```tw
// [home]/index.tw
import "Button"

body {
    Button {
        label "Submit"
        variant "secondary"
    }
}
```

### Common Mistake: Missing Props

```tw
// WRONG — Using component without required props
body {
    Button {}
}
```

**Result:** Component renders with empty/default values. May break if props are required.

**Fix:** Always provide meaningful props or set good defaults in the component.

```tw
// CORRECT — With defaults in component
// [home]/components/Button.tw
let label = "Click me"  // Default value
let variant = "primary" // Default value

button {
    class "btn btn-{variant}"
    "{label}"
}
```

## Pattern 2: Props with Complex Types

### Passing Objects

```tw
// [home]/components/UserCard.tw
let user = {}

article {
    class "user-card"
    img {
        src "{user.avatar}"
        alt "{user.name}"
    }
    h3 "{user.name}"
    p "{user.bio}"
}
```

```tw
// Usage
UserCard {
    user {
        name "John Doe"
        avatar "/avatars/john.jpg"
        bio "Full stack developer"
    }
}
```

### Common Mistake: Wrong Object Syntax

```tw
// WRONG
UserCard {
    user = {
        name "John"
    }
}
```

**Compiler Error:** `TW3006: Invalid property assignment. Use 'key value' syntax, not 'key = value'.`

**Fix:** Use space-separated key-value pairs, not equals signs.

```tw
// CORRECT
UserCard {
    user {
        name "John"
        avatar "/john.jpg"
    }
}
```

## Pattern 3: Slot Usage

### Default Slot

```tw
// [home]/components/Card.tw
let title = ""

article {
    class "card"
    if title {
        h3 "{title}"
    }
    div {
        class "card-body"
        slot {}
    }
}
```

```tw
// Usage
Card {
    title "My Card"
    p "This content goes in the slot."
    button "Action" { class "btn" }
}
```

### Named Slots (Future Feature)

```tw
// [home]/components/Modal.tw
let title = ""

div {
    class "modal"
    header {
        class "modal-header"
        h2 "{title}"
        slot "header" {}
    }
    div {
        class "modal-body"
        slot "body" {}
    }
    footer {
        class "modal-footer"
        slot "footer" {}
    }
}
```

## Pattern 4: Component Composition

### Wrapper Components

```tw
// [home]/components/PageWrapper.tw
let max_width = "1200px"

div {
    class "page-wrapper"
    style "max-width: {max_width}; margin: 0 auto;"
    slot {}
}
```

```tw
// Usage
PageWrapper {
    max_width "960px"
    h1 "Content"
    p "More content"
}
```

### Common Mistake: Deep Nesting

```tw
// WRONG — 6 levels deep, hard to maintain
body {
    div {
        div {
            div {
                div {
                    div {
                        p "Too deep"
                    }
                }
            }
        }
    }
}
```

**Fix:** Extract into components when nesting exceeds 3 levels.

```tw
// CORRECT
body {
    PageWrapper {
        ContentSection {
            Article {}
        }
    }
}
```

## Pattern 5: Conditional Component Rendering

### With If

```tw
let user = null

body {
    if user {
        UserCard { props user }
    } else {
        LoginPrompt {}
    }
}
```

### With Ternary (Not Supported)

```tw
// WRONG — TW does not support ternary expressions
body {
    {user ? UserCard {} : LoginPrompt {}}
}
```

**Compiler Error:** `TW1000: Unexpected token '{' at line 2, col 5.`

**Fix:** Use explicit `if/else` blocks.

```tw
// CORRECT
body {
    if user {
        UserCard { props user }
    } else {
        LoginPrompt {}
    }
}
```

## Pattern 6: Component Loops

### Iterating Components

```tw
let products = load_json "products"

body {
    div {
        class "product-grid"
        each products as product {
            ProductCard { props product }
        }
    }
}
```

### Common Mistake: Missing Key

```tw
// WRONG — No unique identifier for loop items
body {
    each items as item {
        Item {}
    }
}
```

**Warning:** `TW3004: Loop items should have a unique identifier for efficient rendering.`

**Fix:** Use `id` attribute or ensure data has unique fields.

```tw
// CORRECT
body {
    each items as item {
        Item {
            id "{item.id}"
            name "{item.name}"
        }
    }
}
```

## Pattern 7: Self-Closing Components

### Components Without Children

```tw
// CORRECT — Self-closing style
Divider {}
Spacer {}
Icon { name "search" }
```

### Components With Children

```tw
// CORRECT — With slot content
Card {
    h3 "Title"
    p "Description"
}
```

## Pattern 8: Import Paths

### Relative Imports

```tw
// From [home]/blog/index.tw
import "../../components/Card"
import "../../components/Header"
```

### Alias Imports

```tw
// Using @ alias for [home]
import "@/components/Card"
import "@/components/Header"
```

### Common Mistake: Wrong Path

```tw
// WRONG — File does not exist at this path
import "components/Button"
```

**Compiler Error:** `TW2405: Component 'Button' not found at 'components/Button.tw'.`

**Fix:** Use correct relative path or alias.

```tw
// CORRECT
import "@/components/Button"
```

## Pattern 9: Component Styles

### Scoped Styles

```tw
// [home]/components/Alert.tw
let type = "info"
let message = ""

div {
    class "alert alert-{type}"
    "{message}"
}
```

```css
/* [home]/style/alert.tss */
.alert {
    padding: 16px
    radius: 8px
}

.alert-info {
    background: #dbeafe
    color: #1e40af
}

.alert-error {
    background: #fee2e2
    color: #991b1b
}
```

### Loading Component Styles

```tw
// [home]/components/Alert.tw
load "@./style/alert.tss"

let type = "info"
let message = ""

div {
    class "alert alert-{type}"
    "{message}"
}
```

## Pattern 10: Event Handling in Components

### Passing Event Handlers

```tw
// [home]/components/ConfirmButton.tw
let label = "Confirm"
let on_confirm = ""

button {
    class "btn btn-danger"
    on:click "{on_confirm}"
    "{label}"
}
```

```tw
// Usage
ConfirmButton {
    label "Delete Account"
    on_confirm "confirmDelete()"
}
```

### Common Mistake: Missing Quotes

```tw
// WRONG
ConfirmButton {
    on_confirm confirmDelete()
}
```

**Compiler Error:** `TW3005: Event handler value must be a string.`

**Fix:** Always quote event handler values.

```tw
// CORRECT
ConfirmButton {
    on_confirm "confirmDelete()"
}
```

## Anti-Patterns to Avoid

| Anti-Pattern | Why It's Bad | Solution |
|-------------|-------------|----------|
| God Component (>500 lines) | Hard to maintain, test, reuse | Split into smaller components |
| Props drilling (>3 levels) | Brittle, hard to trace | Use context or flatten hierarchy |
| Inline styles | Not reusable, hard to override | Use `.tss` files |
| Magic strings | Error-prone | Use constants |
| Deep nesting (>4 levels) | Readability suffers | Extract components |
| Missing defaults | Components break without props | Set sensible defaults |
| Tight coupling | Components depend on specific data | Pass data via props |

## Component Checklist

Before creating a component, ensure:

- [ ] File name matches component name (PascalCase)
- [ ] All props have default values
- [ ] Uses `slot {}` for flexible content
- [ ] Styles are in separate `.tss` file
- [ ] Event handlers are quoted strings
- [ ] No deeper than 3 levels of nesting
- [ ] Documented with usage examples
