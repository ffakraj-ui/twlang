# Cookie Management

## Setting Cookies

In `.twm` API handlers:

```js
return {
    status: 200,
    json: { ok: true },
    cookies: [
        { name: "session", value: "abc123", httpOnly: true, maxAge: 3600 }
    ]
}
```

## Cookie Options

| Option | Type | Description |
|---|---|---|
| `name` | string | Cookie name |
| `value` | string | Cookie value |
| `httpOnly` | boolean | Prevent JS access |
| `secure` | boolean | HTTPS only |
| `maxAge` | number | Expiry in seconds |
| `sameSite` | string | strict, lax, none |
| `path` | string | Cookie path (default: /) |
| `domain` | string | Cookie domain |

## Reading Cookies

```js
export function GET(request) {
    const session = request.cookies.session
    if (!session) {
        return { status: 401, json: { error: "Not authenticated" } }
    }
    return { status: 200, json: { session } }
}
```

## Clearing Cookies

```js
export function POST(request) {
    return {
        status: 200,
        json: { ok: true },
        cookies: [
            { name: "session", value: "", maxAge: 0, httpOnly: true }
        ]
    }
}
```

## Cookie in Middleware

```tw
rule "set-visitor-cookie" {
    match "/**"
    cookie "visitor_id" "random-id"
}
```

## Best Practices

1. Always use `httpOnly: true` for session cookies
2. Use `secure: true` in production (HTTPS)
3. Use `sameSite: "lax"` to prevent CSRF
4. Set reasonable `maxAge`
5. Never store sensitive data in non-httpOnly cookies
