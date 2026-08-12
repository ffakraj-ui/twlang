# React Usage Guide

TW Framework v0.9.30 adds React compatibility. You can use React alongside TW's native VDOM for islands of interactivity, while keeping Zero-JS for static pages.

## Installation

```bash
tw install react react-dom
```

This installs React, updates `package.json`, and adds it to `tw.config` `server.external_packages`.

## Creating a React Component

Create a `.twm` file with a `export client function`:

```javascript
// [home]/lib/counter-component.twm
import React, { useState } from "react"

export client function Counter() {
    const [count, setCount] = useState(0)
    return React.createElement("div", { className: "counter" },
        React.createElement("h2", null, "React Counter"),
        React.createElement("p", null, "Count: " + count),
        React.createElement("button", {
            onClick: () => setCount(count + 1)
        }, "Increment"),
        React.createElement("button", {
            onClick: () => setCount(count - 1)
        }, "Decrement")
    )
}
```

## Using React in a TW Page

```tw
import { Counter } from "@/lib/counter-component"

page {
    title "React Demo"
    render interactive
}

body {
    div { id "react-root" }
    script { on:load "__tw.react.mount('Counter', 'react-root')" }
}
```

## How It Works

1. TW detects React usage in your `.twm` files
2. React is bundled from `node_modules` into a client-side chunk
3. An import map is generated for ESM resolution
4. The React bootstrap JS is injected into the page
5. `__tw.react.mount()` mounts your component into a DOM element

## React Bootstrap API

TW provides a React bootstrap API on the client:

```javascript
// Register a component
__tw.react.register("MyComponent", MyComponent)

// Mount a component into a DOM element
__tw.react.mount("MyComponent", "root-id", { prop1: "value" })

// Unmount
__tw.react.unmount("root-id")
```

## CDN vs Bundled React

- **Development**: React loads from CDN (umd builds) for simplicity
- **Production**: TW bundles React from `node_modules` into optimized chunks

## Mixing React and TW VDOM

You can mix React components with TW's native VDOM on the same page:

```tw
import { ReactWidget } from "@/lib/react-widget"

page {
    title "Mixed Page"
    render interactive
}

state {
    twCount 0
}

body {
    // TW native VDOM component
    div { class "tw-section"
        h1 "TW Native Counter"
        p "Count: {twCount}"
        button { on:click "twCount++" } "Increment"
    }

    // React island
    div { id "react-widget" }
    script { on:load "__tw.react.mount('ReactWidget', 'react-widget')" }
}
```

## Important Notes

- React components are **client-side only** — they run in the browser
- React does NOT replace TW's native VDOM — it coexists
- Static pages without React remain Zero-JS (0 bytes of JavaScript)
- Use `render interactive` in your page block for pages with React
- React hooks (useState, useEffect, etc.) work normally

## See Also

- [NPM Packages Guide](npm-packages-guide.md)
- [Migration Guide](../MIGRATION_V0.8.1.md)
- [Security Features](../SECURITY.md)
