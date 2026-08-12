# Dev Server

## Starting the Dev Server

```bash
tw dev
```

Options:
```bash
tw dev --host 0.0.0.0 --port 8080 --no-open
```

| Flag | Default | Description |
|---|---|---|
| `--host` | 127.0.0.1 | Bind address |
| `--port` | 3000 | Port number |
| `--no-open` | false | Don't auto-open browser |

## Live Reload

The dev server automatically reloads when files change:

- `.tw` files → page recompiles, browser refreshes
- `.tss` files → CSS recompiles, hot-swapped
- `.twm` files → API route recompiles
- `middleware.tw` → middleware rules reload
- `tw.config` → full server restart

## Reload Mechanism

TW uses two reload mechanisms:

### inotify (Linux)

On Linux (including Termux), TW uses `inotify` for instant file change detection with minimal battery usage.

### Polling (fallback)

On macOS/Windows, TW falls back to polling with configurable interval:

```
# tw.config
watch_interval: 1.0
```

Or via environment variable:
```bash
TW_WATCH_INTERVAL=0.5 tw dev
```

## API Routes in Dev

API routes (`.twm` files) are served at `/api/...` during dev:

```
[home]/api/hello.twm → http://localhost:3000/api/hello
```

## Dev Server Features

- **Hot CSS reload** — styles update without full page refresh
- **Error overlay** — compiler errors shown in browser with file/line info
- **Source maps** — generated for debugging
- **Search index** — built on-the-fly from current pages

## Accessing from Other Devices

```bash
tw dev --host 0.0.0.0
```

Then access from another device on the same network:
```
http://YOUR_IP:3000
```

## Dev Server vs Preview Server

| Feature | `tw dev` | `tw preview` |
|---|---|---|
| Source files | Live `.tw` files | Built `dist/` |
| API routes | Yes | No (static) |
| Live reload | Yes | No |
| Build needed | No | Yes |
| Production output | No | Yes |
