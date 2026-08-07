# Optimization Checklist

## Performance

- [ ] Use `render static` for all non-dynamic pages
- [ ] Add `revalidate` for pages that need periodic refresh
- [ ] Use `loading "lazy"` on below-the-fold images
- [ ] Use `fetchpriority "high"` on hero images
- [ ] Pre-compress images to WebP or AVIF
- [ ] Use CSS aliases (bg, radius, shadow, font)
- [ ] Minimize on:* and bind:* directives (each adds JS)
- [ ] Use `tw build --prod` for production
- [ ] Check build report: `tw build --prod --report`
- [ ] Remove dead code: `tw dead`

## CSS

- [ ] Use CSS custom properties for repeated values
- [ ] Use @media for responsive design
- [ ] Remove unused styles
- [ ] Use transition sparingly
- [ ] Use will-change for animated elements

## HTML

- [ ] Use semantic HTML (header, main, footer, nav, article)
- [ ] Add alt text to all images
- [ ] Add width and height to images
- [ ] Use loading "lazy" on below-the-fold images
- [ ] Minimize DOM depth
- [ ] Use aria-* attributes for accessibility

## Build

- [ ] Run `tw build --prod` (not just `tw build`)
- [ ] Check for gzip/brotli files in dist/
- [ ] Verify hashed filenames in HTML references
- [ ] Run `tw build --analyze` to check bundle sizes
- [ ] Remove dead code with `tw dead`
- [ ] Clear cache before final build

## Deployment

- [ ] Configure vercel.json with --break-system-packages
- [ ] Use python -m tw_framework.cli (not tw)
- [ ] Set outputDirectory to dist
- [ ] Configure cache headers in tw.config
- [ ] Set up environment variables
- [ ] Run tw doctor before deploying

## Security

- [ ] Don't expose secrets in env { public ... }
- [ ] Use auth middleware for protected routes
- [ ] Add rate_limit to API routes
- [ ] Add security headers
- [ ] Use CSRF tokens in forms
- [ ] Validate all user input server-side

## SEO

- [ ] Set page { title "..." } on every page
- [ ] Add seo { description "..." } for meta description
- [ ] Add Open Graph tags
- [ ] Add robots.txt
- [ ] Check sitemap is generated
- [ ] Add canonical URLs
