# Ecosystem and Roadmap

## Current Features (v0.4.5)

### Language
- .tw markup language with lexer, parser, AST, IR
- .tss stylesheet language with CSS aliases
- .twm server-side JavaScript modules
- Text interpolation with {variable}
- Comments (// and /* */)

### Framework
- File-based routing with dynamic routes
- Components and layouts
- Reactive bindings (on:click, bind:value)
- Middleware (auth, rate limit, CORS, path validation)
- Built-in SEO (seo {} block)
- Built-in search index
- Environment variable security
- Code splitting
- Dead code detection
- Incremental build cache

### CLI (16 commands)
- create, init, dev, build, export, preview, deploy
- doctor, check, info, ast, ir, run, tokens, clean, serve, login

### Editor Support
- VS Code extension (syntax highlighting, LSP)
- ACode Android plugin (syntax highlighting, LSP)
- Standalone LSP server (JSON-RPC over stdio)

### Deployment
- Vercel (with serverless functions)
- Netlify (with Netlify functions)
- Cloudflare Pages (with Workers)
- Static export (GitHub Pages, S3)
- Docker
- One-command deploy (tw deploy)

## Planned Features

### v0.5.0
- Image optimization pipeline
- Client-side router (SPA mode)
- Internationalization (i18n) built-in
- Plugin system for custom compiler extensions
- Hot Module Replacement (HMR) in dev server

### v0.6.0
- Built-in analytics dashboard
- A/B testing framework
- Edge middleware
- Streaming SSR
- Partial hydration

### v1.0.0
- Stable API guarantee
- Full documentation website
- Plugin marketplace
- Template gallery
- Community themes

## Community

- GitHub: https://github.com/ffakraj-ui/twlang
- PyPI: https://pypi.org/project/tw-framework/
- Issues: https://github.com/ffakraj-ui/twlang/issues

## Contributing

```bash
git clone https://github.com/ffakraj-ui/twlang.git
cd twlang
pip install -e .
tw create test-site
cd test-site
tw dev
```
