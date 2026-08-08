# Authentication

TW Framework provides built-in authentication via middleware.

## Cookie-Based Auth

### Middleware Rule

```tw
// [home]/middleware.tw

rule "protect-dashboard" {
    match "/dashboard/**"
    auth {
        cookie "session"
        redirect "/login"
    }
}
```

When a user visits `/dashboard/*` without a valid `session` cookie, they're redirected to `/login`.

### Setting the Cookie

In your login API handler:

```js
// [home]/api/auth/login/route.twm

export function POST(request) {
    const { username, password } = request.body;

    // Verify credentials...
    if (username === "admin" && password === "secret") {
        return {
            status: 200,
            json: { ok: true },
            cookies: [
                { name: "session", value: "token123", httpOnly: true, maxAge: 3600 }
            ]
        };
    }

    return { status: 401, json: { error: "Invalid credentials" } };
}
```

### Logout

```js
// [home]/api/auth/logout/route.twm

export function POST(request) {
    return {
        status: 200,
        json: { ok: true },
        cookies: [
            { name: "session", value: "", httpOnly: true, maxAge: 0 }
        ]
    };
}
```

## JWT Authentication

### Middleware Rule

```tw
rule "api-auth" {
    match "/api/admin/**"
    auth_rule {
        jwt_secret_env "JWT_SECRET"
        required true
        cookie "token"
    }
}
```

### Auth Rule Properties

| Property | Description |
|---|---|
| `cookie` | Cookie name containing the JWT |
| `jwt_secret` | Direct JWT secret string |
| `jwt_secret_env` | Env var name containing the JWT secret |
| `required` | If true, request is denied without valid token |

### Generating JWT

```js
// [home]/api/auth/login/route.twm

export function POST(request) {
    const { username, password } = request.body;

    if (verifyCredentials(username, password)) {
        // Generate JWT (use a library like jsonwebtoken)
        const token = createJWT({ userId: 123 }, process.env.JWT_SECRET, { expiresIn: "1h" });

        return {
            status: 200,
            json: { token },
            cookies: [
                { name: "token", value: token, httpOnly: true, maxAge: 3600 }
            ]
        };
    }

    return { status: 401, json: { error: "Invalid credentials" } };
}
```

## CSRF Protection

TW generates CSRF tokens automatically:

```tw
form {
    on:submit "submitForm()"
    input { type "hidden", name "_csrf", value "{csrf_token}" }
}
```

The `{csrf_token}` variable is injected by TW when CSRF protection is enabled.

## Protected Routes Pattern

```
middleware.tw:
  rule "auth" {
    match "/admin/**"
    auth { cookie "session", redirect "/login" }
  }
  rule "api-auth" {
    match "/api/admin/**"
    auth_rule { jwt_secret_env "JWT_SECRET", required true }
  }

pages/login.tw          → public login form
api/auth/login/route.twm → sets session cookie
pages/admin/index.tw    → protected (redirects to /login if no session)
api/admin/*             → protected (returns 401 if no JWT)
```
