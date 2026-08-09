# Changelog

## v0.8.0 (2026-08-09)

### Major Features

#### Virtual DOM (VDOM)
- TW-native Virtual DOM with diff-and-patch algorithm (~3KB gzipped, no React dependency)
- O(n) diffing with keyed children support
- Batched updates via `requestAnimationFrame`
- Auto-detection: VDOM injected only when page uses state/events
- `render interactive` mode forces VDOM
- New directives: `tw-if`, `tw-else`, `tw-key`
- VDOM public API: `__tw.h()`, `__tw.text()`, `__tw.set()`, `__tw.get()`, `__tw.watch()`
- Server-side HTML is initial VDOM state (no hydration mismatch)

#### Lib System Overhaul
- `import { getData } from "@/lib/data"` syntax (Next.js-style)
- Supports named, default, namespace, and default+named imports
- Module resolution: `@/` prefix, relative paths, extension auto-detection
- Async/await support in `.twm` files
- TypeScript-style type annotations (stripped before execution)
- Client-side functions: `export client function` ships to browser
- Backward compatible with v0.7.x `execute_lib_function` API

#### Server Actions
- `action {}` block syntax in `.tw` pages
- Call server functions from client without API routes
- `__twAction("name", args)` client-side helper
- CSRF + auth validation support
- Rate limiting support

#### Metadata API
- Static `metadata {}` block
- Dynamic `generateMetadata {}` block
- Supports title, description, og-image, twitter-card

#### ISR (Incremental Static Regeneration)
- `revalidate N` directive in page block
- Background page regeneration after N seconds

#### Suspense & Streaming
- `__twSuspense()` client-side helper
- Progressive page loading support

#### Error Boundaries
- `error.tw` catches runtime errors
- Error boundary JS auto-injected

### Other Changes
- `render interactive` and `render dynamic` modes added to compiler
- Reactivity module completely rewritten as VDOM system
- Lib executor completely rewritten with import support
- 74 new tests (474 total, all passing)
- Zero-JS preservation verified for static pages

### Breaking Changes
- `reactivity.py` API changed: `get_reactivity_runtime_js()` → `get_vdom_runtime_js()` (old name kept as alias)
- `lib_executor.py` API: new `execute_lib_function` accepts old signature for backward compat

---

## v0.7.2 (2026-08-09)

- App Router scaffold in `tw create`
- Built-in Icons (60+ SVG, zero dependency)
- README rewrite (App Router focus)
- Detailed App Router guide

## v0.7.1 (2026-08-08)

- Client-side navigation (`link` keyword)
- `generateStaticParams` for dynamic routes
- `route.tw` API handlers

## v0.7.0 (2026-08-08)

- App Router architecture
- Layouts with `children` keyword
- Route groups `(folder)`
- Dynamic routes `[slug]`
- `not-found.tw` support

## v0.6.0 (2026-08-07)

- TW Image component
- Inline JSON data
- Tailwind utility class mapping
- Build cache system

## v0.5.0 (2026-08-06)

- Zero-JS static pages
- Comma syntax for attributes
- Build performance improvements

## v0.4.7 (2026-08-05)

- Lib system (`.twm` files)
- Type safety annotations
- Component classification
