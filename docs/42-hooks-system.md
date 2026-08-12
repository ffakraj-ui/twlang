# Hooks System

## Page-Level Hooks

### on load init

Runs initialization code when the page loads:

```tw
on load init "setupPage"

body {
    h1 "Welcome"
}
```

The `setupPage` function must be defined in a `.twm` module or `script {}` block:

```tw
script {
    function setupPage() {
        console.log("Page initialized");
        initializeTheme();
        loadUserData();
    }
}
```

## Dev Server Hooks

Create a Python hook file:

```
[home]/hooks/modern_middleware.py
```

This Python hook runs before TW's built-in middleware:

```python
# [home]/hooks/modern_middleware.py

def before_request(method, path, headers, body):
    # Called before any middleware or route handling
    if path.startswith("/api/"):
        print(f"API call: {method} {path}")
    return None  # None = continue normally

def after_request(method, path, status, response):
    # Called after request is handled
    print(f"{method} {path} -> {status}")
    return response
```

## Hook Execution Order

1. **before_request** hook (if exists)
2. Middleware rules (`middleware.tw`)
3. API route matching
4. Page route matching
5. Page compilation/rendering
6. **after_request** hook (if exists)

## Hook Return Values

### before_request

| Return | Behavior |
|---|---|
| `None` | Continue normally |
| `dict` with `status` | Short-circuit, return this response |
| `dict` with `redirect` | Redirect to URL |

### after_request

| Return | Behavior |
|---|---|
| `None` | Use original response |
| `dict` | Override response |

## Example: Request Logging

```python
import datetime

def before_request(method, path, headers, body):
    timestamp = datetime.datetime.now().isoformat()
    ip = headers.get("X-Forwarded-For", "unknown")
    print(f"[{timestamp}] {ip} {method} {path}")
    return None
```

## Example: IP Blocking

```python
BLOCKED_IPS = ["192.168.1.100", "10.0.0.50"]

def before_request(method, path, headers, body):
    ip = headers.get("X-Forwarded-For", "")
    if ip in BLOCKED_IPS:
        return {"status": 403, "text": "Access denied"}
    return None
```
