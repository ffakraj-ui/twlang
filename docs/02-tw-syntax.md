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
