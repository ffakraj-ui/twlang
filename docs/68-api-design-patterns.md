# API Design Patterns

## RESTful API

```js
// [home]/api/products/route.twm
export function GET(request) {
    const page = parseInt(request.query.page) || 1;
    return { status: 200, json: { products: [], page } };
}

export function POST(request) {
    const { name, price } = request.body;
    if (!name || !price) {
        return { status: 400, json: { error: "Missing fields" } };
    }
    return { status: 201, json: { id: 1, name, price } };
}
```

```js
// [home]/api/products/[id]/route.twm
export function GET(request) {
    const id = request.params.id;
    return { status: 200, json: { id, name: "Product" } };
}

export function PUT(request) {
    const id = request.params.id;
    const { name } = request.body;
    return { status: 200, json: { id, name, updated: true } };
}

export function DELETE(request) {
    const id = request.params.id;
    return { status: 200, json: { id, deleted: true } };
}
```

## Error Handling Pattern

```js
export async function GET(request) {
    try {
        const data = await fetchData();
        if (!data) {
            return { status: 404, json: { error: "Not found" } };
        }
        return { status: 200, json: data };
    } catch (err) {
        return { status: 500, json: { error: "Internal server error" } };
    }
}
```

## Pagination Pattern

```js
export async function GET(request) {
    const page = parseInt(request.query.page) || 1;
    const limit = Math.min(parseInt(request.query.limit) || 20, 100);
    const offset = (page - 1) * limit;

    const items = await getItems(offset, limit);
    const total = await getTotalCount();

    return {
        status: 200,
        json: {
            items, page, limit, total,
            totalPages: Math.ceil(total / limit),
            hasMore: offset + limit < total
        }
    };
}
```

## Response Status Codes

| Status | Meaning |
|---|---|
| 200 | OK - GET success |
| 201 | Created - POST success |
| 204 | No Content - DELETE success |
| 400 | Bad Request - Validation error |
| 401 | Unauthorized - Not authenticated |
| 403 | Forbidden - Not authorized |
| 404 | Not Found |
| 429 | Too Many Requests |
| 500 | Internal Server Error |

## Response Shapes (v0.9.29+)

All response shapes supported by `.twm` API routes:

| Shape | Description |
|-------|-------------|
| `{ status, json }` | JSON response (Next.js-style) |
| `{ status, text }` | Plain text response |
| `{ status, html }` | HTML response |
| `{ status, body, headers }` | Custom body with headers |
| `"string"` | Plain text (200 OK) |
| `{ key: value }` | JSON (200 OK) |

### Runtime Directives

| Directive | Engine |
|-----------|--------|
| `runtime = "nodejs"` | Node.js worker (default) |
| `runtime = "edge"` | V8 Isolate |
| `runtime = "python"` | Python in-process |
| `runtime = "wasm"` | wasmtime sandbox |
