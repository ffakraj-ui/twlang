# State Management

TW Framework provides simple reactive state management.

## Defining State

Use `let` at the top of a `.tw` file:

```tw
let count = 0
let name = "World"
let items = ["Apple", "Banana", "Cherry"]
let user = { name: "John", age: 30 }
let isVisible = true
```

## Reactive State

State becomes reactive when used with `on:` or `bind:` directives:

```tw
let count = 0

body {
    button "Count: {count}" {
        on:click "count++"
    }
    p "You clicked {count} times"
}
```

When `count` changes, all references to `{count}` update automatically.

## Two-Way Binding

```tw
let name = ""

input {
    type "text"
    bind:value "name"
    placeholder "Enter name"
}

h1 "Hello {name}!"
```

Typing in the input updates `{name}` everywhere on the page.

## State Block

For more complex state, use a `state` block:

```tw
state {
    count 0
    name "World"
    items ["Apple", "Banana"]
    user { name "John", age 30 }
    isVisible true
}
```

## Complex State

```tw
let cart = {
    items: [],
    total: 0
}

body {
    each cart.items as item {
        div {
            p "{item.name} — ${item.price}"
        }
    }
    p "Total: ${cart.total}"

    button "Add Item" {
        on:click "cart.items.push({name: 'New', price: 10}); cart.total += 10"
    }
}
```

## State in Components

Components have their own state:

```tw
// Counter.tw
let count = 0

div {
    class "counter"
    button "−" { on:click "count--" }
    span "{count}"
    button "+" { on:click "count++" }
}
```

Each instance of `<Counter>` has independent state.

## State Persistence

State is per-page — it resets on navigation. For persistent state, use localStorage:

```tw
script {
    // Save state
    function saveState(key, value) {
        localStorage.setItem(key, JSON.stringify(value));
    }

    // Load state
    function loadState(key, defaultValue) {
        const stored = localStorage.getItem(key);
        return stored ? JSON.parse(stored) : defaultValue;
    }
}
```
