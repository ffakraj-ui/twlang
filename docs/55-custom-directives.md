# Custom Directives

TW Framework supports custom attributes and directives beyond the built-in ones.

## Data Attributes

```tw
div {
    class "card"
    data-id "123"
    data-category "product"
    data-price "2999"
    data-toggle "modal"
}
```

## Custom Event Patterns

```tw
input {
    on:input "debounceSearch(this.value)"
    type "search"
    placeholder "Search..."
}
```

## Conditional Rendering Directives

```tw
let isVisible = false
let role = "admin"

if isVisible {
    div "Visible content"
}

if role == "admin" {
    button "Delete" { on:click "deleteItem()" }
}
```

## Dynamic Class Binding

```tw
let isActive = true
let theme = "dark"

button "Toggle" {
    class "btn {isActive ? 'btn-active' : ''} theme-{theme}"
    on:click "isActive = !isActive"
}
```

## Attribute Interpolation

```tw
let userId = 42
let avatarUrl = "/images/user42.webp"

img {
    src "{avatarUrl}"
    alt "User avatar"
    data-user-id "{userId}"
}
```

## show: Directives

TW supports show: directives for conditional visibility:

```tw
let loading = true

div {
    class "spinner"
    show:if loading
}

p "Content loaded!" { show:if !loading }
```
