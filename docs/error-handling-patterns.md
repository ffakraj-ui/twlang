# Error Handling Patterns

Robust error handling is essential for production TW applications. This guide covers patterns for handling errors at every layer.

## Page-Level Errors

### Fallback Content

Always provide fallback UI when data might be missing:

```tw
let products = load_json "products"

body {
    section {
        class "products"

        if products {
            each products as product {
                ProductCard { props product }
            }
        } else {
            div {
                class "empty-state"
                h2 "No products available"
                p "Check back later for new items."
                a "Browse categories" { href "/categories" }
            }
        }
    }
}
```

### Error Boundaries (Component Level)

Create an `ErrorBoundary` component:

```tw
// ErrorBoundary.tw
let fallback = "Something went wrong."
let error = null

if error {
    div {
        class "error-boundary"
        h2 "Error"
        p "{fallback}"
        button "Retry" { on:click "window.location.reload()" }
    }
} else {
    slot {}
}
```

Usage:

```tw
ErrorBoundary {
    fallback "Failed to load comments."
    CommentsList {}
}
```

## API Error Handling

### Consistent Error Format

Standardize error responses in `.twm` files:

```twm
function error_response(message, status=400, code="BAD_REQUEST"):
    return json_response({
        "success": False,
        "error": {
            "message": message,
            "code": code,
            "status": status
        }
    }, status=status)

function success_response(data, status=200):
    return json_response({
        "success": True,
        "data": data
    }, status=status)
```

### Input Validation

```twm
function create_user(request):
    data = request.json()

    if not data.get("email"):
        return error_response("Email is required", 400, "MISSING_EMAIL")

    if "@" not in data["email"]:
        return error_response("Invalid email format", 400, "INVALID_EMAIL")

    if not data.get("password") or len(data["password"]) < 8:
        return error_response("Password must be at least 8 characters", 400, "WEAK_PASSWORD")

    # Proceed with creation
    user = db.users.create(data)
    return success_response({"id": user.id}, 201)
```

### Try-Catch Patterns

```twm
function fetch_external_data(request):
    try:
        response = http.get("https://api.example.com/data")
        return success_response(response.json())
    except ConnectionError:
        return error_response("Service unavailable", 503, "SERVICE_DOWN")
    except TimeoutError:
        return error_response("Request timed out", 504, "TIMEOUT")
    except Exception as e:
        log_error(e)
        return error_response("Internal error", 500, "INTERNAL_ERROR")
```

## Client-Side Error Handling

### Form Validation

```tw
form {
    class "contact-form"
    on:submit "handleSubmit(event)"

    div {
        class "field"
        label "Email" { for "email" }
        input {
            id "email"
            type "email"
            name "email"
            required "true"
            on:blur "validateEmail(this)"
        }
        span { id "email-error" class "error" }
    }

    button "Send" { type "submit" }
}
```

```twm
// Client-side validation in .twm
function validate_email(request):
    email = request.json().get("email", "")
    if "@" not in email:
        return json_response({"valid": False, "message": "Invalid email"})
    return json_response({"valid": True})
```

### Network Error Recovery

```javascript
// In your .twm or inline script
async function fetchWithRetry(url, options = {}, maxRetries = 3) {
    for (let i = 0; i < maxRetries; i++) {
        try {
            const response = await fetch(url, options);
            if (!response.ok) throw new Error(`HTTP ${response.status}`);
            return await response.json();
        } catch (err) {
            if (i === maxRetries - 1) throw err;
            await new Promise(r => setTimeout(r, 1000 * (i + 1)));
        }
    }
}
```

## Middleware Error Handling

### Global Error Middleware

```tw
// middleware.tw
middleware {
    on_error "handleMiddlewareError"
}
```

```python
# hooks/error_handler.py
def handle_middleware_error(request, error):
    log_error(error)
    return {
        "status": 500,
        "body": json.dumps({"error": "Internal server error"}),
        "headers": {"Content-Type": "application/json"}
    }
```

### Rate Limit Errors

```twm
function rate_limit_handler(request):
    client_ip = request.headers.get("X-Forwarded-For", request.remote_addr)
    if is_rate_limited(client_ip):
        return json_response({
            "error": "Rate limit exceeded",
            "retry_after": 60
        }, status=429, headers={"Retry-After": "60"})
```

## Logging and Monitoring

### Structured Logging

```twm
function log_error(error, context=None):
    log_entry = {
        "timestamp": datetime.utcnow().isoformat(),
        "level": "error",
        "message": str(error),
        "context": context or {},
        "traceback": traceback.format_exc()
    }
    logger.error(json.dumps(log_entry))
```

### Error Tracking Integration

```tw
// In your layout or base page
script {
    window.onerror = function(msg, url, line, col, error) {
        fetch('/api/errors/log', {
            method: 'POST',
            body: JSON.stringify({
                message: msg,
                url: url,
                line: line,
                stack: error?.stack
            })
        });
    };
}
```

## Common Error Codes

| Code | Meaning | HTTP Status |
|------|---------|-------------|
| `TW1000` | Parser error | 500 |
| `TW2404` | Layout not found | 500 |
| `TW2405` | Component not found | 500 |
| `TW3101` | Code generation error | 500 |
| `MISSING_FIELD` | Required field missing | 400 |
| `INVALID_FORMAT` | Format validation failed | 400 |
| `NOT_FOUND` | Resource not found | 404 |
| `UNAUTHORIZED` | Authentication required | 401 |
| `FORBIDDEN` | Permission denied | 403 |
| `RATE_LIMITED` | Too many requests | 429 |

## Best Practices

1. **Fail gracefully**: Never expose stack traces or internal details to users.
2. **Log everything**: Errors without logs are invisible.
3. **Retry with backoff**: Network errors should retry exponentially.
4. **Validate early**: Check inputs at the API boundary.
5. **Use consistent shapes**: All error responses should have the same structure.
6. **Test error paths**: Write tests for failure scenarios, not just success.

## New Error Reference (v0.9.28+)

| Error | Cause | Fix |
|-------|-------|-----|
| `Not a TW project directory` | No `tw.config.json` found | Run `tw create` or `tw init` |
| `Port 8000 busy` | Another process using port | Server auto-increments to 8001+ |
| `Handler load failed` | .twm module syntax error | Check function syntax, use `--debug` |
| `Method GET not allowed` | Missing handler function | Add `fn get(request) { ... }` |
| `Node.js not detected` | Node.js not installed | Install Node.js v18+ |
| `result is not defined` | Invalid response shape | Use `{ status, json }` format |
| `Both index.tw and page.tw found` | Both files in same dir | Delete one — index.tw takes priority |
| `Top-level statements not allowed` | Code outside function in .twm | Move code inside `fn` block |

### Debug Mode

Use `--debug` flag for full Python traceback:

```bash
tw --debug build
tw --debug serve
tw --debug dev
```
