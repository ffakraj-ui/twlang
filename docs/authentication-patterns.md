# Authentication Patterns

Implement secure user authentication in TW Framework.

## Session-Based Auth

Store session IDs in cookies. Best for traditional server-rendered apps.

### Login Flow

```twm
# [home]/api/auth/login/route.twm
import secrets
import hashlib
from db.connection import get_db

SESSIONS = {}

def hash_password(password):
    return hashlib.pbkdf2_hmac('sha256', password.encode(), b'salt', 100000).hex()

function post(request):
    data = request.json()
    email = data.get("email")
    password = data.get("password")

    conn = get_db()
    cursor = conn.execute("SELECT id, password_hash FROM users WHERE email = ?", (email,))
    user = cursor.fetchone()
    conn.close()

    if not user or hash_password(password) != user["password_hash"]:
        return json_response({"error": "Invalid credentials"}, status=401)

    session_id = secrets.token_urlsafe(32)
    SESSIONS[session_id] = {"user_id": user["id"], "email": email}

    response = json_response({"success": True})
    response.set_cookie("session_id", session_id, httponly=True, secure=True, samesite="Lax")
    return response
```

### Protected Route

```twm
# [home]/api/profile/route.twm
function get(request):
    session_id = request.cookies.get("session_id")
    session = SESSIONS.get(session_id)

    if not session:
        return json_response({"error": "Unauthorized"}, status=401)

    conn = get_db()
    cursor = conn.execute("SELECT id, email, name FROM users WHERE id = ?", (session["user_id"],))
    user = cursor.fetchone()
    conn.close()

    return json_response(dict(user))
```

### Logout

```twm
function post(request):
    session_id = request.cookies.get("session_id")
    SESSIONS.pop(session_id, None)

    response = json_response({"success": True})
    response.delete_cookie("session_id")
    return response
```

## JWT Auth

Stateless authentication using JSON Web Tokens.

### Generate Token

```python
# [home]/auth/jwt.py
import jwt
import datetime
import os

SECRET = os.environ.get("JWT_SECRET", "change-me-in-production")

def create_token(user_id, email, expires_hours=24):
    payload = {
        "user_id": user_id,
        "email": email,
        "exp": datetime.datetime.utcnow() + datetime.timedelta(hours=expires_hours),
        "iat": datetime.datetime.utcnow()
    }
    return jwt.encode(payload, SECRET, algorithm="HS256")

def verify_token(token):
    try:
        return jwt.decode(token, SECRET, algorithms=["HS256"])
    except jwt.ExpiredSignatureError:
        return None
    except jwt.InvalidTokenError:
        return None
```

### API Usage

```twm
# [home]/api/auth/jwt-login/route.twm
from auth.jwt import create_token
from db.connection import get_db

function post(request):
    data = request.json()
    conn = get_db()
    cursor = conn.execute("SELECT id, password_hash FROM users WHERE email = ?", (data["email"],))
    user = cursor.fetchone()
    conn.close()

    if not user or not verify_password(data["password"], user["password_hash"]):
        return json_response({"error": "Invalid credentials"}, status=401)

    token = create_token(user["id"], data["email"])
    return json_response({"token": token})
```

```twm
# [home]/api/user/route.twm
from auth.jwt import verify_token

function get(request):
    auth_header = request.headers.get("Authorization", "")
    if not auth_header.startswith("Bearer "):
        return json_response({"error": "Missing token"}, status=401)

    token = auth_header[7:]
    payload = verify_token(token)

    if not payload:
        return json_response({"error": "Invalid or expired token"}, status=401)

    return json_response({"user_id": payload["user_id"], "email": payload["email"]})
```

## Middleware Auth

Protect entire routes with middleware:

```tw
# middleware.tw
middleware {
    auth "session"
    exclude "/login", "/register", "/api/auth/*"
}
```

```python
# hooks/auth_middleware.py
from auth.jwt import verify_token

def auth_middleware(request):
    public_paths = ["/login", "/register", "/api/auth/login", "/api/auth/register"]
    if any(request.path.startswith(p) for p in public_paths):
        return None  # Allow

    auth_header = request.headers.get("Authorization", "")
    if not auth_header.startswith("Bearer "):
        return {"status": 401, "body": '{"error": "Unauthorized"}'}

    token = auth_header[7:]
    payload = verify_token(token)

    if not payload:
        return {"status": 401, "body": '{"error": "Invalid token"}'}

    request.user = payload
    return None  # Continue
```

## Password Security

Never store plain-text passwords. Use `bcrypt` or `argon2`:

```bash
pip install bcrypt
```

```python
import bcrypt

def hash_password(password):
    return bcrypt.hashpw(password.encode(), bcrypt.gensalt()).decode()

def verify_password(password, hashed):
    return bcrypt.checkpw(password.encode(), hashed.encode())
```

## OAuth Integration

### Google OAuth

```twm
# [home]/api/auth/google/route.twm
function get(request):
    redirect_url = (
        "https://accounts.google.com/o/oauth2/v2/auth"
        "?client_id=" + env("GOOGLE_CLIENT_ID")
        + "&redirect_uri=" + request.base_url + "/callback"
        + "&response_type=code"
        + "&scope=openid email profile"
    )
    return redirect(redirect_url)

function get_callback(request):
    code = request.args.get("code")
    # Exchange code for token, create/update user, set session
    return redirect("/dashboard")
```

## Best Practices

1. **Use HTTPS only**: Never transmit tokens over HTTP.
2. **Short expiry**: JWT should expire in hours, not days.
3. **HttpOnly cookies**: Prevent XSS from stealing sessions.
4. **Rate limit login**: Prevent brute force attacks.
5. **Validate all inputs**: Email format, password strength.
6. **Log auth events**: Track logins, failures, password changes.
