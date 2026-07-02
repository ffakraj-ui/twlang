# SECURITY

## Trust model

- TW exposes security-related primitives such as middleware headers, rate limiting, CSRF helpers, cookie transport settings, and SSR cache controls.
- These primitives are opt-in. The framework provides mechanisms; application policy stays with the developer.
- API handlers are expected in `[home]/api/**/route.twm` and run as trusted server project code.

## Default fixes

- Path containment checks use real path-boundary validation instead of prefix-only checks.
- Static and preview file serving use path-within checks to avoid sibling-prefix traversal mistakes.
- Additional MIME mappings are registered for common modern asset types.
- Edge-page cache keys include request variation by default to avoid leaking cached SSR output across sessions.

## Operator guidance

- Set `TW_CSRF_SECRET` or `SECRET_KEY` in production if you use CSRF helpers.
- Use `cookies.secure: auto` or `true` in HTTPS deployments.
- Prefer explicit `cache_by` selectors for personalized edge pages when you want a narrower cache key than the default.
- Review project plugins and `.twm` API files before deploying, because they execute with full server trust.
