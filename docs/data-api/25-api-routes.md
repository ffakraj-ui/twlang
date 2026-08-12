# API Routes

API routes are server-side endpoints defined in `.twm` files.

## File Structure

```
[home]/api/
├── hello.twm              → GET/POST /api/hello
├── users/
│   ├── route.twm          → GET/POST /api/users
│   └── [id]/
│       └── route.twm      → GET/PUT/DELETE /api/users/:id
├── products/
│   └── route.twm          → /api/products
└── health/
    └── route.twm          → /api/health
```

## Basic Handler

```js
// [home]/api/hello.twm

export function GET(request) {
    return {
        status: 200,
        json: { message: "Hello from TW!" }
    };
}
```

## HTTP Methods

```js
export function GET(request) { ... }
export function POST(request) { ... }
export function PUT(request) { ... }
export function PATCH(request) { ... }
export function DELETE(request) { ... }
```

## Request Object

```js
{
    method: "GET",
    url: "/api/users/123",
    headers: { "content-type": "application/json" },
    body: { name: "John" },
    query: { page: "1", limit: "10" },
    params: { id: "123" },
    cookies: { session: "abc123" }
}
```

## Response Types

### JSON Response

```js
return { status: 200, json: { users: [] } };
```

### Text Response

```js
return { status: 200, text: "OK" };
```

### HTML Response

```js
return { status: 200, html: "<h1>Hello</h1>" };
```

### Redirect

```js
return { status: 302, redirect: "/login" };
```

### Custom Headers

```js
return {
    status: 200,
    json: { data: [] },
    headers: { "X-Total-Count": "42" }
};
```

### Set Cookies

```js
return {
    status: 200,
    json: { ok: true },
    cookies: [
        { name: "session", value: "abc123", httpOnly: true, maxAge: 3600 }
    ]
};
```

## Dynamic Route Params

```
[home]/api/users/[id]/route.twm
```

```js
export function GET(request) {
    const id = request.params.id;
    const user = getUser(id);
    if (!user) {
        return { status: 404, json: { error: "User not found" } };
    }
    return { status: 200, json: user };
}
```

## Query Parameters

```js
export function GET(request) {
    const page = parseInt(request.query.page) || 1;
    const limit = parseInt(request.query.limit) || 10;
    return { status: 200, json: { page, limit } };
}
```

## POST Body

```js
export function POST(request) {
    const { name, email } = request.body;
    if (!name || !email) {
        return { status: 400, json: { error: "Missing fields" } };
    }
    // Save to database...
    return { status: 201, json: { id: 1, name, email } };
}
```

## Error Handling

```js
export function GET(request) {
    try {
        const data = fetchData();
        return { status: 200, json: { data } };
    } catch (err) {
        return { status: 500, json: { error: err.message } };
    }
}
```

## CORS

Enable CORS via middleware or headers:

```js
return {
    status: 200,
    json: { data: [] },
    headers: {
        "Access-Control-Allow-Origin": "*",
        "Access-Control-Allow-Methods": "GET, POST, PUT, DELETE"
    }
};
```

## File Uploads

```js
export function POST(request) {
    const file = request.body.file;
    // Handle file...
    return { status: 201, json: { uploaded: true } };
}
```
