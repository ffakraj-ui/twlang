# API Integration Patterns

Connect your TW Framework site to external APIs and services.

## Pattern 1: Static Build-Time Fetching

Fetch data at build time for static pages:

```tw
page {
    title "Weather"
    layout "main"
    render static
}

let weather = fetch "https://api.weather.com/v1/current?city=delhi"

body {
    div {
        class "weather-card"
        h1 "Weather in Delhi"
        p { class "temp" "{weather.temperature} C" }
        p { class "condition" "{weather.condition}" }
    }
}
```

**Best for**: Data that changes infrequently (daily weather, static content).

## Pattern 2: Server-Side Rendering with API

Fetch fresh data on every request:

```tw
page {
    title "Live Prices"
    layout "main"
    render server
}

body {
    div {
        class "prices"
        h1 "Live Crypto Prices"
        each prices as coin {
            div {
                class "price-row"
                span "{coin.name}"
                span { class "price" "$ {coin.price}" }
            }
        }
    }
}
```

With `[home]/api/prices/route.twm`:

```twm
function get(request):
    response = http.get("https://api.coingecko.com/api/v3/simple/price?ids=bitcoin,ethereum&vs_currencies=usd")
    prices = response.json()
    return json_response([
        {"name": "Bitcoin", "price": prices["bitcoin"]["usd"]},
        {"name": "Ethereum", "price": prices["ethereum"]["usd"]}
    ])
```

**Best for**: Real-time data that must be fresh.

## Pattern 3: Client-Side Fetching

Load data after page load using JavaScript:

```tw
page {
    title "Dashboard"
    layout "main"
    render static
}

body {
    div {
        class "dashboard"
        h1 "Dashboard"
        div {
            id "stats-container"
            class "stats-grid"
            p { class "loading" "Loading stats..." }
        }
    }
}

script {
    async function loadStats() {
        const res = await fetch('/api/stats');
        const stats = await res.json();
        const container = document.getElementById('stats-container');
        container.innerHTML = stats.map(s => `
            <div class="stat-card">
                <h3>${s.label}</h3>
                <p class="stat-value">${s.value}</p>
            </div>
        `).join('');
    }
    loadStats();
}
```

**Best for**: User-specific data, dashboards, and admin panels.

## Pattern 4: Webhook Integration

Receive data from external services:

```twm
// [home]/api/webhooks/stripe/route.twm
function post(request):
    payload = request.json()
    signature = request.headers.get("Stripe-Signature")

    if not verify_stripe_signature(payload, signature):
        return json_response({"error": "Invalid signature"}, status=400)

    event_type = payload.get("type")

    if event_type == "payment_intent.succeeded":
        order_id = payload["data"]["object"]["metadata"]["order_id"]
        mark_order_paid(order_id)
        send_confirmation_email(order_id)

    return json_response({"received": True})
```

**Best for**: Payment processors, CI/CD notifications, third-party events.

## Pattern 5: GraphQL Integration

Query GraphQL APIs:

```twm
function get_posts(request):
    query = (
        "query { posts(limit: 10) { id title excerpt author { name } } }"
    )

    response = http.post(
        "https://api.example.com/graphql",
        json={"query": query},
        headers={"Authorization": f"Bearer {API_KEY}"}
    )

    data = response.json()
    return json_response(data["data"]["posts"])
```

## Pattern 6: Caching External APIs

Cache API responses to reduce load:

```twm
function get_cached_data(request):
    cache_key = "external:products"

    cached = cache.get(cache_key)
    if cached:
        return json_response(cached)

    response = http.get("https://api.example.com/products")
    data = response.json()

    cache.set(cache_key, data, ttl=300)

    return json_response(data)
```

## Pattern 7: Error Resilience

Handle API failures gracefully:

```twm
function get_reliable_data(request):
    try:
        response = http.get("https://api.example.com/data", timeout=5)
        response.raise_for_status()
        return json_response(response.json())
    except TimeoutError:
        stale = cache.get("data:stale")
        if stale:
            return json_response({"data": stale, "stale": True})
        return json_response({"error": "Service temporarily unavailable"}, status=503)
    except Exception as e:
        log_error(e)
        return json_response({"error": "Internal error"}, status=500)
```

## Authentication Patterns

### API Key in Header

```twm
function get_protected_data(request):
    headers = {"X-API-Key": env("EXTERNAL_API_KEY")}
    response = http.get("https://api.example.com/data", headers=headers)
    return json_response(response.json())
```

### OAuth 2.0

```twm
function get_oauth_data(request):
    token = get_oauth_token(
        client_id=env("OAUTH_CLIENT_ID"),
        client_secret=env("OAUTH_CLIENT_SECRET"),
        token_url="https://auth.example.com/oauth/token"
    )

    response = http.get(
        "https://api.example.com/data",
        headers={"Authorization": f"Bearer {token}"}
    )
    return json_response(response.json())
```

## Rate Limiting

Respect API rate limits:

```twm
import time
from collections import deque

_rate_limits = {}

def rate_limited_fetch(url, max_requests=10, window=60):
    host = url.split('/')[2]
    now = time.time()

    if host not in _rate_limits:
        _rate_limits[host] = deque()

    while _rate_limits[host] and _rate_limits[host][0] < now - window:
        _rate_limits[host].popleft()

    if len(_rate_limits[host]) >= max_requests:
        sleep_time = _rate_limits[host][0] - (now - window)
        time.sleep(max(0, sleep_time))

    _rate_limits[host].append(time.time())
    return http.get(url)
```

## Best Practices

1. **Never expose API keys in .tw files**. Use `env:` in `tw.config`.
2. **Always set timeouts**. Default HTTP timeouts can hang indefinitely.
3. **Handle all error cases**. Network failures are common.
4. **Cache aggressively**. External APIs are slow and rate-limited.
5. **Log API calls**. Track latency and error rates.
6. **Validate responses**. Do not trust external API schemas.

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
