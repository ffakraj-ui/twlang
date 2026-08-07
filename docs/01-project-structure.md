# Project Structure

```
my-site/
├── tw.config              # Project configuration
├── package.json
├── vercel.json            # (optional)
├── [home]/                # Source root (literal square brackets)
│   ├── index.tw           # Root entry
│   ├── style.tss          # Global stylesheet
│   ├── pages/             # File-based routes
│   │   ├── index.tw       # → /
│   │   ├── about.tw       # → /about
│   │   └── [slug].tw      # → /:slug (dynamic)
│   ├── components/        # Reusable components
│   ├── layouts/           # Layout templates
│   ├── api/               # API routes (.twm)
│   └── middleware.tw      # Middleware (optional)
├── dist/                  # Build output (auto-generated)
└── .tw/                   # Hidden cache (auto-generated)
```

## Critical Requirements

| Requirement | Why |
|---|---|
| `[home]` with literal brackets | TW looks for exactly `[home]` as source root |
| `tw.config` at root | Project metadata and config |
| `[home]/pages/index.tw` | Root page that renders at `/` |
| `.tw/` in `.gitignore` | Cache directory, should not be committed |

## Common Mistakes

| Mistake | Error | Fix |
|---|---|---|
| Folder named `home` not `[home]` | `TW project root not found` | Rename to `[home]` |
| Missing `tw.config` | `No config file found` | Create `tw.config` |
| Page at `[home]/index.tw` not `pages/index.tw` | Page not found at `/` | Move to `pages/` |
