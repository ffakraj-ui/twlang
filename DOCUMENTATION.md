# TW Framework – Complete Technical Handover Document

## 1. Project Overview

- **Project Name:** TW Framework (TWMODS Site)
- **Purpose:** A static‑site generator and server‑side rendering framework that compiles `.tw` pages and `.twm` API routes into deployable output. It includes a built‑in dev server, production build pipeline, and adapters for Vercel, Netlify, and Cloudflare. The current project is a premium APK catalog website (TWMODS).
- **Main Features:**
  - Page routing via file‑system (`.tw` files in `pages/`)
  - Component system (`.tw` components in `components/`)
  - Layout system (`.tw` layouts in `layouts/`)
  - Styling via `.tss` files (TW Style Sheets)
  - API routes via `.twm` files (TW Modules)
  - Middleware system (`middleware.tw`)
  - Hot‑reload dev server
  - Production build with minification, pre‑compression, and route manifest
  - Deployment adapters for Vercel, Netlify, Cloudflare
- **Target Users:** Developers building static or server‑rendered websites, AI agents that need to understand the project structure, and maintainers.
- **Architecture Overview:** The framework is written in Python (compiler, CLI, dev server) and JavaScript (runtime helpers, API runner). Source files (`.tw`, `.twm`, `.tss`) are compiled into static HTML, CSS, and JavaScript bundles. The build pipeline is orchestrated by `tw_framework/framework.py`.
- **Technology Stack:**
  - Python 3.11+ (compiler, CLI, dev server)
  - Node.js 18+ (API runner, TypeScript compilation)
  - JavaScript (runtime helpers, client‑side bundles)
  - CSS (via `.tss` files)
  - HTML (output)

## 2. TW Framework Explanation

### 2.1 What TW Framework Is

TW Framework is a static‑site generator and server‑side rendering framework. It uses a custom file format (`.tw`) for pages and components, and `.twm` for API routes. The framework compiles these files into deployable output (HTML, CSS, JS) and provides a development server with live reload.

### 2.2 How `.tw` Files Work

- `.tw` files are page templates or components.
- They use a custom syntax that includes:
  - `page { ... }` block for page metadata (title, layout, etc.)
  - `head { ... }` for `<head>` content
  - `body { ... }` for the main content
  - `import "ComponentName"` to include components
  - `import { fn } from "@/lib/file"` to include client-side JS libraries (v0.8.43+)
  - `{slot}` placeholder for layout content
  - `{title}`, `{head}`, `{styles}`, `{scripts}` placeholders
- Example (`pages/index.tw`):
  ```
  page {
    title "TWMODS | Premium APK Catalog"
    layout "main"
    render static
  }
  body {
    h1 { text "Welcome to TWMODS" }
  }
  ```

### 2.3 How Routing Works

TW Framework supports two routing systems:

#### Legacy Routing (v0.5.x and earlier)

- Routes are derived from the file system under `pages/`.
- `pages/index.tw` → `/`
- `pages/about.tw` → `/about`
- `pages/services.tw` → `/services`
- `pages/contact.tw` → `/contact`
- `pages/work.tw` → `/work`
- Dynamic routes are supported via `[param]` in filenames (e.g., `pages/blog/[slug].tw`).
- The routing is handled by `compiler.discover_pages()` and `TWProject.resolve_route()`.
- Layouts are raw HTML templates in `layouts/` with `{slot}`, `{title}`, `{head}` placeholders.

#### App Router (v0.7.0+)

- Routes are derived from `page.tw` files in nested directories.
- `[home]/page.tw` → `/`
- `[home]/about/page.tw` → `/about`
- `[home]/blog/page.tw` → `/blog`
- `[home]/blog/[slug]/page.tw` → `/blog/:slug`
- Route groups `(folder)` are excluded from the URL: `(main)/about/page.tw` → `/about`
- Catch-all routes: `[...path]/page.tw` → `/*path`
- Layouts are TW components (`layout.tw` files) using the `children` keyword.
- Layouts nest automatically by directory structure.
- API routes use `route.tw` instead of `page.tw`.
- The routing is handled by `app_router.discover_routes()` and `app_router.match_route()`.
- Auto-detection: if `[home]/page.tw` or `[home]/layout.tw` exists → App Router mode; if `[home]/` exists → Legacy mode.
- See `docs/app-router.md` for the full guide.

### 2.4 How Components Work

- Components are `.tw` files placed in `components/`.
- They are imported into pages using `import "ComponentName"`.
- Components can accept parameters via attributes (e.g., `Button { label "Click" }`).
- The component system is compiled by the pipeline and produces reusable HTML/JS.


### 2.4.1 ES6 Library Imports (v0.8.43+)

TW supports ES6-style named imports for client-side JavaScript libraries:

```tw
import { startCountdown } from "@/lib/countdown"
import { formatData, parseJSON } from "@/lib/utils"
```

This loads `.js`, `.ts`, or `.mjs` files from `[home]/lib/`. Imported functions
can be used in `script` blocks:

```tw
import { startCountdown } from "@/lib/countdown"

body {
    div { id "countdown" }
    script { startCountdown() }
}
```

ES6 imports support `.js`, `.ts`, `.mjs` files. `.twm` modules use `load` directive.
Component imports and ES6 library imports work in parallel.

### 2.5 How Styling Works (`.tss`)

- `.tss` files are TW Style Sheets.
- They use a CSS‑like syntax with support for variables, nesting, and imports.
- The global stylesheet is `style.tss` in the project root.
- Component‑specific styles can be placed in `components/ComponentName.tss`.
- The compiler reads `.tss` files and outputs a single CSS file.

### 2.6 How Build Pipeline Works

- The build is triggered by `tw build` (or `build_hidden_site()` in `framework.py`).
- Steps:
  1. Load configuration (`tw.config`)
  2. Discover pages and components
  3. Compile each page (modular pipeline or legacy)
  4. Generate route manifest, API manifest, sitemap, RSS, robots.txt
  5. Pre‑compress output (gzip, brotli)
  6. Run deployment adapters (if specified)
- Output is placed in `dist/` (or custom `--out-dir`).

### 2.7 How SSR Works

- The dev server (`tw dev`) runs a Python HTTP server that compiles pages on‑the‑fly.
- It injects a live‑reload script into HTML.
- For production, pages are pre‑rendered to static HTML (SSG). No runtime SSR server is included; the output is static.

### 2.8 How Static Export Works

- `tw build` produces a fully static `dist/` directory.
- All pages are rendered to `.html` files.
- Assets are copied to `dist/assets/`.
- The output can be served by any static file server (nginx, Vercel, Netlify, Cloudflare Pages).

### 2.9 How API Routes Work

- API routes are `.twm` files placed in `api/`.
- Each `.twm` file exports functions named after HTTP methods (`get`, `post`, `put`, `patch`, `delete`, `options`) or a generic `handler`.
- The functions receive a `request` object and return a response.
- The runtime (`twm_api_runner.js`) executes the compiled module via Node.js.
- Example (`api/hello.twm`):
  ```
  fn get(request) {
    return { json: { message: "Hello" } }
  }
  ```

## 3. Complete Project Structure

```
/
├── pages/                     # Page templates (.tw)
│   ├── index.tw               # Home page (TWMODS catalog)
│   ├── about.tw               # About page (Veridian Systems)
│   ├── services.tw            # Services page
│   ├── contact.tw             # Contact page
│   └── work.tw                # Work page
├── components/                # Reusable components (.tw)
│   ├── Header.tw              # Site header with navigation
│   ├── Footer.tw              # Site footer with links
│   └── Button.tw              # (inferred, not present in provided files)
├── layouts/                   # Layout templates (.tw)
│   ├── default.tw             # Default layout (used by starter)
│   └── main.tw                # Main layout (used by TWMODS pages)
├── api/                       # API routes (.twm)
│   ├── health.twm
│   ├── echo.twm
│   ├── users.twm
│   ├── products.twm
│   ├── auth/
│   │   ├── login.twm
│   │   └── profile.twm
│   ├── forms/
│   │   └── contact.twm
│   ├── meta.twm
│   ├── status.twm
│   ├── delay.twm
│   ├── upload.twm
│   └── webhook.twm
├── public/                    # Static assets (images, fonts, etc.)
│   ├── images/
│   ├── fonts/
│   └── favicon.ico
├── dist/                      # Build output (generated)
│   ├── index.html
│   ├── about.html
│   ├── assets/
│   ├── _tw/
│   └── ...
├── tw_framework/              # Framework source code (Python)
│   ├── framework.py           # Main build orchestrator, dev server, CLI
│   ├── compiler.py            # Page/component compiler
│   ├── twm_parser.py          # .twm parser
│   ├── twm_api_runner.js      # Node.js runtime for API routes
│   ├── adapters/
│   │   ├── vercel.py
│   │   ├── netlify.py
│   │   ├── cloudflare.py
│   │   └── vercel_functions.py
│   └── ...
├── tw.config                  # Project configuration
├── middleware.tw              # Middleware rules
├── style.tss                  # Global stylesheet
├── package.json               # Node.js dependencies
├── DOCUMENTATION.md           # This file
└── README.md                  # Quick start guide
```

### Explanation of Key Files

- **`tw.config`**: Project configuration (name, routing, headers, redirects, rewrites, images, bundler, server settings).
- **`middleware.tw`**: Middleware rules for bot protection, origin checks, rate limiting, authentication, path protection.
- **`style.tss`**: Global CSS variables and base styles.
- **`package.json`**: Node.js dependencies (e.g., `firebase-admin` for API routes).
- **`tw_framework/framework.py`**: Contains `TWProject`, `TWDevState`, `TWFileWatcher`, dev server, build function, CLI argument parsing.
- **`tw_framework/compiler.py`**: Contains page discovery, compilation pipeline, asset handling, route manifest generation.
- **`tw_framework/twm_parser.py`**: Parses `.twm` files and compiles them to CommonJS modules.
- **`tw_framework/twm_api_runner.js`**: Node.js script that loads a compiled `.twm` module, installs runtime helpers, and executes the handler.

## 4. Website Implementation Details

### 4.1 Home Page (`pages/index.tw`)

- **Purpose:** Landing page for TWMODS premium APK catalog.
- **UI Sections:**
  - Hero section with headline, description, and CTA buttons
  - Hot Apps section (grid of app cards)
  - Popular Downloads section (wide cards)
  - Latest Premium APKs section (grid)
  - Recommended For You section (grid)
  - New section (wide cards)
  - Browse Categories section (category cards)
  - Search section (placeholder)
  - Request App section (CTA banner)
- **Components Used:** `Header`, `Footer` (via layout), `Button` (inferred)
- **Data Flow:** Static content defined in the `.tw` file.
- **Styling Classes:** `.twmods-home`, `.home-hero`, `.catalog-grid`, `.app-card`, `.wide-card`, `.category-grid`, `.search-bar-shell`, `.request-banner`
- **User Interactions:** Clicking CTA buttons navigates to sections or external links.

### 4.2 About Page (`pages/about.tw`)

- **Purpose:** Information about Veridian Systems (company).
- **UI Sections:**
  - Hero section with company tagline
  - Positioning section with values
  - Team grid (four cards)
  - Metric panels
  - CTA banner
- **Components Used:** `Header`, `Footer` (via layout)
- **Data Flow:** Static content.
- **Styling Classes:** `.page-hero`, `.split-grid`, `.team-grid`, `.metric-grid`, `.cta-banner`

### 4.3 Services Page (`pages/services.tw`)

- **Purpose:** List of services offered by Veridian Systems.
- **UI Sections:**
  - Hero section
  - Service cards (three cards)
  - Delivery model section with timeline
  - CTA banner
- **Components Used:** `Header`, `Footer` (via layout)
- **Data Flow:** Static content.
- **Styling Classes:** `.page-hero`, `.card-grid`, `.service-card`, `.split-grid`, `.timeline`, `.cta-banner`

### 4.4 Contact Page (`pages/contact.tw`)

- **Purpose:** Contact form and direct actions.
- **UI Sections:**
  - Hero section
  - Contact grid with direct actions (email, phone) and enquiry form
  - Service cards for email, call, work page
  - Suggested message format panel
- **Components Used:** `Header`, `Footer` (via layout)
- **Data Flow:** Static content; email and phone links are direct `mailto:` and `tel:`.
- **Styling Classes:** `.page-hero`, `.contact-grid`, `.contact-card`, `.contact-form`, `.card-grid`, `.highlight-panel`

### 4.5 Work Page (`pages/work.tw`)

- **Purpose:** Portfolio/projects showcase.
- **UI Sections:**
  - Hero section
  - Case study grid (four cards)
  - Quote card
  - CTA banner
- **Components Used:** `Header`, `Footer` (via layout)
- **Data Flow:** Static content.
- **Styling Classes:** `.page-hero`, `.case-grid`, `.case-card`, `.quote-card`, `.cta-banner`

## 5. UI/UX Documentation

### 5.1 Design System

- **Colors:**
  - Primary: `#2563eb` (blue)
  - Secondary: `#10b981` (green)
  - Background: `#f6f8fc` (light), `#081120` (dark)
  - Text: `#0f172a` (light), `#e5eefb` (dark)
  - Accent: `#f59e0b` (amber)
- **Typography:**
  - Font family: `Inter, system-ui, sans-serif`
  - Headings: `font-weight: 700`
  - Body: `font-weight: 400`, `line-height: 1.6`
- **Spacing:** 4px base unit (e.g., `padding: 1rem = 16px`)
- **Component Patterns:**
  - Cards: rounded corners (`border-radius: 8px`), shadow (`box-shadow: 0 2px 8px rgba(0,0,0,0.1)`)
  - Buttons: rounded, hover effect, focus ring
  - Navigation: horizontal list, active state underline

### 5.2 Header (`components/Header.tw`)

- Fixed top bar with brand logo, navigation links, theme toggle, and CTA buttons.
- Responsive: collapses to mobile footer navigation on small screens.
- Dark mode toggle button calls `__twToggleTheme`.

### 5.3 Footer (`components/Footer.tw`)

- Four columns: brand, explore links, categories, quick links.
- Bottom bar with copyright and powered‑by badge.
- Mobile footer navigation bar at bottom.

### 5.4 Navigation

- Desktop: horizontal links in header.
- Mobile: bottom navigation bar (`.mobile-footer-nav`).

### 5.5 Cards

- Used for app listings, services, case studies.
- Structure: cover (with icon, badge, size), body (title, subtitle, description, meta).

### 5.6 Buttons

- Primary: filled background, white text.
- Secondary: outlined.
- Ghost: minimal style.
- Sizes: small, medium, large.

### 5.7 Sections

- Each page is divided into `<section>` elements with consistent padding.
- Sections have class `.section` and optional `.section-soft` for softer background.

### 5.8 Responsive Behavior

- Breakpoints: 640px (sm), 768px (md), 1024px (lg), 1280px (xl).
- Mobile: single column layout, reduced padding.
- Desktop: multi‑column grid, larger spacing.

## 6. API Documentation

### 6.1 `/api/health`

- **Method:** GET
- **Request:** None
- **Response:** `{ "status": "ok" }`
- **Auth:** None

### 6.2 `/api/echo`

- **Method:** POST
- **Request:** JSON body (any)
- **Response:** Echoes the request body
- **Auth:** None

### 6.3 `/api/users`

- **Method:** GET
- **Request:** None
- **Response:** Array of user objects
- **Auth:** JWT token required (header `Authorization: Bearer <token>`)

### 6.4 `/api/products`

- **Method:** GET
- **Request:** Query params: `?category=...`
- **Response:** Array of product objects
- **Auth:** None

### 6.5 `/api/auth/login`

- **Method:** POST
- **Request:** `{ "email": "...", "password": "..." }`
- **Response:** `{ "token": "..." }`
- **Auth:** None

### 6.6 `/api/auth/profile`

- **Method:** GET
- **Request:** None
- **Response:** User profile object
- **Auth:** JWT token required

### 6.7 `/api/forms/contact`

- **Method:** POST
- **Request:** `{ "name": "...", "email": "...", "message": "..." }`
- **Response:** `{ "success": true }`
- **Auth:** None

### 6.8 `/api/meta`

- **Method:** GET
- **Request:** None
- **Response:** Site metadata (name, version, etc.)
- **Auth:** None

### 6.9 `/api/status`

- **Method:** GET
- **Request:** None
- **Response:** `{ "uptime": ..., "version": "..." }`
- **Auth:** None

### 6.10 `/api/delay`

- **Method:** GET
- **Request:** Query param: `?ms=2000`
- **Response:** `{ "delayed": true, "ms": 2000 }`
- **Auth:** None

### 6.11 `/api/upload`

- **Method:** POST
- **Request:** Multipart form data (file)
- **Response:** `{ "url": "..." }`
- **Auth:** JWT token required

### 6.12 `/api/webhook`

- **Method:** POST
- **Request:** JSON body (any)
- **Response:** `{ "received": true }`
- **Auth:** Secret header `X-Webhook-Secret`

### Error Responses

All APIs return standard HTTP status codes:
- `200` – Success
- `400` – Bad request
- `401` – Unauthorized
- `403` – Forbidden
- `404` – Not found
- `405` – Method not allowed
- `429` – Rate limited
- `500` – Internal server error

Error body: `{ "error": "message" }`

## 7. Middleware & Security

### 7.1 `middleware.tw` System

The middleware file defines rules that are applied to every incoming request during development and production (via the build output). Rules are evaluated in order.

### 7.2 Bot Protection

- **Rule:** `blocked-bots`
- **Match:** `/**`
- **User‑Agent:** Allows `googlebot`, `bingbot`, `gptbot`; blocks `curl/`, `wget/`, `python-requests`, `scrapy`; blocks empty user‑agent.
- **Response:** 403 Forbidden

### 7.3 Path Protection

- **Rule:** `scanner-paths`
- **Match:** `/**`
- **Path:** Blocks prefixes like `/wp-admin`, `/wp-login`, `/.env`, `/.git`; blocks extensions `.php`, `.env`, `.bak`, `.sql`; blocks traversal and null bytes.
- **Response:** 404 Not Found

### 7.4 Admin Authentication

- **Rule:** `admin-auth`
- **Match:** `/admin/**`
- **Auth:** Requires cookie `admin_token` with a valid JWT signed by `JWT_SECRET` environment variable.
- **Response:** 401 Unauthorized

### 7.5 API Origin Protection

- **Rule:** `api-origin`
- **Match:** `/api/**`
- **Methods:** GET, POST
- **Origin:** Allows `https://twmods.in` and `http://localhost:3000`; requires origin; allows referer.
- **Response:** 403 Forbidden with JSON error

### 7.6 Rate Limiting

- **Rule:** `api-rate-limit`
- **Match:** `/api/**`
- **Rate:** 60 requests per 60 seconds, identity based on path (first two segments).
- **Response:** 429 Too Many Requests

### 7.7 Security Considerations

- All middleware rules are applied in the dev server and also compiled into the build output (via Vercel/Netlify/Cloudflare config).
- JWT secrets should be stored in environment variables, not in code.
- CORS headers are not set by default; the API origin rule provides basic protection.
- The middleware system is extensible; new rules can be added to `middleware.tw`.

## 8. Build and Deployment

### 8.1 Commands

| Command | Description |
|---------|-------------|
| `tw dev` | Start development server with live reload |
| `tw build` | Production build to `dist/` |
| `tw preview` | Serve the built output locally |
| `tw export` | Alias for `tw build` |
| `tw doctor` | Check project health |
| `tw info` | Display project information |
| `tw clean` | Remove build artifacts |
| `tw deploy` | Build and deploy to a provider |

### 8.2 Development Workflow

1. Run `tw dev` (default port 3000).
2. Edit `.tw`, `.tss`, `.twm` files; browser auto‑reloads.
3. Test API routes via `curl` or browser.

### 8.3 Production Workflow

1. Run `tw build --prod` (or `tw build` with minification).
2. Output is in `dist/`.
3. Deploy using one of the adapters.

### 8.4 Deployment Process

- **Vercel:** `tw deploy --provider vercel --prod`
- **Netlify:** `tw deploy --provider netlify --prod`
- **Cloudflare:** `tw deploy --provider cloudflare --prod`
- **GitHub Pages:** `tw deploy --provider github-pages` (generates workflow file)
- **Docker:** `tw deploy --provider docker` (builds Docker image)

### 8.5 Adapter Details

- **Vercel:** Generates `.vercel/output/config.json` and copies static files. API routes become serverless functions.
- **Netlify:** Generates `netlify.toml` and copies functions to `netlify/functions/`.
- **Cloudflare:** Generates `_routes.json` and `_worker.js` for Cloudflare Pages.

## 9. Configuration

### 9.1 `tw.config`

The main configuration file uses a custom DSL. Key sections:

- `name`: Project name
- `pretty_urls`: Enable clean URLs (no `.html` extension)
- `modular_pipeline`: Use the new compilation pipeline
- `theme`: `system`, `light`, or `dark`
- `server.external_packages`: Node.js packages available in API routes
- `images.remote_patterns`: Allowed image domains
- `bundler.client_externals`: Packages excluded from client bundle
- `headers.rule`: Custom HTTP headers per path
- `redirects.rule`: URL redirects
- `rewrites.rule`: URL rewrites

### 9.2 Environment Variables

| Variable | Description |
|----------|-------------|
| `JWT_SECRET` | Secret for JWT signing (used in middleware) |
| `TW_CSRF_SECRET` | Secret for CSRF token generation |
| `VERCEL_TOKEN` | Vercel API token for deployment |
| `TW_WATCH_INTERVAL` | File watcher polling interval (seconds) |
| `TW_TWM_TIMEOUT` | Timeout for API route execution (seconds) |

### 9.3 JWT Secrets

- Used by `middleware.tw` for admin authentication.
- Set via environment variable `JWT_SECRET`.
- The middleware reads `jwt_secret_env` to get the variable name.

### 9.4 API Configuration

- API routes are defined in `api/` directory.
- Each `.twm` file is compiled to a Node.js module.
- The runtime (`twm_api_runner.js`) provides helpers: `http`, `env`, `secrets`, `pkg`, `firebase`.

### 9.5 Plugin Configuration

- Plugins are managed by `ExtensionManager` in `plugin_runtime.py`.
- Not yet documented in detail; see `tw_framework/plugin_runtime.py`.

### 9.6 Deployment Adapters

- Adapters are in `tw_framework/adapters/`.
- Each adapter has a `generate_*_output()` function that takes `dist_dir`, `config`, `project_root`.
- The build loop calls the appropriate adapter based on `--adapter` flag.

## 10. Developer Guide

### 10.1 Best Practices

- Keep pages small; use components for reusable UI.
- Use `.tss` for global styles; component styles can be inline or in separate `.tss` files.
- Always test API routes with `tw dev` before deployment.
- Use environment variables for secrets; never hardcode them.
- Run `tw doctor` before deployment to catch common issues.

### 10.2 Naming Conventions

- Pages: `kebab-case.tw` (e.g., `about-us.tw`)
- Components: `PascalCase.tw` (e.g., `Button.tw`)
- API routes: `kebab-case.twm` (e.g., `user-profile.twm`)
- Stylesheets: `kebab-case.tss` (e.g., `button.tss`)

### 10.3 Recommended Workflow

1. Create a new page in `pages/`.
2. Add components in `components/`.
3. Style with `.tss` files.
4. Test with `tw dev`.
5. Build with `tw build`.
6. Deploy with `tw deploy --provider <name>`.

### 10.4 Common Mistakes

- Forgetting to import a component in a page.
- Using top‑level statements in `.twm` files (only function definitions allowed).
- Not setting `JWT_SECRET` environment variable when using admin middleware.
- Running `tw build` without first installing Node.js dependencies (`npm install`).

---

*This document was generated for the TW Framework project. For questions, refer to the source code or open an issue.*
