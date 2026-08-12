# TW Grammar

TW files define page metadata, directives, state, head, and body blocks.

## Top level

```text
file        := page_block? layout_stmt* load_stmt* lifecycle_stmt* script_module_block* let_stmt* head_block? state_block? body_block
page_block  := "page" "{" page_field* "}"
head_block  := "head" "{" head_stmt* "}"
state_block := "state" "{" state_entry* "}"
body_block  := "BODY" "{" node* "}"
script_module_block := "SCRIPT" "{" twm_source "}"
lifecycle_stmt := "on" "load" "init" identifier
```

Top-level directives are intentionally lightweight. They are scanned before the full page body is compiled, so they affect dependency tracking, stylesheet inclusion, and layout resolution.

## Page fields

```text
page_field := "title" string
           | "layout" string_or_word
           | "render" ("static" | "server" | "edge")
           | "revalidate" number
           | "cache_by" string_or_word
           | "cache_size" number
           | "redirect" string
           | "rewrite" string
```

`layout` also supports chaining with `>` in legacy-compatible source, for example `layout "outer > inner"`.
`cache_by` is an opt-in cache key selector for SSR/edge pages, for example `cache_by cookie:session_id`.

## Directives

```text
import_stmt := "import" string
load_stmt   := "load" string
            | "load" at_path
at_path     := "@" path_token
lifecycle_stmt := "on" "load" "init" identifier
```

- `import "Header"` declares a component dependency and makes `Header {}` usable in the page/component body.
- `import "ui/Button"` supports nested component folders under `[home]/components/`.
- `load "foo.tss"` current file ke same folder se resolve hota hai.
- `load @./styles/foo.tss` `[home]` se resolve hota hai.
- `load "@../components/CTA"` can point directly to a component file path; the `.tw` extension is optional when the target is unambiguous.
- `load` may appear in pages, components, and layouts.
- `load` resolves paths with these aliases:
  - `@file` means "resolve from the project root"
  - `@./file` means "resolve from `[home]`"
  - `@../file` means "go up from the current file folder, then resolve normally"
- `.tss` files loaded through `load` are merged into rendered output.
- `.json` files loaded through `load` are tracked as dependencies and may feed page data workflows.
- `.tw` files loaded through `load` are treated as component dependencies and improve path clarity in diagnostics.
- `.twm` files loaded through `load` are compiled into a page JS bundle and registered into the TW module registry. No functions auto-run.
- `on load init <name>` registers an explicit client-side lifecycle call (similar to React's `useEffect(..., [])`), implemented as `window.__twInvoke("<name>")` after DOMContentLoaded.

Example:

```tw
load "@../components/CTA"

BODY {
  CTA {}
}
```

## Nodes

```text
node := element
     | component
     | let_stmt
     | if_block
     | for_block
     | each_block
     | script_block
```

## Elements

```text
element := tag string? "{" element_item* "}"
element_item := attr_stmt | style_stmt | event_stmt | router_stmt | text_stmt | node
text_stmt := "text" value
```

## Components

```text
component := ComponentName string? "{" component_item* "}"
component_item := prop_stmt | node
```

Component names must not contain null bytes, `..`, or absolute paths. Path-like imports are always resolved relative to `[home]/components/`.

## Control flow

```text
if_block   := "if" expression "{" node* "}" ("else" "{" node* "}")?
for_block  := "for" identifier "in" expression "{" node* "}"
each_block := "each" expression "as" identifier "{" node* "}"
let_stmt   := "let" identifier "="? value
```

## Notes

- Component names start with a capital letter.
- HTML-like `<div>` syntax is not supported. Use `div { ... }`.
- Expressions use the `{expr}` form for interpolation.
- Events may be written as either `click handlerName` or `onclick handlerName`. Both compile to `onclick="..."`
- `script { src "..."; strategy afterInteractive|beforeInteractive|lazyOnload }` injects an external script with an explicit loading strategy (Next.js `<Script>`-like). Raw JS `script { ... }` blocks are disabled by default and require `allow_raw_script: true` in `tw.config`.
- Dynamic routes are filename-based:
  - `[id].tw` for a single segment
  - `[...slug].tw` for catch-all segments
  - `[[...slug]].tw` for optional catch-all segments
- Dynamic route data comes from a sibling `.json` file, for example `[id].json`.
