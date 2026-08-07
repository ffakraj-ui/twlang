# SEO and Meta Tags

TW Framework has built-in SEO support — no plugins needed.

## SEO Block

```tw
head {
    seo {
        description "Page description for search engines"
        og_title "Open Graph Title"
        og_description "Open Graph description"
    }
}
```

## Meta Tags

```tw
head {
    meta { name "description" content "My page description" }
    meta { name "keywords" content "tw, framework, web" }
    meta { name "author" content "Your Name" }
    meta { name "robots" content "index, follow" }
}
```

## Open Graph (Facebook)

```tw
head {
    meta { property "og:title" content "My Page" }
    meta { property "og:description" content "Page description" }
    meta { property "og:image" content "https://example.com/image.jpg" }
    meta { property "og:url" content "https://example.com/page" }
    meta { property "og:type" content "website" }
}
```

## Twitter Cards

```tw
head {
    meta { name "twitter:card" content "summary_large_image" }
    meta { name "twitter:title" content "My Page" }
    meta { name "twitter:description" content "Page description" }
    meta { name "twitter:image" content "https://example.com/image.jpg" }
}
```

## Viewport

```tw
head {
    meta { name "viewport" content "width=device-width, initial-scale=1" }
}
```

## Canonical URL

```tw
head {
    link { rel "canonical" href "https://example.com/page" }
}
```

## Favicon

```tw
head {
    link { rel "icon" href "/favicon.ico" }
    link { rel "apple-touch-icon" href "/apple-touch-icon.png" }
}
```

## Sitemap

TW automatically generates a sitemap at `/sitemap.xml` during build. All static pages are included.

## Robots.txt

Create `[home]/robots.txt`:

```
User-agent: *
Allow: /
Disallow: /admin/
Sitemap: https://example.com/sitemap.xml
```

## Page Title

Set in the `page` block:

```tw
page {
    title "My Page Title — My Site"
}
```

This becomes `<title>My Page Title — My Site</title>` in the HTML.
