# Data Binding and Reactivity

Master variable declaration, interpolation, conditionals, loops, and reactive state in TW Framework.

## Variable Declaration

### Basic Syntax

```tw
let name = "John"
let age = 25
let is_active = true
let items = ["a", "b", "c"]
let user = {name: "John", email: "john@example.com"}
```

### Declaration Rules

1. Must use `let` — no `var`, `const`, or implicit declaration
2. Must be before `body` block
3. TW infers types from values

```tw
// CORRECT
let title = "Home"
let count = 0

body {
    h1 "{title}"
}
```

```tw
// WRONG — let inside body
body {
    let title = "Home"
    h1 "{title}"
}
```

**Compiler Error:** `TW3001: Variable declaration cannot appear inside 'body' block.`

### Common Mistake: Reassigning in Static Pages

```tw
// WRONG — Static pages don't support runtime reassignment without reactive directives
page {
    render static
}

let count = 0

body {
    button "{count}" { on:click "count++" }
}
```

**Note:** This actually WORKS because `on:click` triggers the reactive runtime. But if there are NO `on:` or `bind:` directives, variables are compile-time only.

## String Interpolation

### Basic Interpolation

```tw
let name = "World"

body {
    h1 "Hello, {name}!"
}
```

**Output:** `<h1>Hello, World!</h1>`

### Interpolation in Attributes

```tw
let image_url = "/assets/photo.jpg"
let image_alt = "My photo"

body {
    img {
        src "{image_url}"
        alt "{image_alt}"
    }
}
```

### Interpolation in Classes

```tw
let type = "primary"
let size = "large"

body {
    button {
        class "btn btn-{type} btn-{size}"
        "Click me"
    }
}
```

**Output:** `<button class="btn btn-primary btn-large">Click me</button>`

### Common Mistake: Interpolation Outside Quotes

```tw
// WRONG
body {
    h1 {name}
}
```

**Compiler Error:** `TW1001: Unexpected token 'WORD' at line 2, col 9. Expected STRING.`

**Fix:** Interpolation must be inside a quoted string.

```tw
// CORRECT
body {
    h1 "{name}"
}
```

### Common Mistake: Nested Interpolation

```tw
// WRONG
let prefix = "user"
let suffix = "name"

body {
    p "{{prefix}_{suffix}}"
}
```

**Compiler Error:** `TW3001: Nested interpolation is not supported.`

**Fix:** Pre-compute the value.

```tw
// CORRECT
let prefix = "user"
let suffix = "name"
let field_name = prefix + "_" + suffix

body {
    p "{field_name}"
}
```

## Conditional Rendering

### If Statement

```tw
let is_logged_in = true
let user_name = "John"

body {
    if is_logged_in {
        p "Welcome back, {user_name}!"
    }
}
```

### If-Else Statement

```tw
let is_logged_in = false

body {
    if is_logged_in {
        a "Dashboard" { href "/dashboard" }
    } else {
        a "Log in" { href "/login" }
    }
}
```

### If-Else If-Else

```tw
let status = "loading"

body {
    if status == "loading" {
        p { class "loading" "Loading..." }
    } else if status == "success" {
        p { class "success" "Data loaded!" }
    } else if status == "error" {
        p { class "error" "Failed to load." }
    } else {
        p "Unknown status"
    }
}
```

### Common Mistake: Assignment in Condition

```tw
// WRONG
let status = "ok"

body {
    if status = "ok" {
        p "Good"
    }
}
```

**Compiler Error:** `TW3003: Assignment not allowed in condition expression.`

**Fix:** Use comparison operator `==`.

```tw
// CORRECT
let status = "ok"

body {
    if status == "ok" {
        p "Good"
    }
}
```

### Truthy and Falsy Values

```tw
let count = 0
let name = ""
let items = []
let user = null

body {
    // Falsy in TW: 0, "", [], null, false
    if count {
        p "Count is truthy"  // Won't show (0 is falsy)
    }

    // Check explicitly
    if count > 0 {
        p "Has count"
    }

    if items.length > 0 {
        p "Has items"
    }
}
```

## Loops

### Iterating Arrays

```tw
let colors = ["red", "green", "blue"]

body {
    ul {
        each colors as color {
            li "{color}"
        }
    }
}
```

### Iterating Objects

```tw
let user = {name: "John", age: 30, city: "NYC"}

body {
    dl {
        each user as key, value {
            dt "{key}"
            dd "{value}"
        }
    }
}
```

### Iterating With Index

```tw
let items = ["a", "b", "c"]

body {
    ol {
        each items as item, index {
            li "{index + 1}. {item}"
        }
    }
}
```

### Common Mistake: Modifying Loop Variable

```tw
// WRONG
let numbers = [1, 2, 3]

body {
    each numbers as num {
        let num = num * 2
        p "{num}"
    }
}
```

**Compiler Error:** `TW3004: Cannot redeclare loop variable 'num'.`

**Fix:** Pre-process the data.

```tw
// CORRECT
let numbers = [1, 2, 3]
let doubled = [2, 4, 6]

body {
    each doubled as num {
        p "{num}"
    }
}
```

### Common Mistake: Empty Loop Without Fallback

```tw
// WRONG — No fallback, renders nothing
let items = []

body {
    each items as item {
        p "{item}"
    }
}
```

**Fix:** Add a fallback.

```tw
// CORRECT
let items = []

body {
    if items.length > 0 {
        each items as item {
            p "{item}"
        }
    } else {
        p "No items found."
    }
}
```

## Fetching Data

### fetch Directive

```tw
let posts = fetch "https://api.example.com/posts"

body {
    each posts as post {
        article {
            h2 "{post.title}"
            p "{post.excerpt}"
        }
    }
}
```

### load_json Directive

```tw
let products = load_json "products"

body {
    each products as product {
        ProductCard { props product }
    }
}
```

### Common Mistake: fetch in Static Build

```tw
// WRONG
page {
    render static
}

let data = fetch "https://api.example.com/data"
```

**Compiler Error:** `TW3007: 'fetch' directive requires 'render server' or 'render edge'.`

**Fix:** Change render mode.

```tw
// CORRECT
page {
    render server
}

let data = fetch "https://api.example.com/data"
```

## Reactivity

### on:click

```tw
let count = 0

body {
    p "Count: {count}"
    button "+" { on:click "count++" }
    button "-" { on:click "count--" }
    button "Reset" { on:click "count = 0" }
}
```

### bind:value

```tw
let search_query = ""

body {
    input {
        type "text"
        placeholder "Search..."
        bind:value "search_query"
    }
    p "Searching for: {search_query}"
}
```

### Common Mistake: bind on Non-Input

```tw
// WRONG
let text = ""

body {
    div {
        bind:value "text"
    }
}
```

**Compiler Error:** `TW3005: 'bind:value' can only be used on input, textarea, or select elements.`

**Fix:** Use `bind:` only on form elements.

```tw
// CORRECT
let text = ""

body {
    textarea {
        bind:value "text"
    }
}
```

## Complete Example: Todo List

```tw
page {
    title "Todo List"
    render static
}

let todos = [
    {id: 1, text: "Learn TW", done: false},
    {id: 2, text: "Build app", done: false}
]
let new_todo = ""

body {
    div {
        class "todo-app"
        h1 "Todo List"

        div {
            class "add-todo"
            input {
                type "text"
                placeholder "Add a task..."
                bind:value "new_todo"
            }
            button "Add" { on:click "addTodo()" }
        }

        ul {
            class "todo-list"
            each todos as todo {
                li {
                    class "todo-item"
                    if todo.done {
                        class "todo-item done"
                    }

                    input {
                        type "checkbox"
                        checked "{todo.done}"
                        on:change "toggleTodo({todo.id})"
                    }
                    span "{todo.text}"
                    button "Delete" {
                        on:click "deleteTodo({todo.id})"
                    }
                }
            }
        }

        p "Remaining: {todos.filter(t => !t.done).length}"
    }
}

script {
    function addTodo() {
        if (!new_todo.trim()) return;
        todos.push({id: Date.now(), text: new_todo, done: false});
        new_todo = "";
    }

    function toggleTodo(id) {
        const todo = todos.find(t => t.id === id);
        if (todo) todo.done = !todo.done;
    }

    function deleteTodo(id) {
        todos = todos.filter(t => t.id !== id);
    }
}
```

## Best Practices

1. Initialize variables with default values
2. Use descriptive names: `user_name` not `un`
3. Pre-process data — don't do complex logic in templates
4. Handle empty states — always provide fallback content
5. Avoid deep nesting — extract components when complex
6. Use reactive features sparingly — each reactive page adds ~2KB JS
