# Page Block and Meta Tags

Complete reference for `page {}`, `head {}`, `seo {}`, and render modes in TW Framework.

## The Page Block

The `page` block is the first block in every `.tw` file. It defines page-level metadata.

### Required Properties

```tw
page {
    title "Page Title"
}
```

### Full Syntax

```tw
page {
    title "Page Title"
    layout "main"
    render static
    revalidate 3600
}
```

### Property Reference

| Property | Type | Required | Default | Description |
|----------|------|----------|---------|-------------|
| `title` | string | Yes | none | Page title (appears in `<title>`) |
| `layout` | string | No | none | Layout component to wrap page |
| `render` | string | No | static | Rendering mode: static, server, edge |
| `revalidate` | number | No | none | ISR revalidation interval (seconds) |

### Common Mistake: Missing Title

```tw
// WRONG
page {
    layout "main"
}
```

**Compiler Error:** `TW2001: 'page' block missing required property 'title'.`

**Fix:** Always provide a title.

```tw
// CORRECT
page {
    title "Home"
    layout "main"
}
```

### Common Mistake: Title After Other Properties

```tw
// WRONG — title must be first
page {
    layout "main"
    title "Home"
}
```

**Compiler Warning:** `TW2001: 'title' should be the first property in 'page' block.`

**Fix:** Put `title` first.

```tw
// CORRECT
page {
    title "Home"
    layout "main"
}
```

## Render Modes

### render static (Default)

```tw
page {
    title "About Us"
    render static
}
```

- HTML generated at **build time**
- Served as static files
- Fastest performance
- Zero JavaScript by default
- Best for: marketing pages, blogs, docs

### render server

```tw
page {
    title "Dashboard"
    render server
}
```

- HTML generated **on each request**
- Can access request headers, cookies
- Can fetch fresh data
- Slower than static but always up-to-date
- Best for: user dashboards, admin panels, personalized content

### render edge

```tw
page {
    title "Global Site"
    render edge
}
```

- HTML generated at **edge locations**
- Closest to user = lowest latency
- Limited runtime (no filesystem access)
- Best for: global sites, A/B testing, geo-targeting

### Common Mistake: Invalid Render Mode

```tw
// WRONG
page {
    title "Home"
    render dynamic
}
```

**Compiler Error:** `TW2001: Invalid render mode 'dynamic'. Valid modes: static, server, edge.`

**Fix:** Use valid render mode.

```tw
// CORRECT
page {
    title "Home"
    render server
}
```

## Layout Property

### Using Layouts

```tw
page {
    title "Home"
    layout "main"
}
```

This wraps the page content in `[home]/layouts/main.tw`.

### Layout File Structure

```tw
// [home]/layouts/main.tw
page {
    title "{title}"
    render static
}

load "@./style/global.tss"

head {
    seo { description "My site" }
}

body {
    Header {}
    main {
        slot {}
    }
    Footer {}
}
```

### Common Mistake: Layout Not Found

```tw
// WRONG
page {
    title "Home"
    layout "nonexistent"
}
```

**Compiler Error:** `TW2404: Layout 'nonexistent' not found. Searched in: [home]/layouts/.`

**Fix:** Ensure layout file exists.

```tw
// CORRECT
// File [home]/layouts/main.tw exists
page {
    title "Home"
    layout "main"
}
```

### Common Mistake: Circular Layout Reference

```tw
// WRONG — main.tw references itself
// [home]/layouts/main.tw
page {
    title "{title}"
    layout "main"
}
```

**Compiler Error:** `TW2404: Circular layout reference detected: main → main.`

**Fix:** Layouts should NOT specify a layout.

```tw
// CORRECT
// [home]/layouts/main.tw
page {
    title "{title}"
}

body {
    slot {}
}
```

## The Head Block

### Basic Head Block

```tw
head {
    link { rel "stylesheet" href "/style.css" }
    script { src "/app.js" }
}
```

### SEO Block

```tw
head {
    seo {
        description "Page description for search engines"
        keywords "web, framework, fast"
        author "John Doe"
        og_title "Social Media Title"
        og_description "Social media description"
        og_image "/assets/og-image.png"
        og_type "website"
        twitter_card "summary_large_image"
        twitter_site "@johndoe"
        robots "index, follow"
        canonical "https://example.com/page"
    }
}
```

### SEO Property Reference

| Property | Description | Example |
|----------|-------------|---------|
| `description` | Meta description | `"A fast web framework"` |
| `keywords` | Meta keywords | `"web, framework"` |
| `author` | Page author | `"John Doe"` |
| `og_title` | Open Graph title | `"My Page"` |
| `og_description` | Open Graph description | `"Description"` |
| `og_image` | Open Graph image | `"/og.png"` |
| `og_type` | Open Graph type | `"website"`, `"article"` |
| `twitter_card` | Twitter card type | `"summary"`, `"summary_large_image"` |
| `twitter_site` | Twitter handle | `"@site"` |
| `robots` | Robots directive | `"index, follow"` |
| `canonical` | Canonical URL | `"https://site.com/page"` |

### Common Mistake: SEO Outside Head

```tw
// WRONG
body {
    seo { description "My page" }
}
```

**Compiler Error:** `TW2003: 'seo' block can only appear inside 'head' block.`

**Fix:** Place `seo` inside `head`.

```tw
// CORRECT
head {
    seo { description "My page" }
}

body {
    h1 "Hello"
}
```

### Common Mistake: Head After Body

```tw
// WRONG
body {
    h1 "Hello"
}

head {
    seo { description "My page" }
}
```

**Compiler Error:** `TW2003: 'head' block must appear before 'body' block.`

**Fix:** Order: `page` → `import/load` → `head` → `body`.

```tw
// CORRECT
page {
    title "Home"
}

head {
    seo { description "My page" }
}

body {
    h1 "Hello"
}
```

## Script Loading in Head

### External Scripts

```tw
head {
    script { src "https://cdn.example.com/lib.js" }
    script { src "/assets/app.js" strategy "defer" }
}
```

### Inline Scripts

```tw
head {
    script {
        console.log('Page loaded');
    }
}
```

### Script Strategies

| Strategy | Description | Use Case |
|----------|-------------|----------|
| none (default) | Load immediately | Critical scripts |
| `defer` | Execute after HTML parse | App logic |
| `async` | Execute when ready | Analytics, ads |
| `lazyOnload` | Execute after page load | Non-critical |
| `afterInteractive` | Execute after hydration | Reactivity |
| `beforeInteractive` | Execute before hydration | Feature detection |

### Common Mistake: Wrong Strategy Value

```tw
// WRONG
head {
    script { src "/app.js" strategy "delayed" }
}
```

**Compiler Error:** `TW2003: Invalid script strategy 'delayed'. Valid: defer, async, lazyOnload, afterInteractive, beforeInteractive.`

**Fix:** Use valid strategy.

```tw
// CORRECT
head {
    script { src "/app.js" strategy "defer" }
}
```

## Stylesheet Loading

### External Stylesheets

```tw
head {
    link { rel "stylesheet" href "https://fonts.googleapis.com/css2?family=Inter" }
}
```

### Preconnect

```tw
head {
    link { rel "preconnect" href "https://fonts.googleapis.com" }
    link { rel "preconnect" href "https://fonts.gstatic.com" crossorigin "anonymous" }
}
```

### Favicon

```tw
head {
    link { rel "icon" type "image/png" href "/favicon.png" }
    link { rel "apple-touch-icon" href "/apple-touch-icon.png" }
}
```

## Revalidation (ISR)

### Static with Revalidation

```tw
page {
    title "Blog"
    render static
    revalidate 3600  // Rebuild every hour
}
```

### Common Mistake: Revalidate on Server Render

```tw
// WRONG
page {
    title "Dashboard"
    render server
    revalidate 3600
}
```

**Compiler Warning:** `TW2001: 'revalidate' has no effect with 'render server'. Use 'render static'.`

**Fix:** `revalidate` only works with `render static`.

```tw
// CORRECT
page {
    title "Blog"
    render static
    revalidate 3600
}
```

## Complete Example

```tw
page {
    title "Getting Started | TW Framework"
    layout "docs"
    render static
    revalidate 86400
}

load "@./style/docs.tss"

head {
    link { rel "preconnect" href "https://fonts.googleapis.com" }
    link { rel "stylesheet" href "https://fonts.googleapis.com/css2?family=Inter:wght@400;600&display=swap" }

    seo {
        description "Learn how to build fast websites with TW Framework."
        og_title "Getting Started with TW"
        og_image "/assets/docs-og.png"
        og_type "article"
        twitter_card "summary_large_image"
        canonical "https://tw.dev/docs/getting-started"
    }
}

body {
    h1 "Getting Started"
    p "Welcome to TW Framework..."
}
```

## Block Order Rules

The correct order in a `.tw` file is:

1. `page` block (optional but recommended)
2. `import` directives
3. `load` directives
4. `let` variable declarations
5. `head` block
6. `body` block
7. `script` blocks

```tw
// CORRECT ORDER
page {
    title "Home"
    layout "main"
    render static
}

import "Header"
import "Footer"

load "@./style/home.tss"

let greeting = "Hello"

head {
    seo { description "Home page" }
}

body {
    Header {}
    h1 "{greeting}"
    Footer {}
}
```

## Best Practices

1. Always include `title` in `page` block
2. Use `layout` for consistent page structure
3. Add `seo` block to every public page
4. Use `revalidate` for content that changes periodically
5. Load critical CSS in `head`, defer non-critical
6. Use `preconnect` for external domains
7. Keep `head` block before `body`
