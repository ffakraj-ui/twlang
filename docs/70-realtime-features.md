# Realtime Features

## WebSocket

Create WebSocket handlers in [home]/ws/:

```js
// [home]/ws/chat.twm

export function onConnection(ws, request) {
    console.log("New connection");

    ws.on("message", (data) => {
        const msg = JSON.parse(data);
        broadcast({ user: msg.user, text: msg.text, timestamp: Date.now() });
    });

    ws.on("close", () => {
        console.log("Connection closed");
    });
}

function broadcast(message) {
    connections.forEach(ws => {
        ws.send(JSON.stringify(message));
    });
}
```

## Client-Side WebSocket

```tw
script {
    const ws = new WebSocket("ws://localhost:3000/ws/chat");

    ws.onopen = () => {
        console.log("Connected to chat");
    };

    ws.onmessage = (event) => {
        const msg = JSON.parse(event.data);
        appendMessage(msg);
    };

    ws.onclose = () => {
        console.log("Disconnected, reconnecting...");
        setTimeout(connect, 3000);
    };

    function sendMessage(text) {
        ws.send(JSON.stringify({ user: "me", text: text }));
    }
}

body {
    div { id "chat-messages", class "chat-messages" }
    input { type "text", id "chat-input", placeholder "Type a message..." }
    button "Send" { on:click "sendMessage(document.getElementById('chat-input').value)" }
}
```

## Polling Fallback

For environments without WebSocket support:

```tw
script {
    async function pollUpdates() {
        const response = await fetch("/api/updates");
        const data = await response.json();
        if (data.updated) {
            updateUI(data);
        }
        setTimeout(pollUpdates, 5000);
    }
    pollUpdates();
}
```
