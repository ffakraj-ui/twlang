# Custom Error Pages

## 404 Page

Create `[home]/pages/404.tw`:

```tw
page {
    title "404 - Not Found"
    render static
}

body {
    div {
        class "error-container"
        h1 "404"
        p "The page you're looking for doesn't exist."
        a "Go Home" { href "/", class "btn btn-primary" }
    }
}
```

## 500 Page

Create `[home]/pages/500.tw`:

```tw
page {
    title "Server Error"
    render static
}

body {
    div {
        class "error-container"
        h1 "Something went wrong"
        p "We're working on fixing this."
        a "Try again" { href "/", class "btn" }
    }
}
```

## Special Page Names

| File | Status Code |
|---|---|
| `[home]/pages/404.tw` | 404 Not Found |
| `[home]/pages/500.tw` | 500 Server Error |
| `[home]/pages/403.tw` | 403 Forbidden |
| `[home]/pages/503.tw` | 503 Service Unavailable |

## Dev Mode Error Display

During `tw dev`, compiler errors show an error overlay in the browser with line numbers and suggestions. This is automatic.

## Error Styling

```css
.error-container {
    text-align center
    padding 80px 20px
    max-width 600px
    margin 0 auto
}

.error-container h1 {
    font-size 72px
    color #ef4444
    margin-bottom 16px
}

.error-container p {
    font-size 18px
    color #6b7280
    margin-bottom 24px
}
```
