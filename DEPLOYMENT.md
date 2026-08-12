# TW Framework — Deployment

## Zero-Config Deployment

```bash
tw deploy --provider vercel --prod
tw deploy --provider netlify --prod
tw deploy --provider cloudflare --prod
```

Use `--dry-run` to preview deployment config without deploying.

## Providers

| Provider | Command | Auto-Generated Config |
|----------|---------|----------------------|
| Vercel | `tw deploy --provider vercel` | `vercel.json` with build command and routes |
| Netlify | `tw deploy --provider netlify` | `netlify.toml` with build and redirects |
| Cloudflare | `tw deploy --provider cloudflare` | `_redirects` and headers |
| GitHub Pages | `tw deploy --provider github-pages` | `.nojekyll` and base path |
| Docker | `tw deploy --provider docker` | `Dockerfile` with Python runtime |
| Local | `tw deploy --provider local` | Serves from `dist/` |

## Vercel Deployment

```bash
tw deploy --provider vercel --prod
```

Generated `vercel.json`:
```json
{
  "buildCommand": "pip install --break-system-packages tw-framework && python -m tw_framework.cli build --prod",
  "outputDirectory": "dist",
  "routes": [...]
}
```

Note: Vercel uses `uv`-managed Python, so `--break-system-packages` is required.

## Netlify Deployment

```bash
tw deploy --provider netlify --prod
```

Generated `netlify.toml`:
```toml
[build]
  command = "pip install tw-framework && python -m tw_framework.cli build --prod"
  publish = "dist"
```

## Docker Deployment

```bash
tw deploy --provider docker
```

Generated `Dockerfile` uses Python 3.12-slim, installs tw-framework, builds the project, and runs the production server on port 8000.

## Production Server

```bash
tw serve --host 0.0.0.0 --port 8000
```

Features:
- SSR for `render server` and `render edge` pages
- Static file serving from `dist/` with ETag and Cache-Control
- Brotli/gzip pre-compressed file negotiation
- API route execution (Node.js, Edge V8, Python, WASM)
- Middleware chain execution
- Health check at `/__tw/health`
- Graceful SIGTERM/SIGINT shutdown
- SSR cache (in-memory LRU or Redis via `TW_REDIS_URL`)

## Environment Variables for Production

| Variable | Default | Description |
|----------|---------|-------------|
| `TW_REDIS_URL` | — | Redis URL for distributed SSR cache |
| `TW_MAX_FETCH_PASSES` | 10 | Max fetch calls per Edge V8 request |
| `TW_SSR_CACHE_MAX` | 512 | Max SSR cache entries |
| `TW_AST_CACHE_MAX` | 128 | Max AST cache entries |
| `TW_AST_CACHE_TTL` | 300 | AST cache TTL in seconds |
| `TW_MAX_BODY_SIZE` | 10MB | Max request body size |
