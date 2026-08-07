# Version History

## v0.4.5 (current)

- LSP server with autocomplete and live diagnostics
- Fixed false positive errors (render static no longer flagged)
- Error positions now underline exact token
- Auto-closing braces disabled in VS Code extension
- ACode (mobile editor) plugin support
- File-resolution errors suppressed in LSP context

## v0.4.4

- Added LSP (Language Server Protocol) server
- Added VS Code extension with autocomplete and diagnostics
- Added ACode mobile editor plugin
- Added deployment documentation
- Updated README with feature comparison table

## v0.4.3

- Fixed --prod build: CSS/JS filenames hashed and HTML references auto-updated
- Fixed multi-line CSS values in .tss (no more true values)
- Security: os.environ no longer leaked to page render context
- Only allow-listed env vars reach page HTML

## v0.4.2

- Added tw dead command for dead code detection
- Added code splitting with shared runtime chunk
- Added incremental build cache
- Added build report generation (--report)
- Added build analysis (--analyze)

## v0.4.1

- Added tw export for static export
- Added tw serve command
- Added tw login for provider authentication
- Added Cloudflare Pages adapter
- Added Netlify adapter

## v0.4.0

- Complete rewrite of lexer and parser
- Added AST and IR pipeline
- Added semantic analysis
- Added .twm module support
- Added middleware system
- Added WebSocket support
- Added API routes

## v0.3.x

- Initial framework release
- Basic .tw and .tss compilation
- File-based routing
- Dev server with live reload
- Vercel deployment support
