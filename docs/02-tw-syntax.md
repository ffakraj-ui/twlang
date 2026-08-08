# TW File Syntax

A `.tw` file has up to four sections:

```tw
page {
    title "Page Title"
    layout "main"
    render static
}

load "@./style/site.tss"

head {
    seo { description "Page description" }
}

body {
    div { class "container", h1 "Hello" }
}
```

## Page Block Keys

| Key | Value | Description |
|---|---|---|
| `title` | string | Page title tag |
| `layout` | string | Layout name from `layouts/` |
| `render` | `static`/`server`/`edge` | Rendering mode |
| `revalidate` | number | Cache TTL in seconds |
| `redirect` | string | Redirect to URL |
| `rewrite` | string | Internal rewrite |
| `cache_by` | string | Cache key discriminator |
| `cache_size` | number | Max cache entries |

## Elements

```tw
tagname "text" { attribute "value", child "text" }
```

Void elements: `img`, `br`, `hr`, `meta`, `link`, `input`, `source`

## Variables and Interpolation

```tw
let name = "World"
let count = 5
h1 "Hello {name}!"           // → Hello World!
p "Count: {count}"           // → Count: 5
```

## Type Annotations (Type Safety)

TW supports optional type annotations on `let` variables and `state` block
entries, similar to TypeScript. The compiler validates the value against the
declared type at parse time and during semantic analysis.

### Supported Types

| Type | Matches |
|---|---|
| `string` | Text values like `"hello"` |
| `number` | Integers and floats like `5`, `3.14` |
| `boolean` | `true` / `false` |
| `array` | Lists like `["a", "b"]` |
| `object` | Key-value maps (JSON objects) |
| `null` | The `null` value |
| `any` | Any type — disables checking |

### Syntax

```tw
let count: number = 5
let name: string = "World"
let isActive: boolean = true
let items: array = ["Apple", "Banana"]
let price: number = 19.99
let data: any = "anything goes"
```

### Type Errors

If the value does not match the declared type, the compiler raises an error:

```tw
// ❌ Error: Type error: `count` is annotated as `number` but got `string`.
let count: number = "hello"

// ❌ Error: Type error: `isActive` is annotated as `boolean` but got `number`.
let isActive: boolean = 1
```

### State Block Types

Type annotations also work inside `state` blocks:

```tw
state {
    count: number = 0
    name: string = "hello"
    isActive: boolean = true
    items: array = ["a", "b"]
}
```

### Backward Compatibility

Type annotations are **optional**. Existing `.tw` files without annotations
continue to work unchanged:

```tw
// This is still valid — no type annotation needed
let count = 5
let name = "World"
```


## Lib Function Calls

Functions from loaded `.twm` lib files can be called directly in `let` statements. The function executes at **build time** and the result is baked into the page.

```tw
load @./lib/getApps.twm

let app = getApp("whatsapp")
let name: string = getApp("whatsapp").name
```

See [Lib Directory](21-lib-directory.md) for full documentation.

## Comments

```tw
// Line comment
/* Block comment */
```

## Script Blocks

```tw
script {
    console.log("Hello from TW");
}
```

## If/Else

```tw
if isLoggedIn {
    h1 "Welcome back"
} else {
    a "Login" { href "/login" }
}
```

## Each (loops)

```tw
each items as item {
    li "{item.name}"
}
```

## For loops

```tw
for item in items {
    li "{item.name}"
}
```
