# TWM (TW Modules) Syntax and Patterns

Complete guide to `.twm` server module syntax, routing, request handling, and common errors.

## File Structure

```
[home]/
  api/
    users/
      route.twm          # GET /api/users, POST /api/users
    users/[id]/
      route.twm          # GET /api/users/:id
    products/
      route.twm
```

## Basic Route Handler

```twm
// [home]/api/hello/route.twm
function get(request):
    return json_response({"message": "Hello, World!"})
```

## HTTP Methods

### GET — Read Data

```twm
function get(request):
    page = int(request.args.get("page", 1))
    limit = int(request.args.get("limit", 20))

    posts = db.posts.limit(limit).offset((page - 1) * limit).all()
    total = db.posts.count()

    return json_response({
        "data": posts,
        "pagination": {
            "page": page,
            "limit": limit,
            "total": total,
            "pages": (total + limit - 1) // limit
        }
    })
```

### POST — Create Data

```twm
function post(request):
    data = request.json()

    if not data.get("title"):
        return json_response({"error": "Title is required"}, status=400)

    post_id = db.posts.insert(data)
    return json_response({"id": post_id}, status=201)
```

### PUT — Update Data

```twm
function put(request):
    post_id = request.args.get("id")
    data = request.json()

    existing = db.posts.find_by_id(post_id)
    if not existing:
        return json_response({"error": "Post not found"}, status=404)

    db.posts.update(post_id, data)
    return json_response({"success": True})
```

### DELETE — Remove Data

```twm
function delete(request):
    post_id = request.args.get("id")

    existing = db.posts.find_by_id(post_id)
    if not existing:
        return json_response({"error": "Post not found"}, status=404)

    db.posts.delete(post_id)
    return json_response({"success": True}, status=204)
```

## Request Object

```twm
function get(request):
    # URL parameters
    slug = request.args.get("slug")

    # Query parameters
    page = request.args.get("page", 1)

    # Request body (JSON)
    data = request.json()

    # Form data
    form = request.form()

    # Headers
    auth_header = request.headers.get("Authorization")

    # Method and path
    method = request.method
    path = request.path

    # Client IP
    ip = request.remote_addr

    return json_response({"path": path})
```

### Common Mistake: Wrong Property Access

```twm
// WRONG
function get(request):
    name = request.body.name
```

**Error:** `AttributeError: 'Request' object has no attribute 'body'`

**Fix:** Use `request.json()` or `request.form()`.

```twm
// CORRECT
function get(request):
    data = request.json()
    name = data.get("name")
```

## Response Helpers

```twm
function get(request):
    # Basic JSON
    return json_response({"status": "ok"})

    # With status code
    return json_response({"error": "Not found"}, status=404)

    # With custom headers
    return json_response(
        {"data": []},
        status=200,
        headers={"X-Total-Count": "100"}
    )
```

### HTML Response

```twm
function get(request):
    html = "<h1>Hello</h1>"
    return html_response(html, status=200)
```

### Redirect

```twm
function get(request):
    return redirect("/dashboard", status=302)
```

### Raw Response

```twm
function get(request):
    return Response(
        body="Custom response",
        status=200,
        headers={"Content-Type": "text/plain"}
    )
```

## Error Handling

```twm
function get_data(request):
    try:
        result = fetch_external_api()
        return json_response(result)
    except ConnectionError:
        return json_response({"error": "Service unavailable"}, status=503)
    except TimeoutError:
        return json_response({"error": "Request timed out"}, status=504)
    except Exception as e:
        log_error(e)
        return json_response({"error": "Internal error"}, status=500)
```

## Validation Patterns

```twm
function create_user(request):
    data = request.json()
    errors = []

    email = data.get("email", "").strip()
    if not email:
        errors.append({"field": "email", "message": "Email is required"})
    elif "@" not in email:
        errors.append({"field": "email", "message": "Invalid format"})

    password = data.get("password", "")
    if len(password) < 8:
        errors.append({"field": "password", "message": "Min 8 characters"})

    if errors:
        return json_response({"errors": errors}, status=400)

    user_id = db.users.insert({"email": email})
    return json_response({"id": user_id}, status=201)
```

## File Uploads

```twm
function post_upload(request):
    file = request.files.get("image")

    if not file:
        return json_response({"error": "No file"}, status=400)

    allowed = ["image/jpeg", "image/png", "image/webp"]
    if file.content_type not in allowed:
        return json_response({"error": "Invalid type"}, status=400)

    max_size = 5 * 1024 * 1024
    if len(file.read()) > max_size:
        return json_response({"error": "Too large (max 5MB)"}, status=400)

    filename = secure_filename(file.filename)
    file.save(f"[home]/assets/uploads/{filename}")

    return json_response({"url": f"/assets/uploads/{filename}"})
```

## Common TWM Errors

| Error | Cause | Fix |
|-------|-------|-----|
| `NameError: 'json_response'` | Missing import | Built-in, check TW version |
| `AttributeError: 'dict' object has no attribute 'json'` | Used `.json` not `.json()` | Use `request.json()` |
| `KeyError: 'name'` | Missing dict key | Use `.get()` with default |
| `TypeError: int()` | Passing None to int() | Check value first |
| `500 Internal Server Error` | Unhandled exception | Wrap in try-except |

## Best Practices

1. Always validate input — never trust client data
2. Use consistent response format
3. Return appropriate status codes
4. Log errors but don't expose internals
5. Rate limit public endpoints
6. Sanitize filenames
7. Set content-type headers
