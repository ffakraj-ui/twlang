# Text Interpolation

## Basic Syntax

Use `{variable}` to insert variable values into text:

```tw
let name = "World"
let count = 42

h1 "Hello {name}!"           // → Hello World!
p "You have {count} items"   // → You have 42 items
```

## Object Property Access

```tw
let user = { name: "John", age: 30 }

h1 "Name: {user.name}"       // → Name: John
p "Age: {user.age}"          // → Age: 30
```

## Nested Access

```tw
let product = { category: { name: "Electronics" } }

p "Category: {product.category.name}"  // → Category: Electronics
```

## Array Access

```tw
let colors = ["red", "green", "blue"]

p "First: {colors[0]}"       // → First: red
p "Second: {colors[1]}"      // → Second: green
```

## Expressions

```tw
let price = 100
let quantity = 3

p "Total: {price * quantity}"     // → Total: 300
p "Tax: {price * 0.18}"           // → Tax: 18
p "Final: {price + (price * 0.18)}"  // → Final: 118
```

## String Concatenation

```tw
let firstName = "John"
let lastName = "Doe"

h1 "{firstName} {lastName}"   // → John Doe
```

## Ternary Operator

```tw
let count = 5
let isLoggedIn = true

p "Status: {isLoggedIn ? 'Online' : 'Offline'}"   // → Status: Online
p "Items: {count > 0 ? count : 'None'}"           // → Items: 5
```

## Escaping Braces

To include literal `{` or `}` in text:

```tw
p "Use \{braces\} for objects"    // → Use {braces} for objects
p "JSON: \{key: value\}"         // → JSON: {key: value}
```

## In Attributes

Interpolation works in attribute values:

```tw
let userId = 123
let theme = "dark"

div {
    class "user-card theme-{theme}"
    data-user-id "{userId}"
}
```

## Limitations

- Interpolation is for display only — it doesn't execute arbitrary JavaScript
- Complex expressions (function calls, loops) should be in `script {}` blocks
- Interpolated values are HTML-escaped automatically to prevent XSS

## HTML Escaping

Interpolated values are automatically HTML-escaped:

```tw
let userInput = "<script>alert('xss')</script>"
p "{userInput}"
// Output: <script>alert('xss')</script>
```

This prevents XSS attacks from user-provided data.
