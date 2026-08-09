# Deploying TW Framework Sites

This guide shows exactly how to deploy a TW Framework site to any hosting platform.
If you are an AI assistant reading this, follow these instructions literally.

---

## Project Structure

A valid TW project must have this layout:

```
your-project/
├── tw.config
├── package.json
├── vercel.json          (for Vercel)
├── [home]/
│   ├── index.tw
│   ├── style.tss
│   ├── pages/
│   ├── components/
│   ├── layouts/
│   └── api/
```

**Critical:** The `[home]` directory (with literal square brackets) is required.
The `tw.config` file is required. Both must exist at the project root.
Without `[home]/`, the build fails with: `RuntimeError: TW project root not found.`

The root page must be `[home]/index.tw` for the site to load at `/`.

---

## Vercel

### vercel.json (recommended — minimal, no requirements.txt needed)

```json
{
  "buildCommand": "pip install --break-system-packages tw-framework && python -m tw_framework.cli build --prod",
  "outputDirectory": "dist"
}
```

**Why each flag:**
- `--break-system-packages` — Vercel's Python is managed by `uv`; bare `pip install` is rejected without this.
- `python -m tw_framework.cli` — the `tw` CLI entry-point is not always on PATH after `--break-system-packages` install. Using `python -m` is reliable.
- `--prod` — enables minification, gzip/brotli precompression, and cache-busting. Safe to use on v0.4.3+.

### Alternative: with requirements.txt

If you prefer a `requirements.txt` file:

**requirements.txt:**
```
tw-framework
```

**vercel.json:**
```json
{
  "buildCommand": "pip install --break-system-packages -r requirements.txt && python -m tw_framework.cli build --prod",
  "outputDirectory": "dist"
}
```

### Steps

1. Push your project to GitHub.
2. Go to [vercel.com](https://vercel.com) → New Project → Import your repo.
3. Vercel reads `vercel.json` automatically — no manual settings needed.
4. Deploy. The `dist/` folder is served as static output.

---

## Netlify

**netlify.toml:**
```toml
[build]
command = "pip install tw-framework && python -m tw_framework.cli build --prod"
publish = "dist"
```

Netlify does not use `uv`, so `--break-system-packages` is not needed.

---

## Cloudflare Pages

**Build command:**
```
pip install tw-framework && python -m tw_framework.cli build --prod
```

**Build output directory:**
```
dist
```

---

## GitHub Pages

Enable Pages (Source → GitHub Actions) and push. The included workflow builds and deploys automatically.

---

## Important Notes

### The `--prod` flag

On TW Framework **v0.4.3+**, `--prod` is safe and recommended. It enables:
- HTML/CSS/JS minification
- Gzip + Brotli precompression
- Hashed filenames for cache-busting
- HTML references are automatically updated to match hashed filenames

On versions **before v0.4.3**, `--prod` has a bug where CSS/JS filenames are hashed but HTML `<link>`/`<script>` references are not updated, causing 404s and broken styles. Use `--dev` as a workaround on older versions, or upgrade to v0.4.3+.

### Multi-line CSS values

On **v0.4.3+**, multi-line CSS property values in `.tss` files are handled correctly:

```css
/* This works on v0.4.3+ */
background-image:
  linear-gradient(...),
  linear-gradient(...);
```

On versions **before v0.4.3**, the TSS parser splits on every newline, breaking multi-line values into `true`. Either upgrade to v0.4.3+ or keep all values on a single line.

### Environment variables

Only env vars explicitly allow-listed in `tw.config` reach page render context:

```
env: public: "API_KEY, SITE_URL"
```

All other `os.environ` vars are server-only and never leak into generated HTML.

---

## Quick Reference

| Platform | Build command |
|---|---|
| Vercel | `pip install --break-system-packages tw-framework && python -m tw_framework.cli build --prod` |
| Netlify | `pip install tw-framework && python -m tw_framework.cli build --prod` |
| Cloudflare | `pip install tw-framework && python -m tw_framework.cli build --prod` |
| Local | `tw build --prod` |

All platforms output to `dist/`.
