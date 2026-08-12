# Routing and Navigation

Complete guide to file-based routing, dynamic routes, parameters, and navigation in TW Framework.

## File-Based Routing

TW Framework automatically creates routes from your file structure.

### Basic Routes

```
[home]/
  index.tw      →  /
  about.tw      →  /about
  contact.tw    →  /contact
```

### Nested Routes

```
[home]/
  blog/
    index.tw    →  /blog
    post.tw     →  /blog/post
```

### Common Mistake: Wrong File Extension

```
[home]/
  about.html    →  NOT a route (must be .tw)
  about.txt     →  NOT a route
```

**Fix:** Only `.tw` files become routes.

## Dynamic Routes

### Single Parameter

```
[home]/
  blog/
    [slug].tw   →  /blog/hello-world, /blog/my-post
```

```tw
// [home]/blog/[slug].tw
page {
    title "{post.title}"
    render static
}

body {
    article {
        h1 "{post.title}"
        div "{post.body}"
    }
}
```

### Multiple Parameters

```
[home]/
  shop/
    [category]/
      [product].tw  →  /shop/electronics/iphone-15
```

```tw
// [home]/shop/[category]/[product].tw
page {
    title "{product.name}"
    render static
}

body {
    h1 "{product.name}"
    p "Category: {category.name}"
}
```

### Common Mistake: Parameter Name Mismatch

```tw
// WRONG — Using wrong parameter name
// File: [home]/blog/[slug].tw

body {
    h1 "{post.title}"  // Should be {slug} or loaded data
}
```

**Fix:** The parameter name matches the filename: `[slug].tw` provides `slug` variable.

```tw
// CORRECT
// [home]/blog/[slug].tw
let post = load_json "posts/{slug}"

body {
    h1 "{post.title}"
}
```

## Catch-All Routes

```
[home]/
  docs/
    [...slug].tw  →  /docs/getting-started, /docs/api/rest
```

```tw
// [home]/docs/[...slug].tw
page {
    title "Documentation"
    render static
}

body {
    h1 "Docs: {slug.join(' / ')}"
}
```

### Common Mistake: Catch-All Not Last

```
[home]/
  docs/
    [...slug].tw
    api.tw          →  This will NEVER match — catch-all catches everything first
```

**Fix:** Place specific routes before catch-all, or use different structure.

```
[home]/
  docs/
    api.tw          →  /docs/api
    [...slug].tw    →  /docs/anything-else
```

## Data Files for Dynamic Routes

### JSON Data Files

```
[home]/
  blog/
    [slug].tw
    [slug].json     →  Data source for [slug].tw
```

```json
// [home]/blog/[slug].json
[
  {
    "slug": "hello-world",
    "title": "Hello World",
    "body": "Welcome to my blog!"
  },
  {
    "slug": "getting-started",
    "title": "Getting Started",
    "body": "Let's learn TW Framework..."
  }
]
```

```tw
// [home]/blog/[slug].tw
page {
    title "{post.title}"
    render static
}

body {
    article {
        h1 "{post.title}"
        div "{post.body}"
    }
}
```

### Common Mistake: JSON Structure Mismatch

```json
// WRONG — Single object instead of array
{
  "slug": "hello",
  "title": "Hello"
}
```

**Compiler Error:** `TW3008: Dynamic route data must be an array of objects.`

**Fix:** Use an array.

```json
// CORRECT
[
  {
    "slug": "hello",
    "title": "Hello"
  }
]
```

## Navigation

### Standard Links

```tw
nav {
    ul {
        li { a "Home" { href "/" } }
        li { a "About" { href "/about" } }
        li { a "Blog" { href "/blog" } }
        li { a "Contact" { href "/contact" } }
    }
}
```

### Client-Side Navigation (goto)

```tw
a "Dashboard" {
    href "/dashboard"
    goto "/dashboard"
}
```

The `goto` directive enables client-side navigation without full page reload.

### Common Mistake: goto Without href

```tw
// WRONG
a "Dashboard" {
    goto "/dashboard"
}
```

**Warning:** `TW3009: 'goto' should be accompanied by 'href' for accessibility.`

**Fix:** Always include `href`.

```tw
// CORRECT
a "Dashboard" {
    href "/dashboard"
    goto "/dashboard"
}
```

### External Links

```tw
a "GitHub" {
    href "https://github.com"
    target "_blank"
    rel "noopener noreferrer"
}
```

**Note:** Do NOT use `goto` for external links.

```tw
// WRONG
a "GitHub" {
    href "https://github.com"
    goto "https://github.com"  // goto is for internal navigation only
}
```

## Active Link Styling

```tw
let current_path = "/"

nav {
    ul {
        li {
            a "Home" {
                href "/"
                if current_path == "/" {
                    class "nav-link active"
                } else {
                    class "nav-link"
                }
            }
        }
    }
}
```

## Route Parameters in TWM

```twm
// [home]/api/users/[id]/route.twm
function get(request):
    user_id = request.args.get("id")

    if not user_id:
        return json_response({"error": "ID required"}, status=400)

    user = db.users.find_by_id(user_id)
    if not user:
        return json_response({"error": "Not found"}, status=404)

    return json_response(user)
```

## 404 Pages

```tw
// [home]/404.tw
page {
    title "Page Not Found"
    render static
}

body {
    div {
        class "error-page"
        h1 "404"
        p "The page you're looking for doesn't exist."
        a "Go Home" { href "/" }
    }
}
```

## Route Conflicts

### Conflict Resolution

More specific routes take precedence:

```
[home]/
  blog/
    index.tw      →  /blog (specific)
    [slug].tw     →  /blog/:slug (dynamic)
```

`/blog` matches `index.tw`, not `[slug].tw`.

### Common Mistake: Overlapping Routes

```
[home]/
  [slug].tw     →  /:slug
  about.tw      →  /about (NEVER reached — [slug] catches everything)
```

**Fix:** Restructure to avoid overlap.

```
[home]/
  about.tw      →  /about
  posts/
    [slug].tw   →  /posts/:slug
```

## Best Practices

1. Use kebab-case for route files: `about-us.tw` not `aboutUs.tw`
2. Keep routes shallow — max 3 levels deep
3. Use `index.tw` for directory roots
4. Always provide 404 page
5. Use `goto` for internal navigation
6. Include `href` with every `goto`
7. Validate route parameters in API handlers
