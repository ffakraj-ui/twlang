# Environment Variables

## Security Model

TW Framework has a strict environment variable policy:

- **All env vars are server-only by default**
- Only vars explicitly allow-listed reach page render context
- This prevents accidental secret leakage into generated HTML

## Allow-listing Variables

In `tw.config`:

```
env {
  public "API_URL"
  public "SITE_NAME"
  public "GA_TRACKING_ID"
}
```

Only these variables are available in `.tw` page rendering:

```tw
let apiUrl = "{API_URL}"

body {
    h1 "{SITE_NAME}"
    script {
        // GA_TRACKING_ID is available
        console.log("{GA_TRACKING_ID}");
    }
}
```

## .env File

Create a `.env` file at the project root:

```
API_URL=https://api.example.com
SITE_NAME=My Site
JWT_SECRET=supersecret
DATABASE_URL=postgres://...
```

### .env.local

For local development, create `.env.local`:

```
API_URL=http://localhost:3000/api
DEBUG=true
```

### Comments in .env

```
API_URL=https://api.example.com  # API endpoint
SECRET_KEY=abc123               # Don't share this
```

## Env Type Validation

TW can validate env var types in `tw.config`:

```
env {
  public "API_URL"
  public "MAX_ITEMS"

  schema {
    API_URL { type "string" required true }
    MAX_ITEMS { type "number" default "10" }
    PORT { type "number" default "3000" }
  }
}
```

### Types

| Type | Validation |
|---|---|
| `string` | Any string value |
| `number` | Must be numeric |
| `bool` | `true`, `false`, `1`, `0` |

### Required vs Optional

```
schema {
    API_KEY { type "string" required true }    // Build fails if missing
    CACHE_TTL { type "number" default "60" }   // Optional, uses default
}
```

## Loading Order

1. `.env.local` (if exists)
2. `.env`
3. `os.environ` (system env vars)

Later files override earlier ones.

## In TWM Modules

Server-side `.twm` modules have access to ALL env vars (not just public ones):

```js
// [home]/api/data.twm
export function GET() {
    const dbUrl = process.env.DATABASE_URL;  // Available server-side
    const apiKey = process.env.API_KEY;      // Available server-side
    return { status: 200, json: { data: [] } };
}
```

## Warning: Missing Env Vars

If a required env var is missing, `tw doctor` reports it:

```
⚠ Missing required env var: API_KEY
⚠ Missing required env var: DATABASE_URL
```

Build will fail with `--strict` flag.
