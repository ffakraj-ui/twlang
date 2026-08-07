# Monitoring and Analytics

## Build Report

```bash
tw build --prod --report
```

Shows: pages compiled, build duration, output size, cache hit/miss ratio, performance metrics.

## Build Analysis

```bash
tw build --prod --analyze
```

Shows: bundle sizes, dependency graph, code splitting chunks, performance score.

## tw doctor

```bash
tw doctor
```

Health checks: config validation, env schema, port availability, file structure, WebSocket routes, .gitignore hygiene.

## tw info

```bash
tw info
```

Project summary: total pages, components, layouts, API routes, dependencies.

## Custom Analytics

### Page View Tracking

```tw
script {
    fetch("/api/analytics", {
        method: "POST",
        headers: { "Content-Type": "application/json" },
        body: JSON.stringify({
            page: window.location.pathname,
            referrer: document.referrer,
            timestamp: Date.now()
        })
    });
}
```

```js
// [home]/api/analytics/route.twm
export function POST(request) {
    const { page, referrer, timestamp } = request.body;
    // Store in database
    return { status: 200, json: { tracked: true } };
}
```

## Performance Monitoring

```tw
script {
    // Track Core Web Vitals
    const observer = new PerformanceObserver((list) => {
        for (const entry of list.getEntries()) {
            console.log(entry.name, entry.value);
        }
    });
    observer.observe({ entryTypes: ["largest-contentful-paint", "layout-shift"] });
}
```
