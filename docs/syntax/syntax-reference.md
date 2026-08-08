# Syntax Reference

## Pages

Every page starts with a `page { }` block:

```tw
page {
    title "My Page"
    layout "main"
    render static
}
```

- `render` — `static` (built once), `server` (rendered on each request), or `edge`
- `revalidate <seconds>` — for `render server` pages, re-render after this many seconds
- `layout "name"` — which layout in `[home]/layouts/` to use

## Elements

Elements are `tagname { property value ... }`:

```tw
a {
    href "/about"
    target "_blank"
    class "button"
    text "About us"
}
```

Multiple properties on **one line** are fully supported:

```tw
a { href "/" target "_blank" class "btn" text "Home" }
```

Shorthand for a text-only element:

```tw
h1 "Welcome"
p "Some text"
```

## Loading stylesheets and components

```tw
load "@../style/site.tss"
load @./components/Header.tw
```

`@./...` resolves relative to the `[home]` folder. `@../...` resolves relative to the current file's own folder — this matters most in `layouts/`, where `@./style/x.tss` is usually what you want (not `@../`).

## String interpolation

`{name}` inside a string is replaced with the value of `name` from the page's `let` variables or route params:

```tw
let heroTitle = "Build fast"

h1 "{heroTitle}"
```

Interpolation only works **inside quoted strings** — `{name}` written bare (not inside quotes) is not evaluated.

## Layouts

A layout is written as **raw HTML text** with placeholders, not as nested `.tw` element blocks:

```tw
<!DOCTYPE html>
<html>
<head>
<title>{title}</title>
{head}
{styles}
</head>
<body>
{slot}
{scripts}
</body>
</html>
```

`{slot}` is where the page's `BODY { }` content is injected. `{styles}` and `{scripts}` are injected automatically — don't call `load` for a stylesheet from inside the layout file itself; `load` the stylesheet from each page instead.

## Reactive state

```tw
let count = 0

BODY {
    p {
        text "Count: "
        span { tw-text "count" }
    }
    button {
        on:click "__tw.set('count', __tw.get('count') + 1)"
        text "Increment"
    }
}
```

- `on:click "<expr>"` — runs `<expr>` in the browser on click. Use `__tw.get('name')` / `__tw.set('name', value)` to read/write reactive state.
- `bind:value "name"` — two-way binds an `<input>` to a `let` variable.
- `tw-text "name"` — keeps an element's text in sync with a `let` variable, client-side.

`tw-text` / `on:` / `bind:` are **client-side only** — they don't have access to server-only values like dynamic-route params. For those, use plain `{param}` string interpolation instead (see below).

## Dynamic routes

A page file named with square brackets, e.g. `[home]/pages/blog/[slug].tw`, matches `/blog/<anything>`. It needs a sibling JSON file listing every value to pre-render — same name, with `.tw` replaced by `.json`:

`[home]/pages/blog/[slug].json`:
```json
[
  { "slug": "hello-world" },
  { "slug": "second-post" }
]
```

Route params are merged directly into the page's top-level context — access them as `{slug}`, not `{params.slug}`:

```tw
h1 "Slug: {slug}"
```

## API routes

`.twm` files under `[home]/api/` define server functions:

```tw
// [home]/api/contact/route.twm
fn post(request) {
    return {
        status: 200,
        json: { ok: true, received: request.body || {} }
    };
}
```

The incoming request body is already parsed — use `request.body`, not `request.json()`.

## Middleware

`middleware.tw` in the project root declares rules that run before matching requests:

```tw
use "protect-dashboard" {
    match "/dashboard"
    auth {
        cookie "session_token"
        required true
    }
    response {
        status 302
        header "Location" "/"
    }
}

use "api-rate-limit" {
    match "/api/ping"
    rate_limit {
        requests 60
        window 60
    }
    response {
        status 429
        json { error "Too many requests" }
    }
}

use "api-origin-check" {
    match "/api/ping"
    origin {
        allow ["http://localhost:3000"]
        require true
    }
    response {
        status 403
        json { error "Origin not allowed" }
    }
}
```

Note: for a key that can appear more than once with a list value (like `allow`), use array syntax `allow ["a", "b"]` on one line — repeating the key on separate lines overwrites rather than appends.

## Stylesheets (`.tss`)

```tss
.card {
    padding 16 24
    background #1e293b
    transition "transform 0.3s ease, background 0.3s ease"
}

.card:hover {
    transform "translateY(-6px)"
}

@keyframes pulse {
    0% { box-shadow "0 0 0 0 rgba(34,197,94,0.6)" }
    100% { box-shadow "0 0 0 12px rgba(34,197,94,0)" }
}
```

- Bare numeric values (`padding 16 24`) get `px` appended automatically.
- Multi-word values that need to stay together (`animation`, `transform`, `box-shadow`, etc.) should be quoted.

## Accessibility & data attributes

Hyphenated attribute names work as expected:

```tw
button {
    aria-label "Close dialog"
    data-testid "close-btn"
    text "X"
}
```
