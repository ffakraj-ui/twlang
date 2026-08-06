# WebSockets

TW's dev and production servers support real-time WebSocket connections out of the box.

## Creating a WebSocket route

Add a Python file under [home]/ws/. The filename becomes the route:

[home]/ws/echo.py -> ws://localhost:3000/ws/echo

Each file must export an on_connect(conn) function:

    def on_connect(conn):
        conn.send_text("welcome")
        for message in conn:
            if isinstance(message, str):
                conn.send_text("echo: " + message)
            else:
                conn.send_bytes(message)

## The connection object

- conn.send_text(str) / conn.send_bytes(bytes)
- conn.close(code=1000)
- for message in conn: iterate incoming messages until disconnect
- conn.path, conn.headers

## Client-side

Standard WebSocket API, no TW-specific client needed:

    const ws = new WebSocket("ws://localhost:3000/ws/echo");
    ws.onmessage = (event) => console.log(event.data);

## Notes

- Dynamic route params in [home]/ws/ are not yet supported.
- Unmatched /ws/* paths get a plain 404 instead of upgrading.
