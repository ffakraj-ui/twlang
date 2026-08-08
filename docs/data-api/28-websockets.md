# WebSockets

TW Framework supports WebSocket connections for real-time features.

## Setup

Create a WebSocket handler file:

```
[home]/ws/
├── chat.twm           → ws://localhost:3000/ws/chat
└── notifications.twm   → ws://localhost:3000/ws/notifications
```

## WebSocket Handler

```js
// [home]/ws/chat.twm

export function onConnection(ws, request) {
    console.log("New WebSocket connection");

    ws.on("message", (data) => {
        const msg = JSON.parse(data);
        // Broadcast to all clients
        broadcast({ user: msg.user, text: msg.text });
    });

    ws.on("close", () => {
        console.log("Connection closed");
    });
}
```

## Client-Side Usage

```tw
script {
    const ws = new WebSocket('ws://localhost:3000/ws/chat');

    ws.onopen = () => {
        console.log('Connected');
    };

    ws.onmessage = (event) => {
        const msg = JSON.parse(event.data);
        appendMessage(msg);
    };

    ws.onclose = () => {
        console.log('Disconnected');
    };
}
```

## Dev Server WebSocket

The dev server uses WebSocket for live reload. Your app's WebSocket handlers run alongside it without conflict.

## Discovering WebSocket Routes

TW automatically discovers `.twm` files in `[home]/ws/` directory during build and dev.

Use `tw doctor` to verify WebSocket routes are detected:

```bash
tw doctor
```

Output includes:
```
✓ WebSocket routes: 2 found
  - /ws/chat
  - /ws/notifications
```
