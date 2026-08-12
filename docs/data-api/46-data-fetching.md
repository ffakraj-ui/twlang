# Data Fetching Patterns

## Server-Side Data Fetching

```tw
page {
    title "Products"
    render server
}

script {
    export async function getProducts() {
        const response = await fetch('https://api.example.com/products');
        return response.json();
    }
}

body {
    each products as product {
        div { h3 "{product.name}", p "${product.price}" }
    }
}
```

## API Route Data Fetching

```js
export async function GET(request) {
    const page = parseInt(request.query.page) || 1;
    const response = await fetch(
        `https://api.example.com/products?page=${page}`
    );
    const data = await response.json();
    return { status: 200, json: data };
}
```

## JSON Data Files

```tw
load "@./data/products.json"

body {
    each products as product {
        div { h3 "{product.name}", p "{product.description}" }
    }
}
```

## Pagination

```js
export async function GET(request) {
    const page = parseInt(request.query.page) || 1;
    const limit = parseInt(request.query.limit) || 10;
    const response = await fetch(`https://api.example.com/articles?page=${page}&limit=${limit}`);
    const data = await response.json();
    return {
        status: 200,
        json: { articles: data.articles, page, hasMore: page < data.totalPages }
    };
}
```

## Caching Fetched Data

```js
const cache = new Map();

export async function cachedFetch(url, ttl = 3600) {
    const cached = cache.get(url);
    if (cached && Date.now() - cached.timestamp < ttl * 1000) {
        return cached.data;
    }
    const response = await fetch(url);
    const data = await response.json();
    cache.set(url, { data, timestamp: Date.now() });
    return data;
}
```

## Error Handling

```js
export async function GET(request) {
    try {
        const response = await fetch('https://api.example.com/data');
        if (!response.ok) {
            return { status: response.status, json: { error: `API returned ${response.status}` } };
        }
        const data = await response.json();
        return { status: 200, json: data };
    } catch (err) {
        return { status: 503, json: { error: 'Service unavailable' } };
    }
}
```

## Parallel Fetching

```js
export async function GET(request) {
    const [users, posts, comments] = await Promise.all([
        fetch('https://api.example.com/users').then(r => r.json()),
        fetch('https://api.example.com/posts').then(r => r.json()),
        fetch('https://api.example.com/comments').then(r => r.json())
    ]);
    return { status: 200, json: { users, posts, comments } };
}
```

## Revalidation

```tw
page {
    title "Dashboard"
    render static
    revalidate 60    // Refresh data every 60 seconds
}
```
