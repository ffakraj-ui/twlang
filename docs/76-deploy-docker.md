# Docker Deployment

## Manual Dockerfile

```dockerfile
FROM python:3.12-slim

WORKDIR /app
RUN pip install tw-framework
COPY . .
RUN python -m tw_framework.cli build --prod

EXPOSE 3000
CMD ["python", "-m", "tw_framework.cli", "serve", "--host", "0.0.0.0", "--port", "3000"]
```

## Docker Compose

```yaml
version: '3.8'
services:
  web:
    build: .
    ports:
      - "3000:3000"
    environment:
      - API_URL=https://api.example.com
      - JWT_SECRET=your-secret
```

## Multi-Stage Build

```dockerfile
FROM python:3.12-slim AS builder
WORKDIR /app
RUN pip install tw-framework
COPY . .
RUN python -m tw_framework.cli build --prod

FROM python:3.12-slim
WORKDIR /app
RUN pip install tw-framework
COPY --from=builder /app/dist ./dist
COPY --from=builder /app/tw.config .
COPY --from=builder /app/[home] ./[home]
EXPOSE 3000
CMD ["python", "-m", "tw_framework.cli", "serve", "--host", "0.0.0.0", "--port", "3000"]
```

## Health Check

```dockerfile
HEALTHCHECK --interval=30s --timeout=3s --retries=3 \
  CMD curl -f http://localhost:3000/api/health || exit 1
```
