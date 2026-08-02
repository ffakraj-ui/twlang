# `/api/echo` API

Is doc ka goal yeh batana hai ki TWLang me folder-based `route.twm` API kaise likhte hain.

## Endpoint

- `GET/POST/PUT/PATCH/DELETE/OPTIONS /api/echo`

## 1) `route.twm` file

File: `[home]/api/echo/route.twm`

Minimal example:

```tw
fn post(request) {
  return {
    status: 201,
    json: {
      ok: true,
      method: request.method,
      path: request.path,
      query: request.query || {},
      headers: request.headers || {},
      cookies: request.cookies || {},
      body: request.body || {}
    }
  };
}
```

### Interpolation (dynamic values)

- TW me interpolation `{expr}` se hoti hai.
- API context me `request` object available hota hai:
  - `request.method`, `request.path`
  - `request.query` (parsed query params)
  - `request.body` (JSON / form / raw body decode)
  - `request.headers`, `request.cookies`

## 2) Request object

`request` object me yeh values available hoti hain:

- `request.method`, `request.path`
- `request.query`
- `request.body`
- `request.headers`
- `request.cookies`
- `request.env`

## 3) Run + test

Run:

```bash
python3 -m pip install -e . --break-system-packages
tw serve --host 0.0.0.0 --port 8787
```

### Quick tests

```bash
curl http://localhost:8787/api/echo
```

```bash
curl -X POST http://localhost:8787/api/echo \
  -H "Content-Type: application/json" \
  -d '{"name":"demo","env":"test"}'
```

## 4) Kab use karein?

- `route.twm` quick mocks, CRUD, validation, auth checks, headers-cookies inspection, aur dynamic logic sab handle kar sakta hai.
- Echo endpoint mixed request debugging ke liye useful hai.
