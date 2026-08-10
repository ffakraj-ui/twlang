# Sitemap, Robots.txt & RSS Guide

## Overview

TW Framework generates `sitemap.xml`, `robots.txt`, and `rss.xml` automatically — but only when you explicitly enable them in `tw.config`. This prevents unwanted files from appearing in your build output.

## Configuration

Add these options to your `tw.config`:

```
name: My Site
site_url: https://example.com
sitemap: true
robots: true
rss: true
```

All three default to `false` (OFF). You must set them to `true` to enable auto-generation.

### Options

| Option | Default | Description |
|--------|---------|-------------|
| `sitemap` | `false` | Auto-generate `sitemap.xml` with all route URLs |
| `robots` | `false` | Auto-generate `robots.txt` with Allow: / and sitemap link |
| `rss` | `false` | Auto-generate `rss.xml` feed with all page titles |
| `site_url` | (empty) | Required for sitemap and RSS — URLs are prefixed with this |

## Priority: Developer File > Auto-Generated

If you provide your own custom file, TW will **NOT overwrite it**. TW checks these locations (in order):

1. `[home]/public/` directory
2. Project root `/public/` directory
3. Project root directly

If a custom file is found in any of these locations, it is copied to `dist/` as-is. Auto-generation only happens when no custom file exists.

### Example: Custom robots.txt

Create `public/robots.txt`:
```
User-agent: GoogleBot
Disallow: /admin
Allow: /

Sitemap: https://mysite.com/sitemap.xml
```

TW will copy this to `dist/robots.txt` instead of generating its own.

## XSL Stylesheet (Stylish Sitemap)

When TW auto-generates `sitemap.xml`, it also creates `sitemap.xsl` — a stylesheet that makes the sitemap render as a beautiful, styled page when viewed in a browser (like Next.js does).

The XSL includes:
- Dark theme with gradient logo
- Summary cards (total URLs, format, generator)
- Table with URL list and titles
- Responsive design for mobile

### Custom XSL

Create `public/sitemap.xsl` with your own stylesheet. TW will use it instead of auto-generating one.

## Build Log

When you run `tw build`, the log shows which files were used:

```
  sitemap.xml: auto-generated (with XSL)
  sitemap.xsl: auto-generated
  robots.txt: using developer file (public/robots.txt)
  rss.xml: auto-generated
```

Or when using developer files:

```
  sitemap.xml: using developer file (public/sitemap.xml)
  robots.txt: using developer file (public/robots.txt)
```
