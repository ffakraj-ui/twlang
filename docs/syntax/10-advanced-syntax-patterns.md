# Advanced Syntax Patterns

Advanced patterns, edge cases, and professional techniques for TW Framework syntax.

## Pattern 1: Conditional Classes

### Multiple Conditional Classes

```tw
let is_active = true
let is_large = false
let theme = "dark"

body {
    div {
        class "button"
        if is_active {
            class "button active"
        }
        if is_large {
            class "button large"
        }
        if theme == "dark" {
            class "button dark"
        }
        "Click me"
    }
}
```

**Output:** `<div class="button active dark">Click me</div>`

### Common Mistake: Overwriting Classes

```tw
// WRONG - Only last class attribute wins
body {
    div {
        class "button"
        class "active"  // Overwrites "button"
    }
}
```

**Output:** `<div class="active"></div>` (button lost!)

**Fix:** Combine into one class attribute.

```tw
// CORRECT
body {
    div {
        class "button active"
    }
}
```

## Pattern 2: Dynamic Tag Names

### Not Supported Directly

```tw
// WRONG - TW does not support dynamic tags
let tag = "h1"

body {
    tag {  // Creates <tag> element, not <h1>
        "Hello"
    }
}
```

**Fix:** Use conditional rendering.

```tw
// CORRECT
let level = 1

body {
    if level == 1 {
        h1 "Hello"
    } else if level == 2 {
        h2 "Hello"
    } else {
        h3 "Hello"
    }
}
```

## Pattern 3: Complex Conditionals

### Multiple Conditions

```tw
let user = {role: "admin", active: true, verified: true}

body {
    if user.role == "admin" and user.active and user.verified {
        p "Admin dashboard"
    } else if user.role == "admin" and not user.verified {
        p "Please verify your account"
    } else {
        p "User dashboard"
    }
}
```

### Common Mistake: Using && and ||

```tw
// WRONG - TW uses 'and' and 'or', not '&&' and '||'
body {
    if user.active && user.verified {
        p "OK"
    }
}
```

**Compiler Error:** `TW3003: Invalid operator '&&'. Use 'and'.`

**Fix:** Use TW operators.

```tw
// CORRECT
body {
    if user.active and user.verified {
        p "OK"
    }
}
```

## Pattern 4: Nested Loops

### Loop Inside Loop

```tw
let categories = [
    {name: "Fruits", items: ["Apple", "Banana"]},
    {name: "Vegetables", items: ["Carrot", "Spinach"]}
]

body {
    each categories as category {
        section {
            h2 "{category.name}"
            ul {
                each category.items as item {
                    li "{item}"
                }
            }
        }
    }
}
```

### Common Mistake: Variable Name Collision

```tw
// WRONG - 'item' used in both loops
body {
    each categories as category {
        each category.items as item {
            li "{item}"
        }
        each category.tags as item {  // Same name!
            span "{item}"
        }
    }
}
```

**Warning:** `TW3004: Variable 'item' already in outer scope.`

**Fix:** Use different names.

```tw
// CORRECT
body {
    each categories as category {
        each category.items as food {
            li "{food}"
        }
        each category.tags as tag {
            span "{tag}"
        }
    }
}
```

## Pattern 5: Optional Chaining

### Safe Property Access

```tw
let user = {profile: {name: "John"}}

body {
    p "{user.profile?.name ?? 'Anonymous'}"
}
```

### Common Mistake: Deep Access Without Check

```tw
// WRONG - Errors if profile is null
body {
    p "{user.profile.name}"
}
```

**Runtime Error:** `Cannot read property 'name' of null`

**Fix:** Use optional chaining or check first.

```tw
// CORRECT
body {
    if user.profile {
        p "{user.profile.name}"
    } else {
        p "Anonymous"
    }
}
```

## Pattern 6: Computed Values

### Pre-Computing in Variables

```tw
let items = [10, 20, 30, 40, 50]
let total = items.reduce((a, b) => a + b, 0)
let average = total / items.length
let max = Math.max(...items)

body {
    p "Total: {total}"
    p "Average: {average}"
    p "Max: {max}"
}
```

### Common Mistake: Complex Logic in Templates

```tw
// WRONG - Hard to read
body {
    p "Total: {items.reduce((a,b)=>a+b,0)}"
    p "Avg: {items.reduce((a,b)=>a+b,0)/items.length}"
}
```

**Fix:** Pre-compute values.

## Pattern 7: Multi-Line Strings

### Using Concatenation

```tw
let long_text = "This is a very long text that " +
                "spans multiple lines for better " +
                "readability in the source code."

body {
    p "{long_text}"
}
```

## Pattern 8: Component Composition with Slots

### Default Slot with Fallback

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
    p "This is the slot content."
    button "Action" { class "btn" }
}
```

## Pattern 9: Escape Sequences in Strings

### Supported Escapes

```tw
let quote = "She said \"Hello\""
let newline = "Line 1\nLine 2"
let tab = "Col1\tCol2"
let backslash = "C:\\Users\\John"

body {
    p "{quote}"
    pre "{newline}"
}
```

### Common Mistake: Unescaped Quotes

```tw
// WRONG
let text = "He said "Hello" to me"
```

**Compiler Error:** `TW1001: Unterminated string.`

**Fix:** Escape inner quotes.

```tw
// CORRECT
let text = "He said \"Hello\" to me"
```

## Pattern 10: Working with Dates

### Date Formatting

```tw
let post = {date: "2024-01-15T10:30:00Z"}

body {
    time "{new Date(post.date).toLocaleDateString()}"

    let formatted = new Date(post.date).toLocaleDateString("en-US", {
        year: "numeric",
        month: "long",
        day: "numeric"
    })

    p "Published on {formatted}"
}
```

## Pattern 11: URL Construction

### Building URLs

```tw
let base_url = "https://api.example.com"
let endpoint = "/users"
let user_id = "123"
let full_url = base_url + endpoint + "/" + user_id

body {
    a "View User" { href "{full_url}" }
}
```

### Query Parameters

```tw
let search = "framework"
let page = 1
let query_url = "/search?q=" + encodeURIComponent(search) + "&page=" + page

body {
    a "Search Results" { href "{query_url}" }
}
```

## Pattern 12: Form Handling

### Complete Form Example

```tw
let form_data = {name: "", email: "", message: ""}
let errors = {}
let submitted = false

body {
    if submitted and not errors {
        div {
            class "success"
            p "Thank you! We'll be in touch."
        }
    } else {
        form {
            on:submit "handleSubmit(event)"

            div {
                class "field"
                label "Name" { for "name" }
                input {
                    id "name"
                    type "text"
                    bind:value "form_data.name"
                }
                if errors.name {
                    span { class "error" "{errors.name}" }
                }
            }

            div {
                class "field"
                label "Email" { for "email" }
                input {
                    id "email"
                    type "email"
                    bind:value "form_data.email"
                }
                if errors.email {
                    span { class "error" "{errors.email}" }
                }
            }

            div {
                class "field"
                label "Message" { for "message" }
                textarea {
                    id "message"
                    bind:value "form_data.message"
                }
            }

            button "Send" { type "submit" class "btn" }
        }
    }
}

script {
    function handleSubmit(e) {
        e.preventDefault();
        errors = {};

        if (!form_data.name.trim()) {
            errors.name = "Name is required";
        }

        if (!form_data.email.includes("@")) {
            errors.email = "Valid email required";
        }

        if (Object.keys(errors).length === 0) {
            submitted = true;
        }
    }
}
```

## Pattern 13: Pagination Logic

```tw
let items = load_json "items"
let items_per_page = 10
let current_page = 1
let total_pages = Math.ceil(items.length / items_per_page)
let start = (current_page - 1) * items_per_page
let page_items = items.slice(start, start + items_per_page)

body {
    each page_items as item {
        ItemCard { props item }
    }

    if total_pages > 1 {
        nav {
            class "pagination"
            if current_page > 1 {
                a "Previous" { href "?page={current_page - 1}" }
            }

            span "Page {current_page} of {total_pages}"

            if current_page < total_pages {
                a "Next" { href "?page={current_page + 1}" }
            }
        }
    }
}
```

## Best Practices for Advanced Patterns

1. Pre-compute values - don't put complex logic in templates
2. Use descriptive variable names: `formatted_date` not `d`
3. Handle null/undefined - always check before deep access
4. Avoid nested loops when possible - flatten data structure
5. Use consistent naming: camelCase for variables, kebab-case for classes
6. Comment complex logic - explain why, not what
7. Test edge cases: empty arrays, null values, large datasets
8. Keep components small - extract when logic gets complex
