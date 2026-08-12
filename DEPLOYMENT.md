# TW Framework — Deployment

## Deployment Commands

```bash
tw deploy --provider vercel --prod
tw deploy --provider netlify --prod
tw deploy --provider cloudflare --prod
tw deploy --provider docker
```

Use `--dry-run` to preview deployment config without deploying.

## Providers

| Provider | Command | Generated Config |
|----------|---------|-------------------|
| Vercel | `tw deploy --provider vercel` | vercel.json |
| Netlify | `tw deploy --provider netlify` | netlify.toml |
| Cloudflare | `tw deploy --provider cloudflare` | wrangler.toml |
| Docker | `tw deploy --provider docker` | Dockerfile, docker-compose.yml |

## Infrastructure as Code

Generate Terraform configuration for AWS:

```bash
tw infrastructure --provider aws --region ap-south-1
```

This generates:
- `infrastructure/main.tf` — VPC, ECS, ECR, ALB, S3, CloudFront, WAF, Redis
- Complete AWS infrastructure setup

## Health Checks

- `/health/live` — Liveness probe
- `/health/ready` — Readiness probe
- `/health` — Full health report

## Serving

```bash
tw serve --port 3000
```

If port 3000 is busy, the server automatically tries 3001, 3002, etc. (up to 10 retries).
