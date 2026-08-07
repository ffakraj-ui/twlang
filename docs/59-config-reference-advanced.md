# Advanced Config Reference

## Complete tw.config Fields

```
name: My Site
pretty_urls: true
modular_pipeline: true
theme: system
watch_interval: 1.0

env {
  public "API_URL"
  public "SITE_NAME"

  schema {
    API_URL { type "string" required true }
    MAX_ITEMS { type "number" default "10" }
    PORT { type "number" default "3000" }
  }
}

server {
  external_packages ["firebase-admin", "google-auth-library"]
}

images {
  remote_patterns [
    { protocol: "https", hostname: "**" }
  ]
  unoptimized true
}

bundler {
  client_externals ["firebase-admin"]

  fallback {
    fs false
    net false
    tls false
    http false
    https false
    path false
    stream false
    crypto false
    os false
    zlib false
  }
}

headers {
  rule {
    source "/api/**"
    set "Cache-Control" "no-store, no-cache, private"
  }
  rule {
    source "/static/**"
    set "Cache-Control" "public, max-age=31536000, immutable"
  }
  rule {
    source "/**"
    set "Cache-Control" "public, s-maxage=3600, stale-while-revalidate=86400"
  }
}

redirects {
  rule {
    source "/old/:slug"
    destination "/new/:slug"
    permanent true
  }
}

rewrites {
  rule {
    source "/games"
    destination "/category/games"
  }
}
```

## Field Reference

| Field | Type | Default | Description |
|---|---|---|---|
| name | string | required | Project name |
| pretty_urls | bool | true | Clean URLs without .html |
| modular_pipeline | bool | false | Use modular build pipeline |
| theme | string | system | Theme preference |
| watch_interval | number | 1.0 | Dev server watch interval (seconds) |

## Headers Rules

Headers use glob patterns for matching:
- `/api/**` matches all API routes
- `/static/**` matches all static assets
- `/**` matches everything

## Redirect Rules

- `permanent true` = 301 redirect
- `permanent false` = 302 redirect
- `:slug` = URL parameter passed to destination

## Rewrite Rules

Rewrites serve different content without changing the URL in the browser.
