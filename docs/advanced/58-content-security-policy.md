# Content Security Policy

## Basic CSP Header

In `tw.config`:

```
headers {
  rule {
    source "/**"
    set "Content-Security-Policy" "default-src 'self'; script-src 'self' 'unsafe-inline'; style-src 'self' 'unsafe-inline'; img-src 'self' data: https:; font-src 'self'; connect-src 'self' https://api.example.com"
  }
}
```

## CSP Directives

| Directive | Description |
|---|---|
| `default-src` | Fallback for all resource types |
| `script-src` | JavaScript sources |
| `style-src` | CSS sources |
| `img-src` | Image sources |
| `font-src` | Font sources |
| `connect-src` | AJAX/fetch/WebSocket sources |
| `frame-src` | iframe sources |

## CSP Values

| Value | Meaning |
|---|---|
| `'self'` | Same origin only |
| `'none'` | Nothing allowed |
| `'unsafe-inline'` | Allow inline styles/scripts |
| `https:` | Any HTTPS source |

## Other Security Headers

```
headers {
  rule {
    source "/**"
    set "X-Content-Type-Options" "nosniff"
    set "X-Frame-Options" "DENY"
    set "X-XSS-Protection" "1; mode=block"
    set "Referrer-Policy" "strict-origin-when-cross-origin"
    set "Strict-Transport-Security" "max-age=31536000; includeSubDomains"
  }
}
```
