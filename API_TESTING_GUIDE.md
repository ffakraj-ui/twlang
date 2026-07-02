# API Testing Guide

Is project me sample APIs ko clean karke ek hi convention par shift kiya gaya hai: folder-based `route.twm`.

## Run kaise karein

1. `python3 -m pip install -e . --break-system-packages`
2. `tw serve --host 0.0.0.0 --port 8787`
3. Base URL use karo: `http://localhost:8787`

`tw preview` static files ke liye useful hai, lekin API routes test karne ke liye `tw serve` use karo.

## API structure

- Sabhi API files ab `[home]/api/**/route.twm` format me hain
- Example: `[home]/api/users/route.twm` → `/api/users`
- Root listing: `[home]/api/route.twm` → `/api`
- Example detailed doc: `docs/api/echo-api.md`
- Server-side `.twm` scripting doc: `docs/api/twm-api.md`

## Available APIs

| Endpoint | Method | Use |
| --- | --- | --- |
| `/api` | `GET` | Saare testing endpoints ki listing |
| `/api/health` | `GET` | Health check |
| `/api/echo` | `GET, POST, PUT, PATCH, DELETE, OPTIONS` | Request echo aur payload inspect |
| `/api/users` | `GET, POST, PUT, PATCH, DELETE` | CRUD testing |
| `/api/products` | `GET` | Pagination, filter, sort |
| `/api/auth/login` | `POST` | Demo login |
| `/api/auth/profile` | `GET` | Bearer token protected route |
| `/api/forms/contact` | `POST` | Validation testing |
| `/api/meta` | `GET, OPTIONS` | Headers, cookies, trace id, CORS |
| `/api/status` | `GET, POST` | Custom status code response |
| `/api/delay` | `GET` | Delay / timeout simulation |
| `/api/upload` | `POST` | Raw body testing |
| `/api/webhooks/test` | `POST` | Webhook receiver testing |

## Quick test examples

### 1. Health

```bash
curl http://localhost:8787/api/health
```

### 2. Echo JSON

```bash
curl -X POST http://localhost:8787/api/echo \
  -H "Content-Type: application/json" \
  -d '{"name":"demo","env":"test"}'
```

### 3. Users list

```bash
curl http://localhost:8787/api/users
```

### 4. Create user

```bash
curl -X POST http://localhost:8787/api/users \
  -H "Content-Type: application/json" \
  -d '{"name":"Riya","email":"riya@example.com","role":"qa","active":true}'
```

### 5. Update user

```bash
curl -X PATCH http://localhost:8787/api/users \
  -H "Content-Type: application/json" \
  -d '{"id":2,"role":"lead-tester","active":true}'
```

### 6. Delete user

```bash
curl -X DELETE "http://localhost:8787/api/users?id=3"
```

### 7. Filter products

```bash
curl "http://localhost:8787/api/products?category=electronics&page=1&limit=2&sort=price&order=desc"
```

### 8. Login

```bash
curl -X POST http://localhost:8787/api/auth/login \
  -H "Content-Type: application/json" \
  -d '{"username":"admin","password":"password123"}'
```

Demo credentials:

- `admin / password123`
- `tester / test123`

### 9. Protected profile

```bash
curl http://localhost:8787/api/auth/profile \
  -H "Authorization: Bearer test-token-admin"
```

### 10. Form validation

```bash
curl -X POST http://localhost:8787/api/forms/contact \
  -H "Content-Type: application/x-www-form-urlencoded" \
  -d "name=Rahul&email=rahul@example.com&message=Testing contact form"
```

### 11. Headers and cookies

```bash
curl "http://localhost:8787/api/meta?debug=true" \
  -H "X-Test-Trace: qa-run-001" \
  -H "Cookie: theme=dark; session=abc123"
```

### 12. Status code test

```bash
curl "http://localhost:8787/api/status?code=422&message=Validation%20demo"
```

### 13. Delay test

```bash
curl "http://localhost:8787/api/delay?seconds=2"
```

### 14. Raw upload test

```bash
curl -X POST http://localhost:8787/api/upload \
  -H "Content-Type: text/plain" \
  --data-binary "sample raw payload for testing"
```

### 15. Webhook test

```bash
curl -X POST http://localhost:8787/api/webhooks/test \
  -H "Content-Type: application/json" \
  -H "X-Webhook-Event: order.created" \
  -H "X-Signature: demo-signature" \
  -d '{"orderId":"ORD-1001","amount":999}'
```

## Notes

- `users` data `[home]/api/_data/users.json` me persist hoti hai.
- `POST`, `PUT`, `PATCH`, `DELETE` sab directly test kiye ja sakte hain.
- `application/json`, `application/x-www-form-urlencoded`, aur raw text payloads cover kiye gaye hain.
- Legacy `.tw`, `.py`, aur `_py` API variants hata diye gaye hain.
