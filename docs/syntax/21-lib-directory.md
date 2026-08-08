# Lib Directory — Build-Time Functions

TW Framework supports a `lib/` directory for shared server-side utility
functions, similar to Next.js `@/lib`. These functions execute at **build
time** via Node.js, and their return values are baked directly into the
static HTML output.

## Directory Structure

```
[home]/
├── lib/                ← Shared utility functions (.twm files)
│   ├── getApps.twm
│   ├── sanitize.twm
│   └── format.twm
├── pages/
├── components/
└── api/
```

## Creating a Lib Function

Lib functions use the same `.twm` syntax as API routes — `fn` declarations:

```twm
// lib/getApps.twm
fn getApp(slug) {
  return {
    name: "WhatsApp",
    slug: slug,
    version: "2.23.10",
    size: "45MB",
    developer: "Meta"
  }
}

fn getAllApps() {
  return [
    { name: "WhatsApp", slug: "whatsapp" },
    { name: "Telegram", slug: "telegram" }
  ]
}
```

## Using Lib Functions in Pages

### Basic Usage

```tw
page {
    title "Download - {app.name}"
    render static
}

load @./lib/getApps.twm

let slug = "whatsapp"
let app = getApp("whatsapp")

body {
    h1 "{app.name}"
    p "Version: {app.version}"
    p "Size: {app.size}"
    button "Download Now" {
        on:click "startDownload('{app.slug}')"
    }
}
```

### With Type Safety

Combine with type annotations for compile-time validation:

```tw
page {
    title "App List"
    render static
}

load @./lib/getApps.twm

let app: object = getApp("whatsapp")
let allApps: array = getAllApps()

body {
    h1 "{app.name}"
    each allApps as item {
        li "{item.name}"
    }
}
```

If a function returns the wrong type, the compiler raises an error:

```
Type error: `app` is annotated as `string` but got `object`.
```

### Multiple Lib Files

You can load multiple lib files in a single page:

```tw
page {
    title "Dashboard"
    render static
}

load @./lib/getApps.twm
load @./lib/sanitize.twm
load @./lib/format.twm

let rawApp = getApp("whatsapp")
let cleanApp = sanitizeApp(rawApp)
let formatted = formatName(cleanApp.name)

body {
    h1 "{formatted}"
}
```

## How It Works

```
.tw file (let app = getApp("whatsapp"))
       |
       v
+----------------------------------+
|  TW Compiler (Python)            |
|  1. load @./lib/getApps.twm      |
|  2. Parse function names         |
|  3. let app = getApp("whatsapp") |
|     -> detect function call      |
|  4. Compile .twm -> .cjs         |
|  5. Execute via Node.js          |
|  6. Inject result into let_vars  |
+----------------------------------+
       |
       v
+----------------------------------+
|  Build Time Output (HTML)        |
|  <h1>WhatsApp</h1>              |
|  <p>Version: 2.23.10</p>        |
|  Data baked into static HTML    |
+----------------------------------+
```

### Execution Flow

1. `load @./lib/getApps.twm` — the compiler reads and registers the lib file
2. `let app = getApp("whatsapp")` — the compiler detects a function call
3. The `.twm` file is compiled to CommonJS (`.cjs`)
4. A Node.js bridge executes the function with the provided arguments
5. The return value (JSON) is injected into the page's `let_vars`
6. The value is available for interpolation in the page body
7. Type checking validates the return value if a type annotation is present

## Client/Server Separation

Lib functions run at **build time on the server**. Secrets, API keys, and
sensitive data stay server-side. Only the sanitized result is baked into
the HTML that reaches the browser.

```
Server (Build Time)              ->    Browser (Client)
--------------------------------------------------------
lib/getApps.twm                       <h1>WhatsApp</h1>
  fn getApp(slug) {                   <p>Version: 2.23.10</p>
    // API keys here are SAFE         <- No API keys in HTML
    // They never reach the browser
  }
```

## Error Handling

### Function Not Found

If a function is called that was not loaded via `load`, it is treated as
a string literal (backward compatible):

```tw
// No `load` for unknownFunc — treated as string "unknownFunc(test)"
let x = unknownFunc("test")
```

### Function Execution Error

If a loaded function raises an error during execution:

```
Error: Lib function `getApp` failed: TypeError: Cannot read property 'name' of undefined
```

## Requirements

- **Node.js v18+** must be installed and available on PATH
- Lib files must use `.twm` extension
- Only `fn` declarations are supported (no top-level execution)

## Comparison with Next.js

| Feature | Next.js `@/lib` | TW `lib/` |
|---|---|---|
| Language | JavaScript/TypeScript | `.twm` (TW's JS-like syntax) |
| Execution | Server runtime | Build time via Node.js bridge |
| Import syntax | `import { fn } from '@/lib/file'` | `load @./lib/file.twm` |
| Usage | `const x = fn(args)` | `let x = fn(args)` |
| Type safety | TypeScript | TW type annotations |
| Output | Runtime fetch | Baked into static HTML |
