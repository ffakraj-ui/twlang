# Server-side TW scripting APIs (`.twm`)

Is document ka goal yeh hai ki developers pure TWLang API system use karein, bina mixed Python/TW API setup ke.

## 1) Routing rule

Folder: `[home]/api/`

- `[home]/api/route.twm` → `/api`
- `[home]/api/health/route.twm` → `/api/health`
- `[home]/api/auth/login/route.twm` → `/api/auth/login`

Rule:

1. Har endpoint ka file name `route.twm` hoga
2. Folder path hi URL path decide karega
3. API layer me Python handlers supported nahi hain

## 2) Handler functions

`.twm` file me top-level pe **sirf functions** allowed hain (top-level code allowed nahi), so koi bhi module load hote hi auto-run nahi karega.

You can define:

- `async fn get(request) { ... }`
- `async fn post(request) { ... }`
- `fn get(request) { ... }`
- `fn post(request) { ... }`
- `fn put(request) { ... }`
- `fn patch(request) { ... }`
- `fn delete(request) { ... }`
- `fn options(request) { ... }`

Ya phir generic:

- `fn handler(request) { ... }`

## 3) Request object (JS)

Handler ko `request` object milega:

- `request.method` (e.g. `GET`)
- `request.path` (normalized URL path)
- `request.query` (query params; key → value/string/array)
- `request.body` (JSON / form / raw decode; jo TW server ne parse kiya)
- `request.headers`
- `request.cookies`
- `request.env` (server env vars)

Built-in helpers bhi milte hain:

- `http.get(url, options?)`
- `http.post(url, body?, options?)`
- `http.put(url, body?, options?)`
- `http.patch(url, body?, options?)`
- `http.delete(url, options?)`
- `env.KEY`, `env.get("KEY")`, `env.require("KEY")`
- `secrets.KEY`, `secrets.get("KEY")`, `secrets.require("KEY")`
- `pkg.require("firebase-admin")` jaisa project package loader
- `firebase.app()`, `firebase.firestore()`, `firebase.auth()` helpers

`http.*` helpers async hote hain, isliye unke liye `async fn` use karo.

## 4) Response return formats

Handler yeh return kar sakta hai:

### A) Simple string

```tw
fn get(request) {
  return "ok";
}
```

### B) Auto JSON (object)

```tw
fn get(request) {
  return { ok: true, hello: "world" };
}
```

### C) Explicit response object

```tw
fn get(request) {
  return {
    status: 201,
    headers: { "X-Test": "1" },
    json: { ok: true }
  };
}
```

Supported keys:

- `status` (number)
- `headers` (object or `[["K","V"]]`)
- `cookies` (object or `[["name","value"]]`)
- `json` (object/string)
- `text` (string)
- `html` (string)
- `body` + `content_type` (advanced)

### D) Tuple style

```tw
fn get(request) {
  return [{ ok: true }, 200, { "X-Mode": "tuple" }];
}
```

## 5) Run + test

```bash
python3 -m pip install -e . --break-system-packages
tw serve --host 0.0.0.0 --port 8787
```

Example:

File: `[home]/api/math/route.twm`

```bash
curl "http://localhost:8787/api/math?a=1&b=2"
```

## 6) `package.json` dependencies

Ab starter `package.json` me `dependencies` aur `devDependencies` blocks scaffold hote hain, to user direct npm packages add kar sakta hai.

Example:

```json
{
  "dependencies": {
    "firebase-admin": "^13.8.0",
    "google-play-scraper": "^9.2.0",
    "jose": "^6.2.3",
    "jsonwebtoken": "^9.0.3"
  },
  "devDependencies": {
    "@playwright/test": "^1.40.0"
  }
}
```

Uske baad project root me:

```bash
npm install
```

Phir `.twm` handler ke andar:

```tw
async fn post(request) {
  const jwt = pkg.require("jsonwebtoken");
  const token = jwt.sign({ sub: "123" }, secrets.require("JWT_SECRET"));
  return { json: { ok: true, token } };
}
```

## 7) Firebase Admin SDK

Firebase Admin use karne ke liye 2 cheezein chahiye:

1. `firebase-admin` package install
2. credentials env me dena

Supported env inputs:

- `FIREBASE_SERVICE_ACCOUNT_JSON`
- `FIREBASE_SERVICE_ACCOUNT_PATH`
- `FIREBASE_ADMIN_CREDENTIALS_JSON`
- `FIREBASE_ADMIN_CREDENTIALS_PATH`
- `GOOGLE_APPLICATION_CREDENTIALS`
- optional `FIREBASE_PROJECT_ID`

Example:

```tw
async fn get(request) {
  const db = firebase.firestore();
  const snap = await db.collection("users").limit(1).get();
  return {
    json: {
      ok: true,
      count: snap.size
    }
  };
}
```

## Notes

- Is implementation me `.twm` **Node.js** ke through execute hota hai (server-side). Isliye runtime me Node available hona chahiye.
- Built-in `http.*` helpers ke liye Node.js `18+` recommended hai.
- `.twm` handlers trusted server code hain; API layer me ab single convention `route.twm` hi use hota hai.
