# TW Framework — Deployment

## Deployment Commands

```bash
tw deploy --provider vercel --prod
tw deploy --provider netlify --prod
tw deploy --provider cloudflare --prod
```

Use `--dry-run` to preview deployment config without deploying.

## Providers

| Provider | Command | Generated Config |
|----------|---------|-------------------|
| Vercel | `tw deploy --provider vercel` | vercel.json |
| Netlify | `tw deploy --provider netlify` | netlify.toml |
| Cloudflare | `tw deploy --provider cloudflare` | wrangler.toml |
| Docker | `tw deploy --provider docker` | Dockerfile, docker-compose.yml |

## Health Checks

- `/health/live` — Liveness probe
- `/health/ready` — Readiness probe
- `/health` — Full health report
