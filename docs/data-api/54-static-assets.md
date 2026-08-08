# Static Assets

## Asset Directory

Place static files in `[home]/static/`:

```
[home]/
├── static/
│   ├── favicon.ico
│   ├── robots.txt
│   ├── manifest.json
│   ├── images/
│   │   ├── logo.png
│   │   └── hero.jpg
│   ├── fonts/
│   │   ├── inter.woff2
│   │   └── mono.woff2
│   └── js/
│       └── analytics.js
```

## Referencing Assets

In `.tw` files, reference assets with absolute paths:

```tw
img { src "/images/logo.png", alt "Logo" }
link { rel "icon", href "/favicon.ico" }
link { rel "manifest", href "/manifest.json" }
```

## Robots.txt

Create `[home]/robots.txt`:

```
User-agent: *
Allow: /
Disallow: /admin/
Disallow: /api/
Sitemap: https://example.com/sitemap.xml
```

## Favicon

```tw
head {
    link { rel "icon", href "/favicon.ico" }
    link { rel "apple-touch-icon", href "/images/apple-touch-icon.png" }
    link { rel "icon", type "image/png", href "/images/icon-32.png", sizes "32x32" }
}
```

## Fonts

```css
@font-face {
    font-family 'Inter'
    src url('/fonts/inter-regular.woff2') format('woff2')
    font-weight 400
    font-display swap
}

body {
    font-family 'Inter', sans-serif
}
```

Images in `[home]/static/images/` are copied to `dist/images/` during build. They are NOT processed or optimized - use pre-compressed images (WebP, AVIF).
