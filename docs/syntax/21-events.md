# Event Types

## Available Events

### Mouse Events

| Event | Directive | Description |
|---|---|---|
| Click | `on:click` | Single click |
| Double click | `on:dblclick` | Double click |
| Mouse down | `on:mousedown` | Mouse button pressed |
| Mouse up | `on:mouseup` | Mouse button released |
| Mouse over | `on:mouseover` | Mouse enters element |
| Mouse out | `on:mouseout` | Mouse leaves element |
| Mouse enter | `on:mouseenter` | Mouse enters (no bubbling) |
| Mouse leave | `on:mouseleave` | Mouse leaves (no bubbling) |
| Context menu | `on:contextmenu` | Right-click |

### Keyboard Events

| Event | Directive | Description |
|---|---|---|
| Key down | `on:keydown` | Key pressed |
| Key up | `on:keyup` | Key released |
| Key press | `on:keypress` | Key pressed (deprecated but supported) |

### Form Events

| Event | Directive | Description |
|---|---|---|
| Submit | `on:submit` | Form submitted |
| Change | `on:change` | Input value changed |
| Input | `on:input` | Input value changing (live) |
| Focus | `on:focus` | Element gained focus |
| Blur | `on:blur` | Element lost focus |

### Window Events

| Event | Directive | Description |
|---|---|---|
| Load | `on:load` | Page loaded |
| Resize | `on:resize` | Window resized |
| Scroll | `on:scroll` | Page scrolled |

## Usage

```tw
button "Click me" {
    on:click "incrementCounter()"
}

input {
    type "text"
    on:input "updateValue(event)"
    on:focus "handleFocus()"
    on:blur "handleBlur()"
}

form {
    on:submit "handleSubmit(event)"
}

div {
    on:mouseover "showTooltip()"
    on:mouseout "hideTooltip()"
}
```

## Event Handler Syntax

Event handlers are JavaScript expressions:

```tw
// Simple expression
button "Add" { on:click "count++" }

// Function call
button "Save" { on:click "saveData()" }

// Inline function
button "Alert" { on:click "alert('Hello!')" }

// Multiple statements
button "Submit" { on:click "validate(); submit()" }
```

## Two-Way Binding

`bind:value` is shorthand for `on:input` + value sync:

```tw
// These are equivalent:
input { bind:value "name" }
input { on:input "name = event.target.value" }
```
