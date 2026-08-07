# Deployment Guide

## Vercel (recommended)

### vercel.json

```json
{
  "buildCommand": "pip install --break-system-packages tw-framework && python -m tw_framework.cli build --prod",
  "outputDirectory": "dist"
}
```

### Why each part

- `--break-system-packages` — Vercel's Python is managed by `uv`; bare `pip install` is rejected
- `python -m tw_framework.cli` — the `tw` CLI may not be on PATH; using `python -m` is reliable
- `--prod` — minification, compression, cache-busting

### Steps

1. Push to GitHub
2. Vercel → New Project → Import repo
3. Vercel reads `vercel.json` automatically
4. Deploy — `dist/` is served

### With requirements.txt (alternative)

**requirements.txt:**
```
tw-framework
```

**vercel.json:**
```json
{
  "buildCommand": "pip install --break-system-packages -r requirements.txt && python -m tw_framework.cli build --prod",
  "outputDirectory": "dist"
}
```

## Netlify

### netlify.toml

```toml
[build]
command = "pip install tw-framework && python -m tw_framework.cli build --prod"
publish = "dist"
```

Netlify doesn't use `uv`, so `--break-system-packages` is not needed.

## Cloudflare Pages

- **Build command:** `pip install tw-framework && python -m tw_framework.cli build --prod`
- **Build output directory:** `dist`

## Static Export

```bash
tw export
```

Outputs pure HTML/CSS/JS to `dist/`. Host anywhere: GitHub Pages, S3, Netlify Drop.

## One-Command Deploy

```bash
tw deploy
```

Requires `tw login` first:

```bash
tw login --provider vercel --vercel-token YOUR_TOKEN
```

### Deploy flags

| Flag | Description |
|---|---|
| `--provider` | `vercel`, `netlify`, `cloudflare` |
| `--prod` | Production deployment |
| `--dry-run` | Preview what would deploy |
| `--vercel` | Shortcut for `--provider vercel` |
| `--cloudflare` | Shortcut for `--provider cloudflare` |

## Docker

```bash
tw deploy --provider docker
```

Generates a `Dockerfile` and builds a container.

## GitHub Pages

Enable Pages (Source → GitHub Actions) and push. The included workflow builds and deploys automatically.
