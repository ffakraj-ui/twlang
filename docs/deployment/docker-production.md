# Docker Production

Containerize and deploy TW Framework applications with Docker.

## Basic Dockerfile

```dockerfile
# Dockerfile
FROM python:3.11-slim

WORKDIR /app

# Install system dependencies
RUN apt-get update && apt-get install -y \
    gcc \
    && rm -rf /var/lib/apt/lists/*

# Install Python dependencies
COPY requirements.txt .
RUN pip install --no-cache-dir -r requirements.txt

# Copy project files
COPY . .

# Build the site
RUN tw build --prod

# Expose port
EXPOSE 3000

# Run production server
CMD ["tw", "serve", "--port", "3000", "--prod"]
```

## Multi-Stage Build

```dockerfile
# Dockerfile (multi-stage)
# Stage 1: Build
FROM python:3.11-slim AS builder

WORKDIR /app

RUN apt-get update && apt-get install -y gcc && rm -rf /var/lib/apt/lists/*

COPY requirements.txt .
RUN pip install --no-cache-dir -r requirements.txt

COPY . .
RUN tw build --prod

# Stage 2: Runtime
FROM python:3.11-slim

WORKDIR /app

# Only install runtime dependencies
COPY requirements.txt .
RUN pip install --no-cache-dir -r requirements.txt

# Copy built assets from builder
COPY --from=builder /app/dist ./dist
COPY --from=builder /app/tw.config ./

EXPOSE 3000

CMD ["tw", "serve", "--port", "3000", "--prod"]
```

## Docker Compose

```yaml
# docker-compose.yml
version: '3.8'

services:
  app:
    build: .
    ports:
      - "3000:3000"
    environment:
      - ENVIRONMENT=production
      - DATABASE_URL=postgresql://user:pass@db:5432/tw_app
      - REDIS_URL=redis://redis:6379
    depends_on:
      - db
      - redis
    restart: unless-stopped
    healthcheck:
      test: ["CMD", "curl", "-f", "http://localhost:3000/api/health"]
      interval: 30s
      timeout: 10s
      retries: 3

  db:
    image: postgres:15-alpine
    environment:
      POSTGRES_USER: user
      POSTGRES_PASSWORD: pass
      POSTGRES_DB: tw_app
    volumes:
      - postgres_data:/var/lib/postgresql/data
    restart: unless-stopped

  redis:
    image: redis:7-alpine
    restart: unless-stopped

  nginx:
    image: nginx:alpine
    ports:
      - "80:80"
      - "443:443"
    volumes:
      - ./nginx.conf:/etc/nginx/nginx.conf:ro
      - ./ssl:/etc/nginx/ssl:ro
    depends_on:
      - app
    restart: unless-stopped

volumes:
  postgres_data:
```

## Nginx Configuration

```nginx
# nginx.conf
events {
    worker_connections 1024;
}

http {
    include /etc/nginx/mime.types;
    default_type application/octet-stream;

    # Gzip compression
    gzip on;
    gzip_types text/plain text/css application/json application/javascript;

    upstream app {
        server app:3000;
    }

    server {
        listen 80;
        server_name example.com;

        # Redirect to HTTPS
        return 301 https://$server_name$request_uri;
    }

    server {
        listen 443 ssl http2;
        server_name example.com;

        ssl_certificate /etc/nginx/ssl/cert.pem;
        ssl_certificate_key /etc/nginx/ssl/key.pem;
        ssl_protocols TLSv1.2 TLSv1.3;

        # Security headers
        add_header X-Frame-Options "SAMEORIGIN" always;
        add_header X-Content-Type-Options "nosniff" always;
        add_header X-XSS-Protection "1; mode=block" always;
        add_header Referrer-Policy "strict-origin-when-cross-origin" always;

        # Static assets (cache 1 year)
        location ~* \.(css|js|png|jpg|jpeg|webp|avif|woff2|svg)$ {
            proxy_pass http://app;
            expires 1y;
            add_header Cache-Control "public, immutable";
        }

        # HTML pages (cache 1 hour)
        location ~* \.html$ {
            proxy_pass http://app;
            expires 1h;
            add_header Cache-Control "public, must-revalidate";
        }

        # API routes (no cache)
        location /api/ {
            proxy_pass http://app;
            proxy_set_header Host $host;
            proxy_set_header X-Real-IP $remote_addr;
            proxy_set_header X-Forwarded-For $proxy_add_x_forwarded_for;
            proxy_set_header X-Forwarded-Proto $scheme;
        }

        # Everything else
        location / {
            proxy_pass http://app;
            proxy_set_header Host $host;
            proxy_set_header X-Real-IP $remote_addr;
        }
    }
}
```

## Kubernetes Deployment

```yaml
# k8s/deployment.yaml
apiVersion: apps/v1
kind: Deployment
metadata:
  name: tw-app
  labels:
    app: tw-app
spec:
  replicas: 3
  selector:
    matchLabels:
      app: tw-app
  template:
    metadata:
      labels:
        app: tw-app
    spec:
      containers:
        - name: tw-app
          image: your-registry/tw-app:latest
          ports:
            - containerPort: 3000
          env:
            - name: ENVIRONMENT
              value: "production"
            - name: DATABASE_URL
              valueFrom:
                secretKeyRef:
                  name: app-secrets
                  key: database-url
          resources:
            requests:
              memory: "256Mi"
              cpu: "250m"
            limits:
              memory: "512Mi"
              cpu: "500m"
          livenessProbe:
            httpGet:
              path: /api/health
              port: 3000
            initialDelaySeconds: 10
            periodSeconds: 30
          readinessProbe:
            httpGet:
              path: /api/health
              port: 3000
            initialDelaySeconds: 5
            periodSeconds: 10
---
apiVersion: v1
kind: Service
metadata:
  name: tw-app-service
spec:
  selector:
    app: tw-app
  ports:
    - port: 80
      targetPort: 3000
  type: ClusterIP
---
apiVersion: networking.k8s.io/v1
kind: Ingress
metadata:
  name: tw-app-ingress
  annotations:
    kubernetes.io/ingress.class: nginx
    cert-manager.io/cluster-issuer: letsencrypt
spec:
  tls:
    - hosts:
        - example.com
      secretName: tw-app-tls
  rules:
    - host: example.com
      http:
        paths:
          - path: /
            pathType: Prefix
            backend:
              service:
                name: tw-app-service
                port:
                  number: 80
```

## Building and Running

```bash
# Build image
docker build -t tw-app:latest .

# Run container
docker run -p 3000:3000 -e ENVIRONMENT=production tw-app:latest

# Run with compose
docker-compose up -d

# View logs
docker-compose logs -f app

# Scale app
docker-compose up -d --scale app=3
```

## Best Practices

1. **Use non-root user**: Create a dedicated user in Dockerfile.
2. **Minimize layers**: Combine RUN commands.
3. **Use .dockerignore**: Exclude unnecessary files.
4. **Scan for vulnerabilities**: Use `docker scan` or Trivy.
5. **Pin base image versions**: Don't use `latest`.
6. **Health checks**: Ensure containers report their status.
7. **Resource limits**: Prevent runaway containers.
8. **Secrets management**: Use Docker secrets or Kubernetes secrets.
