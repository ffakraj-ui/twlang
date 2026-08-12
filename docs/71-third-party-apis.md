# Third-Party API Integration

## Fetching External APIs

```js
export async function GET(request) {
    const { city } = request.query
    const apiKey = process.env.WEATHER_API_KEY

    const response = await fetch(
        'https://api.openweathermap.org/data/2.5/weather?q=' + city + '&appid=' + apiKey
    )
    const data = await response.json()

    return {
        status: 200,
        json: { temp: data.main.temp, desc: data.weather[0].description }
    }
}
```

## Error Handling

```js
export async function GET(request) {
    try {
        const response = await fetch('https://api.example.com/data')
        if (!response.ok) {
            return { status: 502, json: { error: 'Upstream API error' } }
        }
        const data = await response.json()
        return { status: 200, json: { data } }
    } catch (err) {
        return { status: 500, json: { error: err.message } }
    }
}
```

## Caching API Responses

```js
const cache = new Map()

export async function GET(request) {
    const key = request.url
    const cached = cache.get(key)
    if (cached && Date.now() - cached.time < 60000) {
        return { status: 200, json: cached.data }
    }
    const response = await fetch('https://api.example.com/data')
    const data = await response.json()
    cache.set(key, { data, time: Date.now() })
    return { status: 200, json: data }
}
```

## Configuration

```
# .env
WEATHER_API_KEY=your_key
STRIPE_SECRET_KEY=sk_test_xxx
SENDGRID_API_KEY=SG.xxx
```

Most API keys should stay server-only (do not add to public).
