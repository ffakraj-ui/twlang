# Public Folder Guide

## Overview

The `public/` folder is for static files that should be served as-is — no compilation, no processing. Files placed here are copied directly to `dist/` during build.

## What Goes in public/

- `robots.txt` — custom robots file
- `sitemap.xml` — custom sitemap
- `sitemap.xsl` — custom sitemap stylesheet
- `rss.xml` — custom RSS feed
- `favicon.ico` — site favicon
- Static HTML files
- CSS files (plain `.css`, not `.tss`)
- JavaScript files (plain `.js`)
- Images, fonts, PDFs, downloads
- Any file that should be accessible via URL

## What Does NOT Belong in public/

- `.tw` files — use `[home]/` for pages
- `.tss` files — use `[home]/` for styles
- `.twm` files — use `[home]/api/` for API routes
- Component files — use `[home]/components/`

TW will not process `.tw`, `.tss`, or `.twm` files in `public/`. They will be ignored.

## How It Works

```
public/
  robots.txt       → dist/robots.txt
  favicon.ico      → dist/favicon.ico
  example/
    index.html     → dist/example/index.html
  css/
    custom.css     → dist/css/custom.css
```

Files in `public/` are copied to `dist/` preserving their path structure. A file at `public/example/index.html` will be accessible at `/example/index.html` in the browser.

## HTML Files in public/

You can place standalone HTML files in `public/`:

```
public/
  landing.html     → accessible at /landing.html
  promo/
    index.html     → accessible at /promo/index.html
```

These are served as-is without any TW processing. Use this for legacy pages, third-party HTML, or standalone landing pages.

## CSS and JS in public/

Plain `.css` and `.js` files in `public/` are served as-is:

```
public/
  css/
    bootstrap.min.css    → /css/bootstrap.min.css
  js/
    analytics.js         → /js/analytics.js
```

## Images in public/

```
public/
  img/
    logo.png              → /img/logo.png
    og-image.jpg          → /img/og-image.jpg
```

## Priority Over Auto-Generated Files

Files in `public/` take priority over auto-generated files:

| File | Auto-generated | public/ override |
|------|---------------|-------------------|
| `sitemap.xml` | When `sitemap: true` | `public/sitemap.xml` wins |
| `robots.txt` | When `robots: true` | `public/robots.txt` wins |
| `rss.xml` | When `rss: true` | `public/rss.xml` wins |
| `sitemap.xsl` | When sitemap auto-generated | `public/sitemap.xsl` wins |

## Best Practices

1. Use `public/` for files that should be served exactly as-is
2. Use `[home]/` for TW pages, components, and styles
3. Use `[home]/assets/` for images referenced in `.tw` files
4. Use `public/` for standalone static files like favicons, downloads, etc.
