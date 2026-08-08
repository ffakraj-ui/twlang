# Deployment Troubleshooting

## Vercel

### "externally-managed-environment"

Error: This environment is externally managed

Fix: Add --break-system-packages:
```json
{
  "buildCommand": "pip install --break-system-packages tw-framework && python -m tw_framework.cli build --prod"
}
```

### "tw: command not found"

Fix: Use python -m tw_framework.cli instead of tw.

### CSS/JS 404 errors

Cause: Pre-v0.4.3 bug - filenames hashed but HTML not updated.

Fix: pip install --upgrade tw-framework

### Build succeeds but page is blank

Check:
1. outputDirectory is dist in vercel.json
2. [home]/pages/index.tw exists
3. Page has body {} block with content
4. Layout exists if specified

### API routes return 404

Check:
1. .twm files in [home]/api/ directory
2. File named route.twm in subdirectories
3. Vercel functions generated in dist/api/

## Netlify

### "Publish directory not found"

Fix: Set publish to dist in netlify.toml.

## Cloudflare Pages

### "Build command failed"

Check:
1. Python 3.9+ available
2. pip install tw-framework succeeds
3. Build output is dist

## GitHub Pages

### "Assets not loading (404)"

Cause: GitHub Pages serves from subpath (/repo-name/).

Fix: Use relative paths or configure base URL.

## General

### "ModuleNotFoundError: No module named 'tw_framework'"

Fix: pip install tw-framework in build environment.

### "RuntimeError: TW project root not found"

Cause: [home] directory not in deployed code.

Fix: Ensure [home]/ is committed to git (not in .gitignore).

### Build timeout

Fix:
1. Reduce page count
2. Use --workers 4 for parallel compilation
3. Clear cache: tw clean
