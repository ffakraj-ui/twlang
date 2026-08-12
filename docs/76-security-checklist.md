# Security Checklist

## Environment Variables

- [ ] All secrets in .env file (not committed to git)
- [ ] .env in .gitignore
- [ ] Only public vars in env { public ... }
- [ ] DATABASE_URL, JWT_SECRET, API_KEY NOT in public env
- [ ] Required env vars validated with schema

## Authentication

- [ ] Protected routes use auth { cookie "...", redirect "..." }
- [ ] API routes check authentication
- [ ] JWT tokens have expiry
- [ ] Cookies are httpOnly: true
- [ ] Cookies are secure: true in production

## Input Validation

- [ ] All API inputs validated server-side
- [ ] POST bodies checked for required fields
- [ ] Query params sanitized
- [ ] Route params validated
- [ ] File uploads checked for type and size

## Middleware

- [ ] Rate limiting on API routes
- [ ] Rate limiting on auth endpoints (stricter)
- [ ] CORS configured for allowed origins only
- [ ] Path traversal protection enabled
- [ ] Null byte protection enabled
- [ ] User agent filtering for bots

## Headers

- [ ] X-Content-Type-Options: nosniff
- [ ] X-Frame-Options: DENY or SAMEORIGIN
- [ ] X-XSS-Protection: 1; mode=block
- [ ] Referrer-Policy: strict-origin-when-cross-origin
- [ ] Content-Security-Policy configured

## CSRF

- [ ] CSRF tokens in all forms
- [ ] CSRF tokens verified on POST/PUT/DELETE
- [ ] Tokens have expiry (2 hours default)

## XSS Prevention

- [ ] Text interpolation auto-escapes HTML
- [ ] No innerHTML with user data in scripts
- [ ] No eval() with user data
- [ ] Content Security Policy header set

## Rate Limiting

- [ ] API routes: 100 req/60 sec per IP
- [ ] Login: 5 req/60 sec per IP
- [ ] Registration: 3 req/60 sec per IP
- [ ] Password reset: 3 req/60 sec per IP

## Deployment

- [ ] HTTPS enforced
- [ ] tw doctor passes before deploy
- [ ] No debug mode in production
- [ ] Error messages don't expose stack traces

## Dependencies

- [ ] Regularly update tw-framework
- [ ] Audit third-party packages
- [ ] No unnecessary packages in external_packages
