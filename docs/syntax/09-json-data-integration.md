# JSON Data Integration

Complete guide to using JSON data files with TW Framework pages.

## How JSON Data Works

TW Framework automatically pairs `.tw` files with `.json` files of the same name for dynamic route data.

### File Pairing

```
[home]/
  blog/
    [slug].tw      -> Template
    [slug].json    -> Data source
```

## JSON Structure Rules

### Dynamic Routes: Array of Objects

For `[slug].tw`, the JSON must be an **array of objects**. Each object needs a `slug` field matching the route parameter.

```json
// [home]/blog/[slug].json
[
  {
    "slug": "hello-world",
    "title": "Hello World",
    "date": "2024-01-15",
    "body": "Welcome to my blog!"
  },
  {
    "slug": "getting-started",
    "title": "Getting Started with TW",
    "date": "2024-01-20",
    "body": "Let's build something amazing..."
  }
]
```

### Common Mistake: Single Object Instead of Array

```json
// WRONG
{
  "slug": "hello",
  "title": "Hello"
}
```

**Compiler Error:** `TW3008: Dynamic route data must be an array of objects.`

**Fix:** Wrap in an array.

```json
// CORRECT
[
  {
    "slug": "hello",
    "title": "Hello"
  }
]
```

### Common Mistake: Missing Slug Field

```json
// WRONG
[
  {
    "title": "Hello World",
    "body": "Content"
  }
]
```

**Compiler Error:** `TW3008: Object at index 0 missing required 'slug' field.`

**Fix:** Add `slug` field.

```json
// CORRECT
[
  {
    "slug": "hello-world",
    "title": "Hello World",
    "body": "Content"
  }
]
```

### Common Mistake: Invalid Slug Characters

```json
// WRONG
[
  {
    "slug": "hello world!",
    "title": "Hello World"
  }
]
```

**Warning:** `TW3008: Slug 'hello world!' has invalid characters. Use lowercase, numbers, hyphens.`

**Fix:** Use URL-safe slugs.

```json
// CORRECT
[
  {
    "slug": "hello-world",
    "title": "Hello World"
  }
]
```

## Data Types in JSON

### Supported Types

```json
[
  {
    "slug": "demo",
    "string_field": "Hello",
    "number_field": 42,
    "boolean_field": true,
    "null_field": null,
    "array_field": ["a", "b", "c"],
    "object_field": {
      "nested": "value",
      "count": 10
    }
  }
]
```

### Using in Templates

```tw
// [home]/blog/[slug].tw
page {
    title "{post.title}"
    render static
}

body {
    article {
        h1 "{post.title}"
        time "{post.date}"
        div {
            class "content"
            "{post.body}"
        }

        if post.tags {
            div {
                class "tags"
                each post.tags as tag {
                    span { class "tag" "{tag}" }
                }
            }
        }

        if post.author {
            p "By {post.author.name}"
        }
    }
}
```

### Common Mistake: Wrong Property Access

```tw
// WRONG
body {
    p "{author.name}"  // Should be post.author.name
}
```

**Fix:** Access through data variable.

```tw
// CORRECT
body {
    p "{post.author.name}"
}
```

## Static Pages with JSON

### Non-Dynamic JSON Loading

```tw
// [home]/products.tw
page {
    title "Products"
    render static
}

let products = load_json "products"

body {
    each products as product {
        ProductCard { props product }
    }
}
```

```json
// [home]/products.json
[
  {"name": "Widget", "price": 19.99},
  {"name": "Gadget", "price": 29.99}
]
```

### Common Mistake: Wrong load_json Path

```tw
// WRONG
let products = load_json "[home]/products.json"
```

**Compiler Error:** `TW3007: Invalid path for load_json. Use relative path without extension.`

**Fix:** Use relative path without `.json`.

```tw
// CORRECT
let products = load_json "products"
```

## JSON Validation

### Common Mistake: Trailing Commas

```json
// WRONG
[
  {
    "slug": "hello",
    "title": "Hello",
  }
]
```

**Compiler Error:** `TW3008: Invalid JSON: Parse error on line 4.`

**Fix:** Remove trailing comma.

```json
// CORRECT
[
  {
    "slug": "hello",
    "title": "Hello"
  }
]
```

### Common Mistake: Comments in JSON

```json
// WRONG
[
  {
    // This is a post
    "slug": "hello",
    "title": "Hello"
  }
]
```

**Compiler Error:** `TW3008: Invalid JSON: Comments not allowed.`

**Fix:** Remove comments.

```json
// CORRECT
[
  {
    "slug": "hello",
    "title": "Hello"
  }
]
```

## Large JSON Files

### Performance Considerations

```json
// WRONG - Too many items slow build
[
  // ... 10,000 items
]
```

**Fix:** Paginate or split into multiple files.

```
[home]/
  blog/
    page-1.json     // Items 1-100
    page-2.json     // Items 101-200
```

### Using External JSON

```tw
// For large datasets, use API
page {
    title "Products"
    render server
}

let products = fetch "https://api.example.com/products?page=1"

body {
    each products as product {
        ProductCard { props product }
    }
}
```

## JSON Data with Multiple Parameters

```
[home]/
  shop/
    [category]/
      [product].tw
      [product].json
```

```json
// [home]/shop/[category]/[product].json
[
  {
    "category": "electronics",
    "product": "iphone-15",
    "name": "iPhone 15",
    "price": 999
  },
  {
    "category": "electronics",
    "product": "macbook-pro",
    "name": "MacBook Pro",
    "price": 1999
  }
]
```

```tw
// [home]/shop/[category]/[product].tw
page {
    title "{item.name}"
    render static
}

body {
    h1 "{item.name}"
    p "Category: {item.category}"
    p "Price: ${item.price}"
}
```

## Best Practices

1. Always use arrays for dynamic route data
2. Include matching route parameter as first field
3. Use URL-safe slugs (lowercase, hyphens)
4. Remove trailing commas
5. No comments in JSON files
6. Keep files under 1000 items
7. Use `load_json` without `.json` extension
8. Validate JSON with `tw check`
9. Use consistent field naming (camelCase)
10. Handle missing fields with `if` in templates
