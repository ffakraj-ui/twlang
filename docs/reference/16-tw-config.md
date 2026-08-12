# TW Config Reference

The `tw.config` file is the project configuration file at the root.

## Minimal Config

```
name: My Site
```

## Full Config

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
  }
}

server {
  external_packages [
    "firebase-admin",
    "google-auth-library"
  ]
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

## Config Fields

| Field | Type | Description |
|---|---|---|
| `name` | string | Project name |
| `pretty_urls` | bool | Strip trailing slashes, no `.html` extensions |
| `modular_pipeline` | bool | Use modular build pipeline |
| `theme` | string | Theme: `system`, `light`, `dark` |
| `watch_interval` | number | Dev server file watch interval (seconds) |

## Headers Rules

```
headers {
  rule {
    source "/api/**"
    set "Cache-Control" "no-store"
    set "X-Robots-Tag" "noindex"
  }
}
```

## Redirects Rules

```
redirects {
  rule {
    source "/old-path"
    destination "/new-path"
    permanent true       // 301 (permanent) vs 302 (temporary)
  }
}
```

## Rewrites Rules

```
rewrites {
  rule {
    source "/games"
    destination "/category/games"
  }
}
```

Rewrites serve different content without changing the URL.
