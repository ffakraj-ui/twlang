# Documentation Site Template

Build a docs site using TW Framework.

## Structure

```
docs-site/
├── [home]/
│   ├── pages/
│   │   ├── index.tw              → /
│   │   ├── docs/
│   │   │   ├── index.tw          → /docs
│   │   │   ├── getting-started.tw → /docs/getting-started
│   │   │   └── [slug].tw         → /docs/:slug
│   │   └── search.tw              → /search
│   ├── components/
│   │   ├── Sidebar.tw
│   │   ├── CodeBlock.tw
│   │   └── SearchBox.tw
│   └── layouts/
│       └── docs.tw
```

## Docs Layout

```tw
// [home]/layouts/docs.tw
html {
    head { meta { name "viewport", content "width=device-width" } }
    body {
        div {
            class "docs-layout"
            aside {
                class "sidebar"
                SearchBox {}
                nav {
                    a "Getting Started" { href "/docs/getting-started" }
                    a "Syntax" { href "/docs/syntax" }
                    a "CLI" { href "/docs/cli" }
                }
            }
            main {
                class "content"
                {children}
            }
        }
    }
}
```

## Search Component

```tw
// [home]/components/SearchBox.tw
div {
    class "search-box"
    input {
        type "text"
        placeholder "Search docs..."
        on:input "searchDocs(event)"
        id "search-input"
    }
    div { id "search-results", class "search-results" }
}
```

## Code Block Component

```tw
// [home]/components/CodeBlock.tw
pre {
    class "code-block"
    code "{code}"
}
```
