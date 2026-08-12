# Reactive Bindings

TW Framework provides reactive directives for interactivity without writing raw JavaScript.

## Event Bindings

Use `on:event` syntax:

```tw
button "Click me" {
    on:click "count++"
}

input {
    type "text"
    on:input "handleInput(event)"
}

form {
    on:submit "submitForm(event)"
}
```

### Available Events

`click`, `dblclick`, `change`, `input`, `submit`, `focus`, `blur`, `keydown`, `keyup`, `keypress`, `mouseover`, `mouseout`, `mouseenter`, `mouseleave`, `mousedown`, `mouseup`, `load`, `resize`, `scroll`, `contextmenu`

## Two-Way Binding

Use `bind:property` for two-way data binding:

```tw
let name = ""

input {
    type "text"
    bind:value "name"
    placeholder "Enter your name"
}

h1 "Hello {name}!"
```

### Bindable properties

| Directive | Binds to |
|---|---|
| `bind:value` | Input/select value |
| `bind:checked` | Checkbox/radio checked state |
| `bind:src` | Image source |

## State Management

Define reactive state:

```tw
let count = 0
let items = ["Apple", "Banana"]
let user = { name: "John", age: 30 }

body {
    button "Count: {count}" {
        on:click "count++"
    }
    input {
        type "text"
        bind:value "user.name"
    }
    p "Name: {user.name}"
}
```

## Reactive Runtime

TW ships a tiny (~2KB) reactive runtime only for pages that use `on:` or `bind:` directives. Static pages stay at 0KB JS.

The runtime:
- Listens for events on elements with `data-tw-*` attributes
- Updates the DOM when state changes
- Handles two-way binding automatically

## Conditional Classes

```tw
let isActive = true

button "Toggle" {
    on:click "isActive = !isActive"
    class "btn {isActive ? 'active' : 'inactive'}"
}
```

## Show/Hide

```tw
let visible = true

if visible {
    div "I'm visible!"
}
```
