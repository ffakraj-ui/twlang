# TW Framework

A high-performance, HTML-first web framework with Virtual DOM, App Router, and Zero-JS static sites.

**v0.8.45** — NPM Package Manager, React Compatibility, esbuild Bundling, Security Module, Route Fixes

## Quick Start

```bash
pip install tw-framework
tw create my-site
cd my-site
tw build
```

That's it. Your static site is in `dist/` — deploy it anywhere.

> **Pre-release / development install:** `pip install tw-framework` from a clone of this repo.

## What's New in v0.8.45

### Route Path Fix (Critical)
- App Router route paths no longer double-nested (`/about/about` → `/about`)
- Fixed in `sitemap.xml`, `__TW_DATA__` JSON, HTML metadata comments, and RSS feed
- All three route generators (`route_path_from_page_info`, `route_from_static_page`, `route_from_dynamic_page`) now consistent

### NPM Package Manager (like Next.js)
Install, remove, and list npm packages directly from the TW CLI:
```bash
tw install react react-dom        # Install packages
tw install chart.js@4.0.0         # Install specific version
tw install --save-dev jest         # Save as devDependency
tw install --exact axios@1.6.0    # Save exact version (no ^)
tw add lodash                      # Alias for install
tw remove react                    # Remove a package
tw list                            # List installed packages
tw list --detailed                 # Show installed versions
```
Auto-detects npm, pnpm, yarn, and bun from lockfiles.

### React Compatibility
Use React alongside TW's native VDOM for islands of interactivity:
```bash
tw install react react-dom
```

```tw
import { Counter } from "@/lib/react-component"

page {
    title "React Demo"
    render interactive
}

body {
    div { id "react-root" }
    script { on:load "__tw.react.mount('Counter', 'react-root')" }
}
```
React bootstrap and loader scripts are automatically injected during build.

### esbuild Integration
Complex npm packages (like `dayjs`, `chart.js`) are bundled for the browser using esbuild, with an IIFE fallback when esbuild is not installed.

### Security Module
Built-in CSP nonce generation, secure HTTP headers, input sanitization, and CSRF protection.

### Enhanced Lib System
- NPM packages from node_modules are now properly resolved in .twm files
- Better error messages with install hints for missing packages
- Import maps generation for client-side ESM resolution

### Breaking Changes
- `tw.config` `server.external_packages` is automatically updated when using `tw install`
- Lib executor now resolves npm packages from project root node_modules
- See [MIGRATION_V0.8.1.md](MIGRATION_V0.8.1.md) for full migration guide

## What's New in v0.8.0 (Previous Release)

- **Virtual DOM** — TW-native VDOM with diff-and-patch algorithm (~3KB, no React dependency)
- **Lib System Overhaul** — `import { getData } from "@/lib/data"` syntax, async/await, type annotations, client-side functions
- **Server Actions** — `action {}` blocks, call server functions from client without API routes
- **ISR** — `revalidate 60` for background page regeneration
- **Metadata API** — Static and dynamic `metadata {}` / `generateMetadata {}` blocks
- **Suspense & Streaming** — Progressive page loading
- **Error Boundaries** — Runtime error catching via `error.tw`
- **Zero-JS Preserved** — Static pages still ship 0 bytes of JavaScript

## Routing (App Router)

```
[home]/
├── layout.tw          ← Root layout (TW component with `children`)
├── page.tw            ← Home page (/)
├── about/
│   └── page.tw        ← /about
├── blog/
│   ├── page.tw        ← /blog
│   └── [slug]/
│       └── page.tw    ← /blog/:slug (dynamic route)
├── (dashboard)/       ← Route group (doesn't appear in URL)
│   ├── layout.tw
│   └── stats/
│       └── page.tw    ← /stats
├── api/
│   └── route.tw       ← API route handler
├── not-found.tw       ← 404 page
└── error.tw           ← Error boundary
```

## Layouts

```tw
component layout {
    html {
        head {
            title "{children.title}"
        }
        body {
            nav { class "navbar"
                a { href "/" } "Home"
                a { href "/about" } "About"
            }
            main { class "container"
                children
            }
            footer "© 2026"
        }
    }
}
```

## Virtual DOM

VDOM is auto-detected. If your page uses `state`, events, or bindings, the VDOM runtime is injected automatically.

```tw
page {
    title "Counter"
    render interactive
}

state {
    count 0
    items []
}

body {
    button { on:click "count++" } "Increment"
    p { tw-text "count" } ""
    input { bind:value "name" }
    div { show:visible "count > 5" } "Count is high!"
}
```

Static pages remain Zero-JS — no runtime, no overhead.

## Lib System

```tw
import { getApps, getApp } from "@/lib/data"
import formatPrice from "@/lib/utils"

page {
    title "Apps"
    render static
}

let apps = getApps()

body {
    each apps as app {
        div { class "card"
            h1 "{app.name}"
            p "Price: {formatPrice(app.price)}"
        }
    }
}
```

### .twm files

```javascript
// Server-side (build-time execution)
export async function getApps() {
    const res = await fetch("https://api.example.com/apps");
    return res.json();
}

// Client-side (shipped to browser)
export client function formatPrice(n) {
    return "₹" + n.toFixed(2);
}

// Type annotations (stripped before execution)
export function getApp(slug: string): Promise<App> {
    return getApps().find(a => a.slug === slug);
}
```

## Server Actions

```tw
action createPost {
    method POST
    handler "createPost"
    require_auth true
}

body {
    button { on:click "__twAction('createPost', { title: 'Hello' })" } "Create"
}
```

## Icons

Built-in 60+ SVG icons, zero dependency:

```tw
Icon { name "home" }
Icon { name "search" size 20 }
Icon { name "menu" class "text-gray-500" }
```

## CLI

| Command | Description |
|---------|-------------|
| `tw create <name>` | Create new App Router project |
| `tw build` | Build site to `dist/` |
| `tw dev` | Start dev server |
| `tw info` | Show project info |
| `tw dead` | Find unused files |

## Zero-JS

Static pages ship **0 bytes of JavaScript**:

```tw
page {
    title "About"
    render static
}

body {
    h1 "About Us"
    p "We build amazing things."
}
```

## Deployment

Output is static HTML/CSS/JS in `dist/`. Deploy to any host:
- Vercel, Netlify, Cloudflare Pages
- GitHub Pages
- Any static file server

## License

MIT


## Components

**Auto-Discovery:** Components in `[home]/components/` are auto-discovered.
No `import` needed — just use `ComponentName {}` directly.

File: `[home]/components/Button.tw`
```tw
let label "Click"
let href "#"

a { class "btn", href "{href}" text "{label}" }
```

Usage (no import needed):
```tw
body {
    Button { href "/about", label "Get Started" }
}
```

`import "Button"` also works but is optional.

## Script Blocks

- Inline: `script { console.log("hello") }` — raw JS
- **{prop} interpolation in scripts** (v0.8.45+): `script { new Date("{target}") }`
- **External `script { src "@/lib/file.js" }`** — @/ resolved, file copied to `dist/_tw/scripts/` (v0.8.45+)
