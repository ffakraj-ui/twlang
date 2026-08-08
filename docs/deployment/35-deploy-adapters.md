# Deploy Adapters

TW Framework has built-in adapters for Vercel, Netlify, and Cloudflare.

## Vercel Adapter

Generates `vercel.json` and configures output for Vercel:

```bash
tw build --prod --adapter vercel
```

Or use `vercel.json` directly:

```json
{
  "buildCommand": "pip install --break-system-packages tw-framework && python -m tw_framework.cli build --prod",
  "outputDirectory": "dist"
}
```

### Vercel Functions

For API routes, TW generates Vercel serverless functions in `dist/api/`:

```
dist/
├── api/
│   ├── hello.js          → /api/hello (serverless function)
│   └── users/
│       └── [id].js       → /api/users/:id
├── index.html
└── _tw/
```

### Vercel-specific notes

- Python managed by `uv` → need `--break-system-packages`
- `tw` CLI not on PATH → use `python -m tw_framework.cli`
- Static files served from `dist/`
- API routes deployed as serverless functions

## Netlify Adapter

```bash
tw build --prod --adapter netlify
```

Generates `netlify.toml`:

```toml
[build]
command = "pip install tw-framework && python -m tw_framework.cli build --prod"
publish = "dist"

[[redirects]]
from = "/api/*"
to = "/.netlify/functions/:splat"
status = 200
```

### Netlify Functions

API routes become Netlify functions:

```
dist/
├── .netlify/
│   └── functions/
│       ├── hello.js
│       └── users.js
├── index.html
└── _tw/
```

## Cloudflare Adapter

```bash
tw build --prod --adapter cloudflare
```

Generates Cloudflare Pages configuration:

```
dist/
├── functions/
│   └── api/
│       ├── hello.js
│       └── users.js
├── index.html
└── _tw/
```

Cloudflare Pages uses Workers for API routes.

## Deploy Metadata

TW generates `dist/tw.deploy.json` with deployment metadata:

```json
{
    "framework": "tw",
    "version": "0.4.5",
    "build_time": "2024-01-15T10:30:00Z",
    "pages": 10,
    "api_routes": 5,
    "adapter": "vercel"
}
```

## Choosing an Adapter

| Provider | Best for | API routes | Static |
|---|---|---|---|
| Vercel | General purpose, Next.js alternative | Serverless functions | ✅ |
| Netlify | Static sites + forms | Netlify functions | ✅ |
| Cloudflare | Global edge, Workers | Workers | ✅ |
| Static export | GitHub Pages, S3 | ❌ | ✅ |
