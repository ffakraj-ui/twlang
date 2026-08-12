# Client-Side Bundling — Capabilities & Limitations

This document honestly describes what TW Framework's client-side bundler can and
cannot do, and how it compares to Next.js's webpack/turbopack.

## esbuild Integration (v0.9.30) — Real Bundling ✅

TW Framework v0.9.30 integrates **esbuild** as its client-side bundler. esbuild is
an extremely fast JavaScript bundler (written in Go) that handles:

- **CJS → ESM conversion** — CommonJS packages are properly converted
- **Tree shaking** — Dead code is eliminated, only used exports are included
- **Transitive dependency resolution** — All nested deps are bundled recursively
- **Minification** — Output is minified for production
- **Browser polyfills** — `process.env.NODE_ENV` is set to `"production"`
- **JSX/TSX transforms** — esbuild handles these natively

### How It Works

When you build a page with client-side npm imports:

1. TW detects all npm package imports in `.tw` and `.twm` files
2. For each package, esbuild bundles it from `node_modules`:
   - Resolves the package entry point (browser > module > main)
   - Bundles all transitive dependencies into a single file
   - Converts CJS to browser-compatible IIFE format
   - Tree-shakes unused exports
   - Minifies the output
3. The bundled chunk is written to `dist/_tw/chunks/npm/`
4. An import map is generated mapping bare specifiers to chunk URLs
5. `<script type="importmap">` and `<script src="...">` tags are injected into HTML

### Fallback (No esbuild)

If esbuild is not installed, TW falls back to a basic IIFE wrapper that:
- Wraps CJS modules in a function scope with `module`, `exports`, `require()` shim
- Provides stubs for 12 common Node.js built-ins (fs, path, process, etc.)
- Resolves transitive dependencies manually (recursive package.json reading)

**To get full bundling, install esbuild:**
```bash
tw install --save-dev esbuild
```

### Verified Working

| Package | Format | Deps | esbuild Bundle | IIFE Fallback |
|---------|--------|------|----------------|----------------|
| dayjs | CJS | none | ✅ 13,497 bytes | ✅ 7,682 bytes |
| lodash | CJS | none | ✅ | ✅ |
| chart.js | CJS | simple | ✅ | ✅ |
| react | CJS/ESM | react-dom | ✅ | ⚠️ partial |

### What Still Doesn't Work (Honest)

Even with esbuild, some things are NOT supported:

- **HMR / Fast Refresh** — No hot module replacement; changes require full rebuild
- **Source maps** — Not generated (planned for future)
- **Code splitting** — One chunk per package (esbuild supports it but TW doesn't use it yet)
- **CSS-in-JS** — Packages like styled-components need additional loaders
- **Worker imports** — `new Worker(new URL(...))` is not supported

## Comparison with Next.js

| Feature | TW v0.9.30 (esbuild) | TW (fallback) | Next.js |
|---------|---------------------|--------------|---------|
| NPM install | ✅ `tw install` | ✅ | ✅ `npm install` |
| Server-side (.twm) | ✅ Full Node.js | ✅ | ✅ Full Node.js |
| CJS → ESM conversion | ✅ esbuild | ✅ Basic IIFE | ✅ webpack/turbopack |
| Transitive deps | ✅ esbuild resolves | ✅ Manual recursive | ✅ Full resolution |
| Tree shaking | ✅ esbuild | ❌ | ✅ |
| Minification | ✅ esbuild | ❌ | ✅ |
| Node built-in stubs | ✅ esbuilt + 12 stubs | ✅ 12 stubs | ✅ node-polyfill |
| Source maps | ❌ Planned | ❌ | ✅ |
| Code splitting | ❌ One chunk/pkg | ❌ | ✅ Automatic |
| HMR / Fast Refresh | ❌ Full rebuild | ❌ | ✅ Instant |
| JSX/TSX transform | ✅ esbuild handles | ❌ | ✅ Built-in |
| CSS handling | ❌ Not in bundles | ❌ | ✅ CSS Modules etc. |
| Dynamic imports | ✅ Detected | ✅ Detected | ✅ Full support |

## Server-Side (.twm) — Zero Limitations

NPM packages imported in `.twm` files run via Node.js at build time with
**zero limitations** — any npm package works:

```javascript
// [home]/lib/data.twm
import dayjs from "dayjs"    // ← works, verified

export function formatDate(date) {
    return dayjs(date).format("DD/MM/YYYY")  // ← runs in Node.js
}
```

**Verified**: `currentYear()` → `2026`, `formatDate("2026-08-10")` → `10/08/2026`

## Installation

```bash
# Install TW framework
pip install tw-framework

# Install npm packages
tw install dayjs react react-dom

# Install esbuild for full client-side bundling (recommended)
tw install --save-dev esbuild

# Build
tw build
```

## Summary

| Scenario | Works? | How |
|----------|--------|-----|
| Server-side npm packages (.twm) | ✅ Full | Node.js execution |
| Simple client packages (dayjs, lodash) | ✅ Full | esbuild or IIFE fallback |
| Complex client packages (react, chart.js) | ✅ With esbuild | esbuild bundling |
| Packages without esbuild | ⚠️ Basic | IIFE wrapper (may fail on complex CJS) |
| HMR / Fast Refresh | ❌ | Planned for future |
| Source maps | ❌ | Planned for future |
