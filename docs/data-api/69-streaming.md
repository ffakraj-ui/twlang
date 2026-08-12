# Streaming Responses

## Server-Sent Events (SSE)

```js
export function GET(request) {
    return {
        status: 200,
        headers: {
            'Content-Type': 'text/event-stream',
            'Cache-Control': 'no-cache'
        },
        stream: (send) => {
            send('data: {"msg":"Hello"}\n\n')
            const interval = setInterval(() => {
                send('data: {"time":"' + new Date().toISOString() + '"}\n\n')
            }, 1000)
            request.onClose(() => clearInterval(interval))
        }
    }
}
```

## Client-Side SSE

```tw
script {
    const source = new EventSource('/api/events')
    source.onmessage = (event) => {
        const data = JSON.parse(event.data)
        document.getElementById('output').textContent = data.time
    }
}

body {
    div { id "output", p "Waiting..." }
}
```

## Use Cases

| Use Case | Method |
|---|---|
| Live notifications | SSE |
| Chat | WebSocket |
| Progress updates | SSE |
| Real-time data | SSE or WebSocket |

## Limitations

- Streaming only with `render server`
- Static pages cannot stream
- Not all hosting providers support streaming
