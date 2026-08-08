# Glossary

## TW Framework Terms

| Term | Definition |
|---|---|
| .tw | TW markup file - contains page config, markup, and logic |
| .tss | TW stylesheet file - CSS without semicolons, with aliases |
| .twm | TW module file - server-side JavaScript for API routes |
| [home] | Source root directory (literal square brackets) |
| tw.config | Project configuration file |
| AST | Abstract Syntax Tree - parsed representation of .tw source |
| IR | Intermediate Representation - lowered form of AST |
| LSP | Language Server Protocol - provides autocomplete and diagnostics |
| SSG | Static Site Generation - HTML at build time (render static) |
| SSR | Server-Side Rendering - HTML per request (render server) |
| Edge | Edge rendering - HTML at CDN (render edge) |
| Void element | Self-closing HTML tag (img, br, hr, meta) |
| Reactive binding | on:click / bind:value directive for interactivity |
| Layout chain | Multiple layouts applied in sequence: layout "base > docs" |
| Page block | page { ... } block with page metadata |
| Load directive | load "@./path" - imports stylesheets, JSON, or modules |
| Import directive | import "Component" - imports a component |
| Middleware | middleware.tw - request processing rules |
| Revalidate | Cache TTL - page regenerates after N seconds |
| Code splitting | Automatic per-page JS chunks |
| Dead code | Unused pages, components, layouts detected by tw dead |
| Incremental cache | .tw/ directory - caches compiled pages |
| Precompression | .gz and .br files generated at build time |
| Content hashing | Filenames include hash for cache-busting |
| Token | Lexer output - WORD, STRING, BRACE, NL |
| Interpolation | {variable} in text to insert variable values |
| Render mode | static, server, or edge |
| CSRF | Cross-Site Request Forgery - prevented with tokens |
| CORS | Cross-Origin Resource Sharing - configured via middleware |
| Token bucket | Rate limiting algorithm used by TW middleware |
| TWM | TW Module - server-side JavaScript file |

## File Types

| Extension | Type | Purpose |
|---|---|---|
| .tw | TW source | Page markup and logic |
| .tss | TSS stylesheet | Styles |
| .twm | TW module | Server-side JavaScript |
| .json | Data file | Loaded with load directive |
| tw.config | Config file | Project configuration |
| vercel.json | Deploy config | Vercel deployment settings |
| netlify.toml | Deploy config | Netlify deployment settings |

## CLI Quick Reference

| Command | Purpose |
|---|---|
| tw create | New project |
| tw dev | Dev server |
| tw build | Production build |
| tw export | Static export |
| tw preview | Preview build |
| tw deploy | Deploy to hosting |
| tw doctor | Health check |
| tw check | Diagnostics for a file |
| tw info | Project summary |
| tw dead | Dead code detection |
| tw clean | Clear cache |
| tw ast | Print AST JSON |
| tw ir | Print IR JSON |
| tw tokens | Print lexer tokens |
| tw serve | Serve production build |
| tw login | Authenticate with provider |
