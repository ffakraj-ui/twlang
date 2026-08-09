# Troubleshooting

## Build Issues

### "TW project root not found"

**Cause:** `[home]` directory missing or named incorrectly.

**Fix:**
```bash
# Check if [home] exists
ls -la [home]/

# If not, rename your source directory
mv home "[home]"
```

### "No config file found"

**Fix:** Create `tw.config` at project root:
```
name: My Site
```

### "Build produces 0 pages"

**Cause:** No `.tw` files in `[home]/`.

**Fix:**
```bash
mkdir -p [home]/pages
# Create index.tw
echo 'page { title "Home" } body { h1 "Hello" }' > [home]/index.tw
```

### Build hangs / is very slow

**Fix:**
```bash
# Clear cache and rebuild
tw clean
tw build --prod --force

# Use parallel workers
tw build --prod --workers 4
```

## Vercel Deployment Issues

### "externally-managed-environment"

**Fix:** Add `--break-system-packages`:
```json
{
  "buildCommand": "pip install --break-system-packages tw-framework && python -m tw_framework.cli build --prod"
}
```

### "tw: command not found"

**Fix:** Use `python -m tw_framework.cli` instead of `tw`.

### CSS/JS 404 in production

**Cause:** Pre-v0.4.3 `--prod` bug — filenames hashed but HTML not updated.

**Fix:** Upgrade to v0.4.3+:
```bash
pip install --upgrade tw-framework
```

## TSS Issues

### CSS value shows as `true`

**Cause:** Multi-line CSS value (pre-v0.4.3 bug).

**Fix:** Upgrade to v0.4.3+, or keep values on one line:
```css
// Wrong (pre-v0.4.3):
background-image:
    linear-gradient(...),
    url(...)

// Right (all versions):
background-image: linear-gradient(...), url(...)
```

### Styles not applying

**Check:**
1. `.tss` file is loaded: `load "@./style/site.tss"`
2. Selector matches element class
3. No syntax errors in `.tss` file
4. Run `tw check [home]/style.tss` for diagnostics

## Component Issues

### "Component not found"

**Check:**
1. File exists: `[home]/components/Hero.tw`
2. Import name matches: `import "Hero"`
3. No file extension in import: `import "Hero"` not `import "Hero.tw"`

### Component renders empty

**Cause:** Component file has no content, or content is in wrong section.

**Fix:** Ensure component has markup:
```tw
// Hero.tw
div {
    class "hero"
    h1 "{title}"
}
```

## Dev Server Issues

### Port 3000 already in use

**Fix:** Use a different port:
```bash
tw dev --port 8080
```

### Live reload not working

**Check:**
1. File is inside `[home]/` directory
2. Not editing files in `dist/` (edit source, not output)
3. Try increasing watch interval:
```
# tw.config
watch_interval: 0.5
```

### "Cannot access /api/* in dev"

**Cause:** `.twm` file not in correct location.

**Fix:** API routes go in `[home]/api/`:
```
[home]/api/hello.twm      → /api/hello
[home]/api/users/route.twm → /api/users
```

## Environment Variable Issues

### "Env var not available in page"

**Cause:** Var not allow-listed in `tw.config`.

**Fix:**
```
env {
  public "MY_VAR"
}
```

### "Missing required env var"

**Cause:** Required env var not set.

**Fix:** Create `.env` file:
```
API_URL=https://api.example.com
JWT_SECRET=your-secret-key
```

## LSP Issues

### "Language server not available" (ACode)

**Check:**
1. `tw-framework` installed: `pip install tw-framework`
2. Python3 path correct: `which python3`
3. Server configured as "Manual binary"
4. Args in JSON array format: `["-m", "tw_framework.lsp_server"]`

### False positive errors

If LSP shows errors that don't match actual problems:

1. Upgrade to v0.4.5+ (fixes `render static` false positives)
2. File-resolution errors (`load "missing.tss"`) are suppressed in LSP
3. Run `tw check <file>` for accurate diagnostics
