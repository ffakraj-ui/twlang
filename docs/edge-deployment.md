# Edge Deployment

Deploy TW Framework to edge networks for global low-latency delivery.

## What is Edge Deployment?

Edge deployment runs your code on servers close to users worldwide, reducing latency to under 50ms globally.

## Cloudflare Workers

### Setup

1. Install Wrangler:

```bash
npm install -g wrangler
wrangler login
```

2. Create `wrangler.toml`:

```toml
name = "tw-app"
main = "dist/worker.js"
compatibility_date = "2024-03-01"

[site]
bucket = "./dist"

[vars]
ENVIRONMENT = "production"
```

3. Build for edge:

```bash
tw build --prod --target edge
```

4. Deploy:

```bash
wrangler deploy
```

### KV Storage

Use Cloudflare KV for data at the edge:

```javascript
// In your worker
export default {
  async fetch(request, env) {
    const cacheKey = new URL(request.url).pathname;
    let html = await env.TW_CACHE.get(cacheKey);

    if (!html) {
      html = await generatePage(request);
      await env.TW_CACHE.put(cacheKey, html, { expirationTtl: 3600 });
    }

    return new Response(html, {
      headers: { "Content-Type": "text/html" }
    });
  }
};
```

## Vercel Edge

### Setup

1. Install Vercel CLI:

```bash
npm install -g vercel
```

2. Create `vercel.json`:

```json
{
  "builds": [
    {
      "src": "dist/**",
      "use": "@vercel/static"
    }
  ],
  "routes": [
    {
      "src": "/(.*)",
      "dest": "/dist/$1"
    }
  ]
}
```

3. Deploy:

```bash
vercel --prod
```

### Edge Functions

```javascript
// api/edge.js
export const config = {
  runtime: 'edge',
};

export default async function handler(request) {
  const url = new URL(request.url);

  // Check cache
  const cache = caches.default;
  let response = await cache.match(request);

  if (!response) {
    const html = await fetch(`https://origin.example.com${url.pathname}`);
    response = new Response(html.body, {
      headers: {
        'Content-Type': 'text/html',
        'Cache-Control': 'public, max-age=60'
      }
    });
    await cache.put(request, response.clone());
  }

  return response;
}
```

## Netlify Edge

### Setup

1. Create `netlify.toml`:

```toml
[build]
  command = "tw build --prod"
  publish = "dist"

[[edge_functions]]
  function = "geo-redirect"
  path = "/*"
```

2. Create edge function:

```javascript
// netlify/edge-functions/geo-redirect.js
export default async (request, context) => {
  const country = context.geo?.country?.code;

  if (country === 'IN' && request.url.pathname === '/pricing') {
    return context.rewrite('/pricing/inr');
  }

  return context.next();
};
```

## Deno Deploy

```bash
# Install deployctl
deno install -A --no-check -r -f https://deno.land/x/deploy/deployctl.ts

# Deploy
deployctl deploy --project=tw-app --prod
```

## Edge Caching Strategies

### Cache Everything

```javascript
// Cache HTML at the edge for 1 hour
const response = new Response(html, {
  headers: {
    'Cache-Control': 'public, max-age=3600, s-maxage=3600',
    'CDN-Cache-Control': 'max-age=3600'
  }
});
```

### Stale-While-Revalidate

```javascript
// Serve stale for 24h, revalidate in background
const response = new Response(html, {
  headers: {
    'Cache-Control': 'public, max-age=60, stale-while-revalidate=86400'
  }
});
```

### Cache Tags for Invalidation

```javascript
// Tag content for targeted purging
const response = new Response(html, {
  headers: {
    'Cache-Tag': 'products,homepage'
  }
});

// Later, purge by tag
// curl -X POST "https://api.cloudflare.com/client/v4/zones/xxx/purge_cache" //   -H "Content-Type: application/json" //   -d '{"tags":["products"]}'
```

## Geo-Based Features

### Currency Detection

```javascript
export default {
  async fetch(request, env) {
    const country = request.cf?.country;
    const currency = country === 'IN' ? 'INR' : 'USD';

    const html = await generatePage({ currency });
    return new Response(html, { headers: { 'Content-Type': 'text/html' } });
  }
};
```

### Language Detection

```javascript
const acceptLang = request.headers.get('Accept-Language');
const lang = acceptLang?.startsWith('hi') ? 'hi' : 'en';
```

## Best Practices

1. **Cache aggressively**: Edge bandwidth is cheap, origin bandwidth is expensive.
2. **Use KV for config**: Avoid origin round-trips for settings.
3. **Minimize origin fetches**: Serve from edge cache when possible.
4. **Handle cold starts**: Edge functions may have cold start latency.
5. **Monitor edge errors**: Use the platform's analytics dashboard.
6. **Test globally**: Use tools like Pingdom or GTmetrix from multiple locations.
