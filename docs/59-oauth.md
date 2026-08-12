# OAuth Integration

TW does not have built-in OAuth, but you can implement it using API routes.

## GitHub OAuth Example

### Step 1: Redirect to GitHub

```js
export function GET(request) {
    const clientId = process.env.GITHUB_CLIENT_ID
    const redirectUri = process.env.GITHUB_REDIRECT_URI
    const scope = 'read:user user:email'
    const url = 'https://github.com/login/oauth/authorize?client_id=' + clientId + '&redirect_uri=' + redirectUri + '&scope=' + scope
    return { status: 302, redirect: url }
}
```

### Step 2: Handle Callback

```js
export async function GET(request) {
    const code = request.query.code
    // Exchange code for token
    const tokenResponse = await fetch('https://github.com/login/oauth/access_token', {
        method: 'POST',
        headers: { 'Accept': 'application/json', 'Content-Type': 'application/json' },
        body: JSON.stringify({
            client_id: process.env.GITHUB_CLIENT_ID,
            client_secret: process.env.GITHUB_CLIENT_SECRET,
            code: code
        })
    })
    const tokens = await tokenResponse.json()
    // Fetch user info
    const userResponse = await fetch('https://api.github.com/user', {
        headers: { Authorization: 'Bearer ' + tokens.access_token }
    })
    const user = await userResponse.json()
    // Create session
    return {
        status: 302,
        redirect: '/dashboard',
        cookies: [{ name: 'session', value: createSession(user), httpOnly: true, maxAge: 3600 }]
    }
}
```

### Step 3: Login Button

```tw
a "Login with GitHub" { href "/api/auth/github", class "btn btn-github" }
```

## Environment Variables

```
# .env
GITHUB_CLIENT_ID=your_client_id
GITHUB_CLIENT_SECRET=your_client_secret
GITHUB_REDIRECT_URI=https://example.com/api/auth/github/callback
```

Never add these to `env { public "..." }`.
