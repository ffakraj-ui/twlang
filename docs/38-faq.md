# FAQ

## General

### Is TW Framework suitable for deployment?

TW Framework v0.4.5+ is stable for static sites and landing pages. API routes and middleware are functional but still maturing. Use `tw doctor` to check project health before deploying.

### Does TW use React or Vue?

No. TW has its own lexer, parser, AST, and code generator. It compiles `.tw` files directly to HTML/CSS/JS. No Virtual DOM, no React runtime, no framework abstraction layer.

### Can I build full web apps with TW?

TW is designed for websites — landing pages, blogs, portfolios, docs, catalogs. For complex web apps (dashboards, editors, real-time collaboration), React/Next.js may be more suitable. TW focuses on the 80% of websites that don't need client-side routing and complex state.

### How is TW different from Astro?

Both ship zero JS by default. Key differences:
- TW uses Python (runs on mobile via Termux); Astro requires Node.js
- TW has its own language (`.tw`/`.tss`); Astro uses HTML+JS in `.astro` files
- TW is a single `pip install`; Astro needs `npm` and 200MB+ of `node_modules`

## Syntax

### Do I need semicolons in TSS?

No. TSS doesn't require semicolons. Each property on its own line:

```css
.card {
    bg #fff
    radius 8px
    padding 16px
}
```

### Can I use regular CSS?

Yes. TSS is a superset of CSS — any valid CSS works in `.tss` files. The semicolons are optional, not forbidden.

### How do I escape `{` in text?

Use backslash: `\{` and `\}`.

### Can I use TypeScript?

TW has its own language — no TypeScript needed. Server-side code in `.twm` files uses plain JavaScript.

## Performance

### How much JS does TW ship?

- Static page: 0 bytes
- Page with `on:click`: ~2KB (reactive runtime)
- Page with `bind:value`: ~2KB (reactive runtime)

### Does TW support SSR?

Yes — `render server` generates HTML per-request. `render static` generates at build time. `render edge` generates at CDN edge.

### Does TW support SSG (static site generation)?

Yes — `render static` is the default and generates static HTML at build time. Use `tw export` for pure static output.

## Development

### Can I develop on my phone?

Yes! Install Termux, then:

```bash
pkg install python
pip install tw-framework
tw create my-site
cd my-site
tw dev
```

Use ACode editor with the TW Language Support plugin for syntax highlighting and autocomplete.

### Does TW support hot module replacement (HMR)?

TW supports live reload — the browser refreshes when files change. CSS is hot-swapped without full page refresh.

### How do I debug?

1. `tw check <file>` — prints diagnostics for a `.tw` file
2. `tw build --debug` — verbose build output
3. `tw doctor` — project health checks
4. Dev server shows errors in browser with line numbers

## Deployment

### Can I deploy to GitHub Pages?

Yes:
```bash
tw export
```
Then serve the `dist/` folder via GitHub Pages. API routes won't work (static only).

### Does TW support Docker?

Yes:
```bash
tw deploy --provider docker
```

### Can I self-host?

Yes. Run `tw serve` to serve the built site:

```bash
tw build --prod
tw serve --port 8080
```

## Limitations

### What TW doesn't do (yet)

- No client-side routing (multi-page apps need full page loads)
- No image optimization (use pre-compressed images)
- No built-in CMS integration
- No i18n/internationalization built-in
- No testing framework (use pytest for .twm modules)

### Maximum project size?

No hard limit. Incremental caching keeps build times manageable for large projects (100+ pages tested).
