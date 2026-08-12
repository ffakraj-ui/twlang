# CLI Command Reference

## tw create

```bash
tw create <name> [--directory <dir>]
```

Scaffolds a new TW project with `[home]/`, `tw.config`, and starter pages.

## tw init

```bash
tw init
```

Creates a TW project in the current directory (instead of a new subfolder).

## tw dev

```bash
tw dev [--host <addr>] [--port <num>] [--no-open]
```

Starts the live-reloading dev server.

- `--host` — bind address (default: 127.0.0.1)
- `--port` — port (default: 3000)
- `--no-open` — don't auto-open browser

## tw build

```bash
tw build [options]
```

| Flag | Description |
|---|---|
| `--prod` | Minified, compressed, cache-busted build |
| `--dev` | Development build (no optimization) |
| `--out-dir <dir>` | Output directory (default: dist) |
| `--force` | Force full rebuild (skip cache) |
| `--clean` | Clean output before build |
| `--watch` | Rebuild on file change |
| `--analyze` | Generate build analysis report |
| `--no-minify` | Skip minification |
| `--strict` | Treat warnings as errors |
| `--fail-on-warnings` | Exit non-zero on warnings |
| `--adapter <name>` | Deployment adapter (vercel/netlify/cloudflare) |
| `--report` | Generate build report |
| `--workers <n>` | Parallel worker count |
| `--debug` | Verbose debug output |

## tw export

```bash
tw export [--out-dir <dir>] [--workers <n>] [--no-minify] [--fail-on-warnings]
```

Static export — generates pure HTML/CSS/JS. No server-side code.

## tw preview

```bash
tw preview [--host <addr>] [--port <num>] [--no-open] [--no-build] [--no-minify] [--workers <n>]
```

Previews the production build locally.

- `--no-build` — use existing dist/ without rebuilding

## tw deploy

```bash
tw deploy [--provider <name>] [--prod] [--dry-run] [--vercel] [--cloudflare] [--out-dir <dir>]
```

Builds and deploys in one command.

- `--provider` — `vercel`, `netlify`, or `cloudflare`
- `--prod` — production deployment
- `--dry-run` — show what would be deployed without actually deploying
- `--vercel` — shortcut for `--provider vercel`
- `--cloudflare` — shortcut for `--provider cloudflare`

## tw doctor

```bash
tw doctor
```

Runs health checks: config validation, env schema, port availability, file structure.

## tw check

```bash
tw check <file> [--out <path>] [--include-ast] [--include-ir]
```

Prints diagnostics for a `.tw` file.

- `--include-ast` — show AST JSON
- `--include-ir` — show intermediate representation

## tw info

```bash
tw info
```

Shows project summary: pages, components, layouts, API routes, dependencies.

## tw ast

```bash
tw ast <file> [--out <path>] [--diagnostics]
```

Prints the AST JSON for a TW source file.

## tw ir

```bash
tw ir <file> [--out <path>] [--diagnostics]
```

Prints the intermediate representation (IR) for a source file.

## tw run

```bash
tw run <file> [--out <path>] [--diagnostics]
```

Compiles and runs a single TW file, showing output.

## tw tokens

```bash
tw tokens <file> [--out <path>]
```

Prints the lexer tokens for a source file.

## tw clean

```bash
tw clean
```

Removes `dist/` and `.tw/` cache directories.

## tw serve

```bash
tw serve [--host <addr>] [--port <num>] [--out-dir <dir>] [--no-build] [--no-minify] [--fail-on-warnings]
```

Builds (if needed) and serves the production build. Like `tw preview` but can also run API routes.

## tw login

```bash
tw login [--provider <name>] [--vercel-token <token>]
```

Authenticates with a deployment provider.

- `--vercel-token` — provide Vercel API token directly
