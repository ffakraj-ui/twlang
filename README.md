# TW Framework

TW is a custom language + framework for building websites with a Next.js‑like developer experience.

## Zero‑Config Deployment

1. Create a GitHub repository with your TW project (containing `tw.config`, `pages/`, `components/`, `public/`).
2. Connect the repository to Vercel or Netlify.
3. The platform automatically detects `tw.config` and runs `tw build`.
4. Your site goes live – no terminal commands required.

## Quick Start

```bash
# Create a new project
tw init my-site
cd my-site

# Development server
tw dev

# Production build
tw build

# Preview the build
tw preview
```

## CLI Commands

| Command | Description |
|---------|-------------|
| `tw init [name]` | Create a new TW project in the current directory |
| `tw dev` | Start the development server with live reload |
| `tw build` | Generate a production build |
| `tw preview` | Preview the built output |
| `tw export` | Generate a static export |
| `tw deploy` | Build and deploy to a hosting provider |
| `tw doctor` | Run project health checks and deployment compatibility |
| `tw ast file.tw` | Print the AST JSON for a TW source file |
| `tw ir file.tw` | Print the IR JSON for a TW source file |
| `tw run file.tw` | Interpret a TW file and output HTML |
| `tw check file.tw` | Print diagnostics for a TW file |
| `tw tokens file.tw` | Print the token stream JSON for a TW source file |
| `tw clean` | Clean dist and hidden cache folders |
| `tw info` | Show a project summary |
| `tw login` | Save deploy provider configuration |

## Deployment Metadata

After a build, the file `dist/tw.deploy.json` is automatically generated. It contains:

```json
{
  "framework": "tw",
  "version": "1.0.0",
  "build": "tw build",
  "output": "dist",
  "runtime": "ssr"
}
```

Deployment platforms can read this file to detect the framework and configure the build.

## Adapters

TW Framework includes built‑in adapters for Vercel and Netlify. They provide:

- Framework detection (`detect()` function)
- Automatic generation of `vercel.json` / `netlify.toml` when missing
- Build command, output directory, install command, and SSR handling

## Documentation

- [Getting Started](docs/getting-started.md)
- [Deployment to Vercel](docs/deployment/vercel.md)
- [Deployment to Netlify](docs/deployment/netlify.md)

## Testing

```bash
python3 -m unittest discover -s tests -q
python3 run_tests.py
```

## Debug Flags

- `TW_WARN_LITERAL_PARSE=1` – warn when literal parsing falls back to string
- `TW_STRICT_EVAL=1` – re‑raise runtime expression errors instead of warning

These flags are mainly useful while debugging parser/runtime edge cases or tightening CI checks around expression handling.
