# TWM Server Modules

`.twm` files are server-side JavaScript modules for API routes and data fetching.

## Basic Structure

```js
// [home]/api/hello.twm

export function GET(request) {
    return {
        status: 200,
        json: { message: "Hello from TW!" }
    };
}

export function POST(request) {
    const body = request.body;
    return {
        status: 201,
        json: { created: true, data: body }
    };
}
```

## HTTP Methods

Each method is an exported function:

| Method | Function |
|---|---|
| GET | `export function GET(request)` |
| POST | `export function POST(request)` |
| PUT | `export function PUT(request)` |
| PATCH | `export function PATCH(request)` |
| DELETE | `export function DELETE(request)` |

## Request Object

```js
{
    method: "GET",
    url: "/api/hello",
    headers: { "content-type": "application/json" },
    body: { ... },           // parsed JSON body
    query: { page: "1" },   // query params
    params: { id: "123" },  // route params
    cookies: { session: "..." }
}
```

## Response Types

### JSON

```js
return { status: 200, json: { key: "value" } };
```

### Text

```js
return { status: 200, text: "Plain text response" };
```

### HTML

```js
return { status: 200, html: "<h1>Hello</h1>" };
```

### Redirect

```js
return { status: 302, redirect: "/new-path" };
```

### Headers

```js
return {
    status: 200,
    json: { data: "value" },
    headers: { "X-Custom-Header": "value" }
};
```

### Cookies

```js
return {
    status: 200,
    json: { ok: true },
    cookies: [{ name: "session", value: "abc123", httpOnly: true }]
};
```

## Route Structure

```
[home]/api/
├── hello.twm              → /api/hello
├── users/
│   ├── route.twm          → /api/users
│   └── [id]/
│       └── route.twm      → /api/users/:id
└── products/
    └── route.twm          → /api/products
```

## Inline Script Blocks

You can also embed server-side JS directly in `.tw` files:

```tw
script {
    export function getData() {
        return fetch('/api/data').then(r => r.json());
    }
}
```

Script blocks are compiled as `.twm` modules — the content is not executed as-is.
