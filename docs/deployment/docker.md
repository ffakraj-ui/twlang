# Docker

Files to add to your TW project root (next to `tw.config`): `Dockerfile`, `.dockerignore`, `docker-compose.yml`.

## Build and run directly

```bash
docker build -t my-tw-site .
docker run -p 8000:8000 my-tw-site
```

Visit `http://localhost:8000`.

## Or with docker-compose

```bash
docker compose up --build
```

## How it works

- **Build stage** — installs `tw-framework`, copies your project, runs `tw build` to produce `dist/`.
- **Runtime stage** — a clean image with just the built output and `tw-framework` installed, running `tw serve --no-build` (verified: this starts the production server, serving `dist/` and handling SSR/API routes, on `0.0.0.0:8000`).

## Environment variables

| Variable | Default | Purpose |
|---|---|---|
| `TW_HOST` | `0.0.0.0` | Server bind address |
| `--port` | `8000` | Server port |

Change the port mapping in `docker run -p <host-port>:8000` or in `docker-compose.yml` if you need a different external port.
